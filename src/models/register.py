from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import joblib

from src.config import MODELS_DIR
from src.storage.model_artifacts import upload_champion_to_gcs
from src.utils.fingerprints import sha256_file


def register_local_model(
    model_path: Path,
    metadata_path: Path,
    registry_dir: Path,
) -> dict:
    """Copie le modèle et ses métadonnées dans le registre local versionné
    (un sous-dossier par version) et met à jour l'index du registre."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = metadata["model_version"]
    target_dir = registry_dir / version
    target_dir.mkdir(parents=True, exist_ok=True)
    target_model = target_dir / "model.joblib"
    target_metadata = target_dir / "metadata.json"
    shutil.copy2(model_path, target_model)
    shutil.copy2(metadata_path, target_metadata)

    # Chemin affiché relatif à la racine du projet si possible, sinon relatif
    # au registre lui-même (cas où registry_dir est hors de MODELS_DIR.parent).
    try:
        artifact_display = str(target_model.relative_to(MODELS_DIR.parent))
        metadata_display = str(target_metadata.relative_to(MODELS_DIR.parent))
    except ValueError:
        artifact_display = str(target_model.relative_to(registry_dir.parent))
        metadata_display = str(target_metadata.relative_to(registry_dir.parent))

    entry = {
        "version": version,
        "model_name": metadata["model_name"],
        "model_sha256": sha256_file(target_model),
        "dataset_manifest_sha256": metadata.get("dataset_manifest_sha256"),
        "validation_metrics": metadata.get("validation_metrics"),
        "artifact": artifact_display,
        "metadata": metadata_display,
    }
    index_path = registry_dir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"champion": None, "versions": []}
    # Remplace une éventuelle entrée existante pour cette version avant de la rajouter,
    # puis désigne cette version comme le champion courant.
    index["versions"] = [x for x in index.get("versions", []) if x.get("version") != version]
    index["versions"].append(entry)
    index["champion"] = version
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def register_mlflow(model_path: Path, metadata_path: Path) -> dict:
    """Enregistre le champion dans MLflow si la dépendance est disponible.

    Le registre local reste la source de secours reproductible. En équipe, définir
    MLFLOW_TRACKING_URI vers un backend persistant.
    """
    try:
        import mlflow
        import mlflow.sklearn
    except Exception as exc:
        return {"status": "skipped", "reason": f"mlflow unavailable: {exc}"}

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    model_registry_name = os.getenv("MLFLOW_MODEL_NAME", "predictmaint-fd001")
    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("predictmaint-fd001")
        model = joblib.load(model_path)
        with mlflow.start_run(run_name=f"register-{metadata['model_version']}") as run:
            mlflow.log_params(
                {
                    "model_name": metadata["model_name"],
                    "model_version": metadata["model_version"],
                    "dataset_manifest_sha256": metadata.get("dataset_manifest_sha256", ""),
                }
            )
            for key, value in metadata.get("validation_metrics", {}).items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(f"validation_{key}", value)
            mlflow.sklearn.log_model(model, name="model")
            model_uri = f"runs:/{run.info.run_id}/model"
            mv = mlflow.register_model(model_uri=model_uri, name=model_registry_name)
        return {
            "status": "registered",
            "tracking_uri": tracking_uri,
            "registry_name": model_registry_name,
            "registered_version": str(mv.version),
            "run_id": run.info.run_id,
        }
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "tracking_uri": tracking_uri}


def main() -> None:
    """Enregistre le modèle champion dans le registre local, MLflow (optionnel)
    et GCS (le bucket, s'il est configuré, devient une exigence obligatoire)."""
    model_path = MODELS_DIR / "model.joblib"
    metadata_path = MODELS_DIR / "model_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Champion artifacts missing")
    local = register_local_model(model_path, metadata_path, MODELS_DIR / "registry")
    mlflow_status = register_mlflow(model_path, metadata_path)
    gcs_status = upload_champion_to_gcs(model_path, metadata_path)
    status = {"local_registry": local, "mlflow_registry": mlflow_status, "gcs_artifact_store": gcs_status}
    # Si un bucket GCS est configuré, l'upload y est obligatoire : on échoue
    # explicitement plutôt que de laisser passer un enregistrement incomplet.
    if os.getenv("MODEL_ARTIFACT_BUCKET") and gcs_status.get("status") != "uploaded":
        raise RuntimeError(f"Persistent GCS model registration failed: {gcs_status}")
    (MODELS_DIR / "registry_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
