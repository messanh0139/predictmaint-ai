from __future__ import annotations

import json
import os
from pathlib import Path


def upload_champion_to_gcs(model_path: Path, metadata_path: Path) -> dict:
    bucket_name = os.getenv("MODEL_ARTIFACT_BUCKET")
    if not bucket_name:
        return {"status": "skipped", "reason": "MODEL_ARTIFACT_BUCKET not configured"}
    try:
        from google.cloud import storage

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        version = metadata["model_version"]
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        model_obj = f"models/{version}/model.joblib"
        metadata_obj = f"models/{version}/metadata.json"
        bucket.blob(model_obj).upload_from_filename(str(model_path))
        bucket.blob(metadata_obj).upload_from_filename(str(metadata_path))
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
        }
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "bucket": bucket_name}
