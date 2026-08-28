import numpy as np
from fastapi.testclient import TestClient

import api.main as api


class DummyModel:
    def predict_proba(self, x):
        return np.tile(np.array([[0.2, 0.8]]), (len(x), 1))


def _snapshot(cycle: int):
    row = {"cycle": cycle, "setting_1": 0.0, "setting_2": 0.0, "setting_3": 100.0}
    row.update({f"sensor_{i}": float(i) for i in range(1, 22)})
    return row


def test_liveness_does_not_require_model():
    client = TestClient(api.app)
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_reports_missing_model(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "MODEL_PATH", tmp_path / "none.joblib")
    monkeypatch.setattr(api, "METADATA_PATH", tmp_path / "none.json")
    monkeypatch.setattr(api, "_model", None)
    monkeypatch.setattr(api, "_metadata", None)
    client = TestClient(api.app)
    assert client.get("/ready").status_code == 503


def test_prediction_contract_with_mocked_model(monkeypatch, tmp_path):
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
    monkeypatch.setattr(api, "PREDICTION_BUCKET", None)
    client = TestClient(api.app)
    response = client.post(
        "/predict",
        json={"engine_id": 1, "history": [_snapshot(1), _snapshot(2)]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk"] == "HIGH"
    assert body["model_version"] == "test-v1"
    assert (tmp_path / "predictions.jsonl").exists()


def test_cycles_must_be_strictly_increasing():
    client = TestClient(api.app)
    response = client.post(
        "/predict",
        json={"engine_id": 1, "history": [_snapshot(2), _snapshot(1)]},
    )
    assert response.status_code == 422


def test_metrics_endpoint_is_exposed():
    client = TestClient(api.app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "predictmaint_predictions_total" in response.text
