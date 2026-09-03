from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import ID_COL, TARGET_COL
from src.features.build_features import build_causal_features


def _read_jsonl(path: Path) -> list[dict]:
    # Lit un fichier JSON Lines (un objet JSON par ligne) ; liste vide si absent
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
    # Lit tous les objets JSON sous un préfixe d'un bucket GCS
    # Import local : évite de rendre google-cloud-storage obligatoire quand on
    # travaille en local avec --predictions/--feedback.
    from google.cloud import storage

    client = storage.Client()
    rows = []
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if blob.name.endswith(".json"):
            rows.append(json.loads(blob.download_as_text()))
    return rows


def build_feedback_feature_dataset(predictions: list[dict], feedback: list[dict]) -> pd.DataFrame:
    # Associe chaque prédiction à son feedback (vérité terrain) pour créer des lignes de retraining
    feedback_by_id = {x["prediction_id"]: x for x in feedback if x.get("prediction_id")}
    rows = []
    for pred in predictions:
        fb = feedback_by_id.get(pred.get("prediction_id"))
        history = pred.get("raw_history")
        if not fb or not history:
            continue
        # Décalage d'ID pour éviter tout chevauchement avec les moteurs du dataset.
        production_engine_id = 1_000_000 + int(pred["engine_id"])
        raw = pd.DataFrame(
            [{ID_COL: production_engine_id, **snap} for snap in history]
        )
        # Dernière ligne = état des features au moment où la prédiction a été faite.
        feat = build_causal_features(raw).iloc[[-1]].copy()
        feat[TARGET_COL] = int(fb["actual_failure_within_30_cycles"])
        feat["source_prediction_id"] = pred["prediction_id"]
        rows.append(feat)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    # Une seule vérité terrain par moteur/cycle dans le lot de retraining.
    return out.drop_duplicates([ID_COL, "cycle"], keep="last").reset_index(drop=True)


UPLOAD_ENGINE_ID_OFFSET = 5_000_000


def build_uploaded_feature_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    # Construit des features causales à partir d'un lot de données labellisées téléversé
    required = {ID_COL, "cycle", "actual_failure_within_30_cycles"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes: {sorted(missing)}")

    raw = raw.copy()
    # Décalage d'ID dédié pour ne chevaucher ni les moteurs du dataset ni les IDs de la boucle
    # de feedback par prédiction (offset 1_000_000).
    raw[ID_COL] = UPLOAD_ENGINE_ID_OFFSET + raw[ID_COL].astype(int)
    labels = raw.groupby(ID_COL)["actual_failure_within_30_cycles"].last()

    feat = build_causal_features(raw.drop(columns=["actual_failure_within_30_cycles"]))
    last_rows = feat.groupby(ID_COL, sort=False).tail(1).copy()
    last_rows[TARGET_COL] = last_rows[ID_COL].map(labels).astype(int)
    return last_rows.reset_index(drop=True)


def append_feature_dataset(new_rows: pd.DataFrame, output: Path) -> int:
    # Fusionne de nouvelles lignes labellisées dans le jeu de features de production
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = pd.read_csv(output)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    combined = combined.drop_duplicates([ID_COL, "cycle"], keep="last").reset_index(drop=True)
    combined.to_csv(output, index=False)
    return int(len(new_rows))


def main() -> None:
    # CLI : construit le dataset de retraining à partir de fichiers locaux ou d'un bucket GCS
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
    if dataset.empty:
        # Rien de nouveau à fusionner : ne pas écraser un fichier existant (ex. données
        # déposées via /retrain/upload) avec un CSV vide et invalide pour pandas.
        print(json.dumps({"rows": 0, "output": None, "note": "no new labelled feedback"}, indent=2))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)
    print(json.dumps({"rows": int(len(dataset)), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
