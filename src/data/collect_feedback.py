from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import ID_COL, TARGET_COL
from src.features.build_features import build_causal_features


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_gcs_prefix(bucket_name: str, prefix: str) -> list[dict]:
    from google.cloud import storage

    client = storage.Client()
    rows = []
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if blob.name.endswith(".json"):
            rows.append(json.loads(blob.download_as_text()))
    return rows


def build_feedback_feature_dataset(predictions: list[dict], feedback: list[dict]) -> pd.DataFrame:
    feedback_by_id = {x["prediction_id"]: x for x in feedback if x.get("prediction_id")}
    rows = []
    for pred in predictions:
        fb = feedback_by_id.get(pred.get("prediction_id"))
        history = pred.get("raw_history")
        if not fb or not history:
            continue
        # Décalage d'ID pour éviter tout chevauchement avec les moteurs NASA.
        production_engine_id = 1_000_000 + int(pred["engine_id"])
        raw = pd.DataFrame(
            [{ID_COL: production_engine_id, **snap} for snap in history]
        )
        feat = build_causal_features(raw).iloc[[-1]].copy()
        feat[TARGET_COL] = int(fb["actual_failure_within_30_cycles"])
        feat["source_prediction_id"] = pred["prediction_id"]
        rows.append(feat)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    # Une seule vérité terrain par moteur/cycle dans le lot de retraining.
    return out.drop_duplicates([ID_COL, "cycle"], keep="last").reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", type=Path)
    p.add_argument("--feedback", type=Path)
    p.add_argument("--bucket")
    p.add_argument("--output", type=Path, default=Path("data/production/feedback_features.csv"))
    args = p.parse_args()

    if args.bucket:
        predictions = _read_gcs_prefix(args.bucket, "predictions/")
        feedback = _read_gcs_prefix(args.bucket, "feedback/")
    elif args.predictions and args.feedback:
        predictions = _read_jsonl(args.predictions)
        feedback = _read_jsonl(args.feedback)
    else:
        raise SystemExit("Provide --bucket or both --predictions and --feedback")

    dataset = build_feedback_feature_dataset(predictions, feedback)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)
    print(json.dumps({"rows": int(len(dataset)), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
