from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import uuid4

import joblib
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field, model_validator
from starlette.responses import Response

try:
    from . import cloud_monitoring
except ImportError:
    # Chargement alternatif pour les tests
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import cloud_monitoring
from src.data.collect_feedback import append_feature_dataset, build_uploaded_feature_dataset
from src.features.build_features import build_causal_features
from src.monitoring.drift import current_features_from_prediction_log, statistical_drift_report

# Racine du projet pour exécuter les commandes depuis le bon répertoire
# Permet de définir explicitement via variable d'environnement, sinon détection automatique
if "PROJECT_ROOT" in os.environ:
    PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
else:
    # Détection automatique: chercher le répertoire contenant 'src' et 'storage'
    current = Path(__file__).resolve()
    for parent in [current.parent.parent, current.parent.parent.parent, current.parent.parent.parent.parent]:
        if (parent / "src").is_dir() or (parent / "api").is_dir():
            PROJECT_ROOT = parent
            break
    else:
        # Fallback: remonter 4 niveaux (structure locale)
        PROJECT_ROOT = current.parent.parent.parent.parent

# Fonction pour résoudre les chemins (absolus ou relatifs à PROJECT_ROOT)
def _resolve_path(env_var: str, default: str) -> Path:
    path_str = os.getenv(env_var, default)
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path

MODEL_PATH = _resolve_path("MODEL_PATH", "storage/models/model.joblib")
METADATA_PATH = _resolve_path("MODEL_METADATA_PATH", "storage/models/model_metadata.json")
PREDICTION_LOG_PATH = Path(os.getenv("PREDICTION_LOG_PATH", "/tmp/predictions.jsonl"))
FEEDBACK_LOG_PATH = Path(os.getenv("FEEDBACK_LOG_PATH", "/tmp/feedback.jsonl"))
PREDICTION_BUCKET = os.getenv("PREDICTION_BUCKET")
PRODUCTION_FEATURES_PATH = _resolve_path("SUPPLEMENTAL_FEATURES_PATH", "storage/production/feedback_features.csv")

# Configuration MLflow pour le retrain via API
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///storage/mlflow.db")
os.environ.setdefault("MLFLOW_TRACKING_URI", MLFLOW_TRACKING_URI)
if MLFLOW_TRACKING_URI.startswith("sqlite:///"):
    # Résoudre les chemins SQLite relatifs par rapport à PROJECT_ROOT
    db_path_str = MLFLOW_TRACKING_URI.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("predictmaint")

app = FastAPI(
    title="PredictMaint AI",
    version="2.0.0",
    description="API de maintenance prédictive sur le jeu de données FD001.",
)

# Configuration CORS pour permettre les appels depuis le dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pour démo/PoC - en production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREDICTIONS = Counter("predictmaint_predictions_total", "Nombre de prédictions", ["risk"])
LATENCY = Histogram("predictmaint_prediction_latency_seconds", "Latence de prédiction")
TELEMETRY_ERRORS = Counter("predictmaint_telemetry_errors_total", "Erreurs de persistance télémétrie", ["sink"])
MODEL_READY = Gauge("predictmaint_model_ready", "1 si le modèle est chargé")
DRIFT_SHARE = Gauge("predictmaint_drift_share", "Part des variables en dérive (PSI >= seuil)")
DRIFT_PSI = Gauge("predictmaint_drift_psi", "PSI par variable vs référence TRAIN", ["feature"])
CLOUD_MONITORING_EXPORT_ERRORS = Counter(
    "predictmaint_cloud_monitoring_export_errors_total",
    "Échecs d'export vers Cloud Monitoring"
)

DRIFT_CHECK_INTERVAL_SECONDS = int(os.getenv("DRIFT_CHECK_INTERVAL_SECONDS", "300"))
CLOUD_MONITORING_FLUSH_INTERVAL_SECONDS = int(os.getenv("CLOUD_MONITORING_FLUSH_INTERVAL_SECONDS", "60"))
GCP_REGION = os.getenv("GCP_REGION", "")

_model = None
_metadata = None


def load_assets(force: bool = False):
    # Charge (ou recharge) le modèle et ses métadonnées en cache mémoire
    global _model, _metadata
    if force:
        _model = None
        _metadata = None
    if _model is None:
        if not MODEL_PATH.exists() or not METADATA_PATH.exists():
            MODEL_READY.set(0)
            raise FileNotFoundError(
                "Artefacts modèle absents. Exécuter le pipeline d'entraînement avant l'API."
            )
        _model = joblib.load(MODEL_PATH)
        _metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        required = {"threshold", "selected_features", "model_name", "failure_window"}
        missing = sorted(required - set(_metadata))
        if missing:
            MODEL_READY.set(0)
            raise ValueError(f"Contrat modèle incomplet: {missing}")
        MODEL_READY.set(1)
    return _model, _metadata


# Relevé capteurs/réglages d'un moteur pour un cycle donné.
class Snapshot(BaseModel):
    cycle: int = Field(ge=1)
    setting_1: float
    setting_2: float
    setting_3: float
    sensor_1: float
    sensor_2: float
    sensor_3: float
    sensor_4: float
    sensor_5: float
    sensor_6: float
    sensor_7: float
    sensor_8: float
    sensor_9: float
    sensor_10: float
    sensor_11: float
    sensor_12: float
    sensor_13: float
    sensor_14: float
    sensor_15: float
    sensor_16: float
    sensor_17: float
    sensor_18: float
    sensor_19: float
    sensor_20: float
    sensor_21: float


class PredictionRequest(BaseModel):
    # Requête de prédiction : identifiant moteur + historique de relevés

    engine_id: int = Field(ge=1)
    history: List[Snapshot] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def cycles_must_increase(self):
        # Les features causales (fenêtres glissantes) supposent un historique
        # ordonné sans doublon : on rejette la requête sinon plutôt que de
        # produire une prédiction silencieusement erronée.
        cycles = [x.cycle for x in self.history]
        if cycles != sorted(cycles) or len(cycles) != len(set(cycles)):
            raise ValueError("history doit contenir des cycles uniques et strictement croissants")
        return self


# Réponse publique renvoyée par /predict (pas de features brutes exposées).
class PredictionResponse(BaseModel):
    prediction_id: str
    timestamp: str
    engine_id: int
    last_cycle: int
    failure_probability: float
    risk: str
    threshold: float
    model_name: str
    model_version: str | None = None


# Retour terrain associé à une prédiction déjà émise (pour évaluation/réentraînement).
class FeedbackRequest(BaseModel):
    prediction_id: str = Field(min_length=3, max_length=200)
    actual_failure_within_30_cycles: int = Field(ge=0, le=1)
    actual_rul: int | None = Field(default=None, ge=0)


def _persist_record(record: dict, local_path: Path, gcs_prefix: str) -> None:
    # Écrit un enregistrement JSONL en local puis, si configuré, sur GCS
    line = json.dumps(record, ensure_ascii=False, allow_nan=False)
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        TELEMETRY_ERRORS.labels(sink="local").inc()
        logger.exception("local telemetry persistence failed")

    if PREDICTION_BUCKET:
        try:
            # Import différé : évite la dépendance google-cloud-storage quand
            # PREDICTION_BUCKET n'est pas configuré (dev local).
            from google.cloud import storage

            client = storage.Client()
            object_id = record.get("prediction_id", str(uuid4()))
            blob = client.bucket(PREDICTION_BUCKET).blob(f"{gcs_prefix}/{object_id}.json")
            blob.upload_from_string(line, content_type="application/json")
        except Exception:
            TELEMETRY_ERRORS.labels(sink="gcs").inc()
            logger.exception("GCS telemetry persistence failed")


_retrain_lock = threading.Lock()
_retrain_status: dict = {
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "rows_added": 0,
    "error": None,
    "model_version": None,
    "optimize": False,
    "trials": 0,
}


def _run_retrain_job(rows_added: int, optimize: bool = True, trials: int = 30) -> None:
    # Lance le réentraînement complet en arrière-plan
    _retrain_status.update(
        state="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        rows_added=rows_added,
        error=None,
        optimize=optimize,
        trials=trials,
    )
    try:
        # On exécute directement les étapes au lieu d'utiliser src.pipelines.retrain
        # car ce dernier fusionne les prédictions/feedback depuis GCS, ce qui n'est
        # pas nécessaire ici vu que les données uploadées sont déjà ajoutées localement.
        env = {
            **os.environ,
            "INCLUDE_PRODUCTION_FEEDBACK": "1",
            "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI", "sqlite:///storage/mlflow.db"),
        }
        steps = [
            [sys.executable, "-m", "src.data.prepare"],
            [sys.executable, "-m", "src.features.select_features"],
            [sys.executable, "-m", "src.models.train"],
        ]
        # On ajoute l'optimisation Optuna et la promotion si demandé
        if optimize:
            steps.append([sys.executable, "-m", "src.models.optimize", "--trials", str(trials)])
            steps.append([sys.executable, "-m", "src.models.promote"])
        steps.extend([
            [sys.executable, "-m", "src.models.quality_gate"],
            [sys.executable, "-m", "src.models.register"],
        ])
        for cmd in steps:
            subprocess.run(cmd, check=True, env=env, cwd=PROJECT_ROOT)
        _, metadata = load_assets(force=True)
        _retrain_status.update(
            state="completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            model_version=metadata.get("model_version"),
        )
    except Exception as exc:
        logger.exception("automatic retrain failed")
        _retrain_status.update(
            state="failed", finished_at=datetime.now(timezone.utc).isoformat(), error=str(exc)
        )
    finally:
        _retrain_lock.release()


def _refresh_drift_metrics() -> None:
    # Recalcule le PSI par variable à partir des prédictions récentes de cette instance
    try:
        current = current_features_from_prediction_log(PREDICTION_LOG_PATH)
        report = statistical_drift_report(current)
        if report["status"] not in ("ok", "alert"):
            return
        DRIFT_SHARE.set(report["drifted_share"])
        for feature, value in report["psi_by_feature"].items():
            DRIFT_PSI.labels(feature=feature).set(value)
    except Exception:
        logger.exception("drift metrics refresh failed")


def _drift_monitor_loop() -> None:
    # Boucle de fond : recalcule périodiquement les métriques de dérive (drift)
    while True:
        _refresh_drift_metrics()
        time.sleep(DRIFT_CHECK_INTERVAL_SECONDS)


threading.Thread(target=_drift_monitor_loop, daemon=True).start()


def _cloud_monitoring_flush_loop() -> None:
    # Boucle de fond : pousse périodiquement les métriques vers GCP Cloud Monitoring
    while True:
        time.sleep(CLOUD_MONITORING_FLUSH_INTERVAL_SECONDS)
        try:
            cloud_monitoring.flush(
                GCP_REGION,
                predictions=PREDICTIONS,
                telemetry_errors=TELEMETRY_ERRORS,
                model_ready=MODEL_READY,
                drift_share=DRIFT_SHARE,
                drift_psi=DRIFT_PSI,
                latency=LATENCY,
            )
        except Exception:
            CLOUD_MONITORING_EXPORT_ERRORS.inc()
            logger.exception("Cloud Monitoring flush loop error")


threading.Thread(target=_cloud_monitoring_flush_loop, daemon=True).start()


@app.get("/live")
def liveness():
    # Sonde de liveness : le process répond, sans vérifier le modèle
    return {"status": "alive"}


@app.get("/ready")
def readiness():
    # Sonde de readiness : vérifie que le modèle et ses métadonnées sont chargeables
    try:
        _, metadata = load_assets()
        return {
            "status": "ready",
            "model": metadata.get("model_name"),
            "model_version": metadata.get("model_version"),
            "failure_window": metadata.get("failure_window"),
        }
    except Exception as exc:
        # 503 plutôt que 500 : signale explicitement une indisponibilité
        # temporaire (artefacts manquants) aux orchestrateurs de déploiement.
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
def health():
    # Alias de /ready, conservé pour compatibilité avec les checks génériques
    return readiness()


@app.get("/metrics")
def metrics_endpoint():
    # Expose les métriques Prometheus au format texte standard
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/feedback")
def feedback(payload: FeedbackRequest):
    # Enregistre le résultat réel observé pour une prédiction déjà émise
    record = {
        "prediction_id": payload.prediction_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_failure_within_30_cycles": payload.actual_failure_within_30_cycles,
        "actual_rul": payload.actual_rul,
    }
    _persist_record(record, FEEDBACK_LOG_PATH, "feedback")
    return {"status": "recorded", **record}


@app.post("/retrain/upload")
async def retrain_upload(file: UploadFile = File(...)):
    # Reçoit un CSV de données terrain, l'ajoute au jeu de features de
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Un réentraînement est déjà en cours.")
    try:
        content = await file.read()
        try:
            raw = pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"CSV illisible: {exc}") from exc
        try:
            new_rows = build_uploaded_feature_dataset(raw)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        rows_added = append_feature_dataset(new_rows, PRODUCTION_FEATURES_PATH)
    except HTTPException:
        # Validation échouée avant le lancement du job : libérer le verrou
        # immédiatement plutôt que d'attendre un job qui ne démarrera jamais.
        _retrain_lock.release()
        raise
    except Exception:
        _retrain_lock.release()
        raise

    # Le job tourne en arrière-plan : la requête HTTP répond immédiatement,
    # l'utilisateur peut suivre l'avancement via /retrain/status.
    # L'optimisation est activée par défaut pour garder la meilleure qualité
    thread = threading.Thread(target=_run_retrain_job, args=(rows_added, True, 30), daemon=True)
    thread.start()
    logger.info("automatic retrain triggered rows_added=%s optimize=True trials=30", rows_added)
    return {"status": "retrain_triggered", "rows_added": rows_added, "optimize": True, "trials": 30}


@app.get("/retrain/status")
def retrain_status():
    # Renvoie l'état courant (ou le dernier connu) du job de réentraînement
    return _retrain_status


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictionRequest):
    # Calcule la probabilité de panne à partir de l'historique fourni et
    start = time.perf_counter()
    model, metadata = load_assets()
    rows = [{"engine_id": payload.engine_id, **snap.model_dump()} for snap in payload.history]
    raw = pd.DataFrame(rows)
    feat = build_causal_features(raw)
    # Seul le dernier cycle de l'historique est prédit : les cycles précédents
    # ne servent qu'à calculer les features causales (fenêtres glissantes).
    last = feat.iloc[[-1]]
    features = metadata["selected_features"]
    missing = [c for c in features if c not in last.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"Features manquantes: {missing}")

    probability = float(model.predict_proba(last[features])[:, 1][0])
    # Seuil de décision fixé lors de l'entraînement (calibré, pas 0.5 par défaut).
    threshold = float(metadata["threshold"])
    risk = "HIGH" if probability >= threshold else "LOW"
    now = datetime.now(timezone.utc)
    prediction_id = str(uuid4())

    public_record = {
        "prediction_id": prediction_id,
        "timestamp": now.isoformat(),
        "engine_id": payload.engine_id,
        "last_cycle": int(last["cycle"].iloc[0]),
        "failure_probability": probability,
        "risk": risk,
        "threshold": threshold,
        "model_name": str(metadata.get("model_name")),
        "model_version": metadata.get("model_version"),
    }
    # Feature snapshot conservé côté télémétrie pour drift/reproductibilité, non exposé
    # au client dans la réponse de l'API.
    telemetry_record = {
        **public_record,
        "dataset_manifest_sha256": metadata.get("dataset_manifest_sha256"),
        "raw_last_snapshot": rows[-1],
        "raw_history": rows,
        "feature_snapshot": {
            k: (None if pd.isna(last.iloc[0][k]) else float(last.iloc[0][k]))
            for k in features
        },
    }
    _persist_record(telemetry_record, PREDICTION_LOG_PATH, "predictions")
    PREDICTIONS.labels(risk=risk).inc()
    LATENCY.observe(time.perf_counter() - start)
    logger.info(
        "prediction_completed id=%s engine=%s cycle=%s risk=%s model=%s",
        prediction_id,
        payload.engine_id,
        public_record["last_cycle"],
        risk,
        public_record["model_version"],
    )
    return public_record
