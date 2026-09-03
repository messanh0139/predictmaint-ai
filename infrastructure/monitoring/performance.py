from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import MIN_PR_AUC, MIN_RECALL
from src.models.common import metrics_from_predictions


def load_jsonl(path: str | Path) -> pd.DataFrame:
    """Charge un fichier JSON Lines (log de prédictions ou de feedback) en DataFrame."""
    rows = []
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def _version_report(group: pd.DataFrame) -> dict:
    """Calcule les métriques de performance pour un sous-ensemble de prédictions d'une même version de modèle."""
    labelled = int(len(group))
    if labelled < 20 or group["actual_failure_within_30_cycles"].nunique() < 2:
        return {
            "labelled_predictions": labelled,
            "status": "insufficient_ground_truth",
            "threshold_policy": "per_prediction_versioned_threshold",
        }

    y = group["actual_failure_within_30_cycles"].astype(int)
    prob = group["failure_probability"].astype(float)
    pred = (prob >= group["threshold"].astype(float)).astype(int)
    report = metrics_from_predictions(y, prob, pred)
    report.update(
        {
            "labelled_predictions": labelled,
            "status": (
                "alert"
                if (report["recall"] < MIN_RECALL or report["pr_auc"] < MIN_PR_AUC)
                else "ok"
            ),
            "threshold_policy": "per_prediction_versioned_threshold",
            "threshold_min": float(group["threshold"].min()),
            "threshold_max": float(group["threshold"].max()),
        }
    )
    return report


def performance_report(predictions_path: str | Path, feedback_path: str | Path) -> dict:
    """Rapproche les prédictions historiques du feedback terrain (label réel) et calcule les métriques
    de performance globales ainsi qu'une ventilation par version de modèle."""
    pred = load_jsonl(predictions_path)
    fb = load_jsonl(feedback_path)
    if pred.empty or fb.empty:
        return {"labelled_predictions": 0, "status": "insufficient_ground_truth"}

    # Contrat minimal attendu du log de prédictions, nécessaire pour recalculer la décision historique.
    required_prediction_columns = {
        "prediction_id",
        "failure_probability",
        "threshold",
        "model_version",
    }
    missing = sorted(required_prediction_columns - set(pred.columns))
    if missing:
        return {
            "labelled_predictions": 0,
            "status": "invalid_prediction_contract",
            "missing_columns": missing,
        }

    merged = pred.merge(
        fb[["prediction_id", "actual_failure_within_30_cycles"]],
        on="prediction_id",
        how="inner",
    )
    # Une seule ligne par prédiction : on garde la dernière en cas de doublon de feedback.
    merged = merged.drop_duplicates(subset=["prediction_id"], keep="last")
    if len(merged) < 20 or merged["actual_failure_within_30_cycles"].nunique() < 2:
        return {"labelled_predictions": int(len(merged)), "status": "insufficient_ground_truth"}

    # La décision historique doit être reconstruite avec le seuil réellement utilisé
    # lors de chaque prédiction. Une médiane de seuils fausserait un lot multi-version.
    y = merged["actual_failure_within_30_cycles"].astype(int)
    prob = merged["failure_probability"].astype(float)
    pred_binary = (prob >= merged["threshold"].astype(float)).astype(int)
    report = metrics_from_predictions(y, prob, pred_binary)
    report.update(
        {
            "labelled_predictions": int(len(merged)),
            "threshold_policy": "per_prediction_versioned_threshold",
            "status": (
                "alert"
                if (report["recall"] < MIN_RECALL or report["pr_auc"] < MIN_PR_AUC)
                else "ok"
            ),
            "alerts": {
                "recall_below_guardrail": report["recall"] < MIN_RECALL,
                "pr_auc_below_guardrail": report["pr_auc"] < MIN_PR_AUC,
            },
        }
    )

    per_version = {}
    for version, group in merged.groupby("model_version", dropna=False):
        key = "unknown" if pd.isna(version) else str(version)
        per_version[key] = _version_report(group)
    report["per_model_version"] = per_version
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("predictions_jsonl")
    p.add_argument("feedback_jsonl")
    args = p.parse_args()
    print(json.dumps(performance_report(args.predictions_jsonl, args.feedback_jsonl), indent=2))
