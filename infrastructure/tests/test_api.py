import threading
import time

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import api.main as api


class DummyModel:
    # Modèle factice renvoyant toujours une forte probabilité de panne (0.8),
    # pour tester l'API de prédiction sans dépendre d'un vrai modèle entraîné.
    def predict_proba(self, x):
        return np.tile(np.array([[0.2, 0.8]]), (len(x), 1))


def _snapshot(cycle: int):
    # Construit une ligne de capteurs valide (tous les champs requis) pour un cycle donné.
    row = {"cycle": cycle, "setting_1": 0.0, "setting_2": 0.0, "setting_3": 100.0}
    row.update({f"sensor_{i}": float(i) for i in range(1, 22)})
    return row


def test_liveness_does_not_require_model():
    # Le endpoint /live (probe Kubernetes) doit répondre même sans modèle chargé :
    # il signale seulement que le processus tourne, pas qu'il est prêt à prédire.
    client = TestClient(api.app)
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_reports_missing_model(monkeypatch, tmp_path):
    # Le endpoint /ready doit renvoyer 503 tant qu'aucun modèle/metadata n'est chargé,
    # afin d'éviter de router du trafic vers une instance non opérationnelle.
    monkeypatch.setattr(api, "MODEL_PATH", tmp_path / "none.joblib")
    monkeypatch.setattr(api, "METADATA_PATH", tmp_path / "none.json")
    monkeypatch.setattr(api, "_model", None)
    monkeypatch.setattr(api, "_metadata", None)
    client = TestClient(api.app)
    assert client.get("/ready").status_code == 503


def test_prediction_contract_with_mocked_model(monkeypatch, tmp_path):
    # Vérifie le contrat complet de /predict avec un modèle et des metadata mockés :
    # la réponse expose bien le risque calculé et la version du modèle, et la
    # prédiction est journalisée sur disque (utile pour le futur retraining).
    monkeypatch.setattr(api, "_model", DummyModel())
    monkeypatch.setattr(
        api,
        "_metadata",
        {
            "threshold": 0.5,
            "selected_features": ["sensor_2_mean_5"],
            "model_name": "dummy",
            "model_version": "test-v1",
            "failure_window": 30,
            "dataset_manifest_sha256": "abc",
        },
    )
    monkeypatch.setattr(api, "PREDICTION_LOG_PATH", tmp_path / "predictions.jsonl")
    monkeypatch.setattr(api, "PREDICTION_BUCKET", None)  # pas d'upload cloud pendant le test
    client = TestClient(api.app)
    response = client.post(
        "/predict",
        json={"engine_id": 1, "history": [_snapshot(1), _snapshot(2)]},
    )
    assert response.status_code == 200
    body = response.json()
    # DummyModel renvoie 0.8 > threshold 0.5, donc le risque attendu est HIGH.
    assert body["risk"] == "HIGH"
    assert body["model_version"] == "test-v1"
    assert (tmp_path / "predictions.jsonl").exists()


def test_cycles_must_be_strictly_increasing():
    # L'historique de cycles doit être trié de façon strictement croissante ;
    # un ordre incohérent doit être rejeté par la validation (422) avant toute prédiction.
    client = TestClient(api.app)
    response = client.post(
        "/predict",
        json={"engine_id": 1, "history": [_snapshot(2), _snapshot(1)]},
    )
    assert response.status_code == 422


def test_metrics_endpoint_is_exposed():
    # Le endpoint /metrics doit exposer les métriques Prometheus (scrapées par le monitoring).
    client = TestClient(api.app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "predictmaint_predictions_total" in response.text


def _upload_csv(engine_ids, cycles_per_engine: int = 5) -> bytes:
    # Génère un CSV de retraining valide pour un ou plusieurs moteurs,
    # avec une étiquette "pas de panne" par défaut sur chaque ligne.
    rows = []
    for engine_id in engine_ids:
        for cycle in range(1, cycles_per_engine + 1):
            row = {"engine_id": engine_id, **_snapshot(cycle)}
            row["actual_failure_within_30_cycles"] = 0
            rows.append(row)
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def test_retrain_status_defaults_to_idle(monkeypatch):
    # L'état de retraining exposé par /retrain/status doit refléter fidèlement
    # l'état interne "idle" (aucun job en cours) fixé via monkeypatch.
    monkeypatch.setattr(
        api,
        "_retrain_status",
        {
            "state": "idle",
            "started_at": None,
            "finished_at": None,
            "rows_added": 0,
            "error": None,
            "model_version": None,
        },
    )
    client = TestClient(api.app)
    response = client.get("/retrain/status")
    assert response.status_code == 200
    assert response.json()["state"] == "idle"


def test_retrain_upload_rejects_missing_columns():
    # Un CSV auquel il manque les colonnes de capteurs requises doit être
    # rejeté (422) avant de déclencher un job de retraining.
    client = TestClient(api.app)
    response = client.post(
        "/retrain/upload",
        files={"file": ("bad.csv", b"engine_id,cycle\n1,1\n", "text/csv")},
    )
    assert response.status_code == 422


def test_retrain_upload_triggers_background_job_and_reports_failure(monkeypatch, tmp_path):
    # Vérifie que l'upload lance bien un job de retraining en arrière-plan,
    # et que l'échec du sous-processus d'entraînement remonte proprement
    # dans le statut (state="failed" + message d'erreur), sans planter l'API.
    monkeypatch.setattr(api, "PRODUCTION_FEATURES_PATH", tmp_path / "feedback_features.csv")

    started = threading.Event()

    def fake_run(cmd, check, env):
        # Simule l'échec du script de retraining réel (pas de subprocess dans les tests).
        started.set()
        raise RuntimeError("subprocess disabled in test")

    monkeypatch.setattr(api.subprocess, "run", fake_run)

    client = TestClient(api.app)
    response = client.post(
        "/retrain/upload",
        files={"file": ("new_data.csv", _upload_csv([1, 2]), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "retrain_triggered"
    assert body["rows_added"] == 2

    assert started.wait(timeout=5)
    # Le job tourne en tâche de fond : on attend la fin (ou un timeout) en pollant le statut.
    deadline = time.time() + 5
    status = client.get("/retrain/status").json()
    while status["state"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        status = client.get("/retrain/status").json()
    assert status["state"] == "failed"
    assert "subprocess disabled in test" in status["error"]


def test_retrain_upload_rejects_concurrent_trigger():
    # Un seul job de retraining doit pouvoir tourner à la fois : on prend le verrou
    # manuellement pour simuler un job déjà en cours, et on vérifie que la requête
    # suivante est rejetée (409) plutôt que de démarrer un second job en parallèle.
    assert api._retrain_lock.acquire(blocking=False)
    try:
        client = TestClient(api.app)
        response = client.post(
            "/retrain/upload",
            files={"file": ("new_data.csv", _upload_csv([3]), "text/csv")},
        )
        assert response.status_code == 409
    finally:
        api._retrain_lock.release()
