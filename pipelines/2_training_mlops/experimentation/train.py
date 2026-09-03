from __future__ import annotations

import json
import os
import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import (
    FAILURE_WINDOW,
    ID_COL,
    MODELS_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
)
from src.models.common import (
    choose_threshold,
    load_selected_features,
    metrics,
    validation_sort_key,
    xy,
)
from src.models.pipelines import build_model_pipeline
from src.utils.fingerprints import runtime_metadata

try:
    import mlflow
    import mlflow.sklearn

    MLFLOW_AVAILABLE = True
except Exception:
    mlflow = None
    MLFLOW_AVAILABLE = False


def build_candidates(y_train: pd.Series) -> dict[str, Pipeline]:
    # Construit les pipelines candidats à comparer (régression logistique, forêt
    positives = max(int(y_train.sum()), 1)
    negatives = max(int((1 - y_train).sum()), 1)
    # Ratio négatifs/positifs, repris comme scale_pos_weight pour XGBoost.
    scale_pos_weight = negatives / positives

    candidates: dict[str, Pipeline] = {
        "logistic_regression": build_model_pipeline(
            LogisticRegression(
                max_iter=2500,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            ),
            scale_features=True,
        ),
        "random_forest": build_model_pipeline(
            RandomForestClassifier(
                n_estimators=180,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        ),
    }
    try:
        from xgboost import XGBClassifier

        # Hyperparamètres par défaut raisonnables (non optimisés) : le tuning fin
        # se fait séparément dans optimize.py via Optuna.
        candidates["xgboost"] = build_model_pipeline(
            XGBClassifier(
                n_estimators=180,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                min_child_weight=2,
                scale_pos_weight=scale_pos_weight,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        )
    except Exception as exc:
        print(f"XGBoost indisponible, ignoré: {exc}")
    return candidates


def _start_mlflow() -> None:
    # Configure le tracking MLflow si la librairie est installée (no-op sinon)
    if not MLFLOW_AVAILABLE:
        print("MLflow non installé: exécution sans tracking. requirements.txt l'active.")
        return
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("predictmaint-fd001")


def main() -> None:
    # Entraîne tous les modèles candidats, calibre leur seuil, sélectionne le
    MODELS_DIR.mkdir(exist_ok=True)
    candidates_dir = MODELS_DIR / "candidates"
    candidates_dir.mkdir(exist_ok=True)

    train_df = pd.read_csv(PROCESSED_DIR / "train_features.csv")
    calibration_df = pd.read_csv(PROCESSED_DIR / "calibration_features.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val_features.csv")
    features = load_selected_features(MODELS_DIR / "selected_features.json")
    X_train, y_train = xy(train_df, features)
    X_cal, y_cal = xy(calibration_df, features)
    X_val, y_val = xy(val_df, features)
    _start_mlflow()

    leaderboard: list[dict] = []
    val_predictions = pd.DataFrame(
        {"engine_id": val_df[ID_COL].astype(int), "y_true": y_val.to_numpy()}
    )

    best: dict | None = None
    for name, base_model in build_candidates(y_train).items():
        model = clone(base_model).fit(X_train, y_train)
        # Seuil choisi uniquement sur des moteurs de calibration jamais vus au fit.
        cal_prob = model.predict_proba(X_cal)[:, 1]
        threshold, calibration_metrics = choose_threshold(y_cal, cal_prob)
        val_prob = model.predict_proba(X_val)[:, 1]
        val_metrics = metrics(y_val, val_prob, threshold)
        row = {
            "name": name,
            "threshold_source": "dedicated calibration engines",
            "calibration_pr_auc": calibration_metrics["pr_auc"],
            "calibration_recall": calibration_metrics["recall"],
            **val_metrics,
        }
        leaderboard.append(row)
        val_predictions[f"prob_{name}"] = val_prob
        joblib.dump(model, candidates_dir / f"{name}.joblib")
        (candidates_dir / f"{name}_metadata.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "threshold": threshold,
                    "threshold_source": "dedicated calibration engines",
                    "calibration_metrics": calibration_metrics,
                    "validation_metrics": val_metrics,
                    "selected_features": features,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        if MLFLOW_AVAILABLE:
            try:
                with mlflow.start_run(run_name=name):
                    mlflow.log_params(
                        {
                            "model_name": name,
                            "n_features": len(features),
                            "threshold_source": "dedicated_calibration",
                        }
                    )
                    mlflow.log_metrics(
                        {
                            f"val_{k}": v
                            for k, v in val_metrics.items()
                            if isinstance(v, (int, float))
                        }
                    )
                    mlflow.log_metrics(
                        {
                            "calibration_pr_auc": calibration_metrics["pr_auc"],
                            "calibration_recall": calibration_metrics["recall"],
                        }
                    )
                    mlflow.log_dict(
                        {"selected_features": features, "threshold": threshold},
                        "model_contract.json",
                    )
                    mlflow.sklearn.log_model(model, name="model")
            except Exception as exc:
                print(f"MLflow tracking warning ({name}): {exc}")

        # Sélectionne le meilleur candidat selon le même critère de tri que la
        # promotion : garde-fou recall -> coût métier -> PR-AUC -> Brier.
        if best is None or validation_sort_key(row) < validation_sort_key(best["row"]):
            best = {"row": row, "model": model, "threshold": threshold}

    assert best is not None
    lb = pd.DataFrame(leaderboard).sort_values(
        by=["business_cost_per_1000", "pr_auc"], ascending=[True, False]
    )
    lb.to_csv(MODELS_DIR / "leaderboard.csv", index=False)
    val_predictions.to_csv(MODELS_DIR / "validation_predictions.csv", index=False)

    joblib.dump(best["model"], MODELS_DIR / "model.joblib")
    split_manifest = json.loads(
        (PROCESSED_DIR / "split_manifest.json").read_text(encoding="utf-8")
    )
    runtime = runtime_metadata()
    # Version = sha git court si disponible, sinon fallback sur le hash du dataset.
    version_token = runtime["git_sha"][:12] if runtime["git_sha"] != "unknown" else split_manifest["manifest_sha256"][:12]
    metadata = {
        **runtime,
        "model_version": f"baseline-{version_token}",
        "model_name": best["row"]["name"],
        "threshold": best["threshold"],
        "threshold_source": "dedicated calibration engines, disjoint from train and validation",
        "selected_features": features,
        "validation_metrics": best["row"],
        "failure_window": FAILURE_WINDOW,
        "dataset": "FD001",
        "dataset_manifest_sha256": split_manifest["manifest_sha256"],
        "raw_sha256": split_manifest["raw_sha256"],
        "anti_leakage": [
            "engine-level train/calibration/validation split",
            "causal per-engine feature engineering",
            "feature selection fit on train only",
            "imputer/scaler fit inside train pipelines",
            "threshold fit on dedicated calibration engines, not validation",
            "external test dataset excluded from model development",
        ],
    }
    (MODELS_DIR / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
