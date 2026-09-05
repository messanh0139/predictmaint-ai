from __future__ import annotations

import json
import os
from pathlib import Path

from src.models.common import validation_sort_key


def _current_gcs_champion_metrics(bucket) -> dict | None:
    # Lit les validation_metrics du champion actuellement pointé par champion.json
    # sur GCS, ou None si absent/illisible (premier déploiement, ex.).
    pointer_blob = bucket.blob("models/champion.json")
    if not pointer_blob.exists():
        return None
    try:
        pointer = json.loads(pointer_blob.download_as_text())
        metadata = json.loads(bucket.blob(pointer["metadata_object"]).download_as_text())
        return metadata.get("validation_metrics")
    except Exception:
        # Pointeur corrompu ou artefact manquant : on ne bloque pas l'upload versionné,
        # mais on ne peut pas garantir la non-régression -> traité comme "pas de champion".
        return None


def upload_champion_to_gcs(model_path: Path, metadata_path: Path) -> dict:
    # Publie le modèle (artefact + métadonnées) sur GCS, toujours sous un chemin
    # versionné. Ne déplace le pointeur global champion.json que si ce modèle est
    # réellement meilleur que le champion GCS actuel (même règle que promote.py) :
    # une exécution qui ne bat pas sa propre baseline ne doit jamais écraser un
    # champion plus ancien mais meilleur.
    bucket_name = os.getenv("MODEL_ARTIFACT_BUCKET")
    if not bucket_name:
        # Upload désactivé si le bucket n'est pas configuré (ex : environnement local/CI sans cloud).
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

        # Upload optionnel de test_metrics.json s'il existe
        test_metrics_path = model_path.parent / "test_metrics.json"
        if test_metrics_path.exists():
            bucket.blob("models/test_metrics.json").upload_from_filename(str(test_metrics_path))

        current_champion_metrics = _current_gcs_champion_metrics(bucket)
        promotes_global_champion = (
            current_champion_metrics is None
            or validation_sort_key(metadata["validation_metrics"]) < validation_sort_key(current_champion_metrics)
        )
        if promotes_global_champion:
            # Pointeur global vers le dernier modèle validé : toujours écrasé (ce n'est pas un artefact versionné).
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
        # On ne fait jamais échouer le pipeline pour un problème d'upload d'artefact :
        # l'échec est renvoyé dans le statut plutôt que propagé.
        return {"status": "failed", "reason": str(exc), "bucket": bucket_name}
