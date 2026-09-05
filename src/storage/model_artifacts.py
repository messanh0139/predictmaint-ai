from __future__ import annotations

import json
import os
from pathlib import Path

from src.models.common import validation_sort_key


def _current_gcs_champion_metrics(bucket) -> dict | None:
    # Récupère les métriques du champion pointé par champion.json, ou None si absent
    pointer_blob = bucket.blob("models/champion.json")
    if not pointer_blob.exists():
        return None
    try:
        pointer = json.loads(pointer_blob.download_as_text())
        metadata = json.loads(bucket.blob(pointer["metadata_object"]).download_as_text())
        return metadata.get("validation_metrics")
    except Exception:
        # pointeur cassé ou fichier manquant -> on considère qu'il n'y a pas de champion
        return None


def upload_champion_to_gcs(model_path: Path, metadata_path: Path) -> dict:
    # Envoie le modèle sur GCS (toujours), et ne déplace le pointeur champion.json
    # que si ce modèle est vraiment meilleur que l'actuel (sinon on garde l'ancien)
    bucket_name = os.getenv("MODEL_ARTIFACT_BUCKET")
    if not bucket_name:
        # pas de bucket configuré (dev local, CI) -> on n'upload rien
        return {"status": "skipped", "reason": "MODEL_ARTIFACT_BUCKET not configured"}
    try:
        from google.cloud import storage

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        version = metadata["model_version"]
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        # Chemins versionnés : un dossier dédié par version de modèle, jamais écrasé.
        model_obj = f"models/{version}/model.joblib"
        metadata_obj = f"models/{version}/metadata.json"
        bucket.blob(model_obj).upload_from_filename(str(model_path))
        bucket.blob(metadata_obj).upload_from_filename(str(metadata_path))

        # test_metrics.json n'existe pas toujours, on l'envoie si présent
        test_metrics_path = model_path.parent / "test_metrics.json"
        if test_metrics_path.exists():
            bucket.blob("models/test_metrics.json").upload_from_filename(str(test_metrics_path))

        current_champion_metrics = _current_gcs_champion_metrics(bucket)
        promotes_global_champion = (
            current_champion_metrics is None
            or validation_sort_key(metadata["validation_metrics"]) < validation_sort_key(current_champion_metrics)
        )
        if promotes_global_champion:
            # champion.json n'est pas versionné, on l'écrase directement
            bucket.blob("models/champion.json").upload_from_string(
                json.dumps(
                    {
                        "model_version": version,
                        "model_name": metadata["model_name"],
                        "model_object": model_obj,
                        "metadata_object": metadata_obj,
                    },
                    ensure_ascii=False,
                ),
                content_type="application/json",
            )
        return {
            "status": "uploaded",
            "bucket": bucket_name,
            "model_object": model_obj,
            "metadata_object": metadata_obj,
            "global_champion_updated": promotes_global_champion,
        }
    except Exception as exc:
        # on ne casse jamais le pipeline pour un souci d'upload, on renvoie juste l'erreur
        return {"status": "failed", "reason": str(exc), "bucket": bucket_name}
