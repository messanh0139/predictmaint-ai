from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.config import (
    FALSE_NEGATIVE_COST,
    FALSE_POSITIVE_COST,
    MIN_RECALL,
    TARGET_COL,
)


def load_selected_features(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))


def xy(df: pd.DataFrame, features: list[str]):
    return df[features], df[TARGET_COL].astype(int)


def _classification_metrics(y_true, prob, pred) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    prob = np.asarray(prob, dtype=float)
    pred = np.asarray(pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    cost = fn * FALSE_NEGATIVE_COST + fp * FALSE_POSITIVE_COST
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "specificity": float(specificity),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_true, pred)),
        "roc_auc": float(roc_auc_score(y_true, prob)),
        # Average precision est la métrique de référence pour le déséquilibre de classes.
        "pr_auc": float(average_precision_score(y_true, prob)),
        "brier": float(brier_score_loss(y_true, prob)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "business_cost": float(cost),
        "business_cost_per_1000": float(cost / max(len(y_true), 1) * 1000),
    }


def metrics(y_true, prob, threshold: float = 0.5) -> dict:
    prob = np.asarray(prob, dtype=float)
    pred = (prob >= threshold).astype(int)
    return {
        "threshold": float(threshold),
        **_classification_metrics(y_true, prob, pred),
    }


def metrics_from_predictions(y_true, prob, pred) -> dict:
    """Calcule les métriques quand la décision binaire est déjà versionnée par ligne.

    Utile en monitoring lorsque plusieurs versions du modèle coexistent et que chaque
    prédiction a été produite avec son propre seuil de décision. On ne remplace jamais
    ces seuils historiques par une médiane ou un seuil courant.
    """
    return _classification_metrics(y_true, prob, pred)


def choose_threshold(y_true, prob, min_recall: float = MIN_RECALL) -> tuple[float, dict]:
    """Choisit un seuil sur la partition de calibration sans coût quadratique.

    Les métriques indépendantes du seuil (ROC-AUC/AP) ne sont calculées qu'une fois
    après sélection. Les candidats sont un maillage régulier + quantiles des scores.
    """
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(prob, dtype=float)
    quantiles = np.quantile(p, np.linspace(0.0, 1.0, 101))
    candidates = np.unique(np.clip(np.r_[np.linspace(0.01, 0.99, 99), quantiles], 0.0, 1.0))
    scored = []
    for t in candidates:
        pred = (p >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        cost = fn * FALSE_NEGATIVE_COST + fp * FALSE_POSITIVE_COST
        scored.append((float(t), recall, f1, float(cost)))
    feasible = [x for x in scored if x[1] >= min_recall]
    pool = feasible if feasible else scored
    best_t, _, _, _ = min(pool, key=lambda x: (x[3], -x[1], -x[2]))
    return float(best_t), metrics(y, p, float(best_t))


def validation_sort_key(row: dict) -> tuple:
    """Ordre de promotion : respect du recall, coût, PR-AUC, calibration."""
    recall_penalty = 0 if row["recall"] >= MIN_RECALL else 1
    return (
        recall_penalty,
        row["business_cost_per_1000"],
        -row["pr_auc"],
        row["brier"],
    )
