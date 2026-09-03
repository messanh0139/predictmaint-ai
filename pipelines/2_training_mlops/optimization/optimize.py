from __future__ import annotations

import argparse
import json

import joblib
import optuna
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, cross_val_score
from xgboost import XGBClassifier

from src.config import CV_FOLDS, ID_COL, MODELS_DIR, PROCESSED_DIR, RANDOM_STATE, TARGET_COL
from src.models.common import choose_threshold, load_selected_features, metrics, xy
from src.models.pipelines import build_model_pipeline


def main(n_trials: int = 30) -> None:
    # Optimise les hyperparamètres XGBoost par recherche bayésienne (Optuna),
    train_df = pd.read_csv(PROCESSED_DIR / "train_features.csv")
    calibration_df = pd.read_csv(PROCESSED_DIR / "calibration_features.csv")
    val_df = pd.read_csv(PROCESSED_DIR / "val_features.csv")
    features = load_selected_features(MODELS_DIR / "selected_features.json")
    manifest = json.loads((PROCESSED_DIR / "split_manifest.json").read_text(encoding="utf-8"))
    X = train_df[features]
    y = train_df[TARGET_COL].astype(int)
    groups = train_df[ID_COL]

    positives = max(int(y.sum()), 1)
    negatives = max(int((1 - y).sum()), 1)
    # Ratio négatifs/positifs utilisé comme scale_pos_weight pour compenser
    # le déséquilibre de classes (pannes rares).
    class_ratio = negatives / positives
    # Groupé par moteur (ID_COL) pour qu'un même moteur ne se retrouve jamais
    # à la fois en train et en test au sein d'un pli -> évite la fuite de données.
    cv = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    def objective(trial: optuna.Trial) -> float:
        # Fonction objectif Optuna : entraîne un pipeline XGBoost avec les
        model = build_model_pipeline(
            XGBClassifier(
                # Plages de recherche resserrées autour de valeurs raisonnables
                # pour un dataset de taille modeste (évite l'overfitting Optuna).
                n_estimators=trial.suggest_int("n_estimators", 120, 400),
                max_depth=trial.suggest_int("max_depth", 3, 7),
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.18, log=True),
                subsample=trial.suggest_float("subsample", 0.65, 1.0),
                colsample_bytree=trial.suggest_float("colsample_bytree", 0.65, 1.0),
                min_child_weight=trial.suggest_float("min_child_weight", 1, 10),
                reg_alpha=trial.suggest_float("reg_alpha", 1e-4, 3.0, log=True),
                reg_lambda=trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
                scale_pos_weight=class_ratio,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=2,
            )
        )
        scores = cross_val_score(
            model,
            X,
            y,
            groups=groups,
            cv=cv,
            scoring="average_precision",
            n_jobs=1,
        )
        trial.set_user_attr("cv_std", float(scores.std()))
        return float(scores.mean())

    # TPE (Tree-structured Parzen Estimator) : sampler bayésien d'Optuna, seed
    # fixée pour reproductibilité des résultats d'optimisation.
    sampler = optuna.samplers.TPESampler(seed=RANDOM_STATE)
    study = optuna.create_study(direction="maximize", study_name="predictmaint-xgb", sampler=sampler)
    study.optimize(objective, n_trials=n_trials)

    # Réentraîne le meilleur jeu d'hyperparamètres trouvé sur tout le train
    # (les essais Optuna n'utilisaient que des sous-plis de cross-validation).
    best_model = build_model_pipeline(
        XGBClassifier(
            **study.best_params,
            scale_pos_weight=class_ratio,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=2,
        )
    )

    best_model.fit(X, y)
    X_cal, y_cal = xy(calibration_df, features)
    cal_prob = best_model.predict_proba(X_cal)[:, 1]
    # Seuil calibré sur une partition dédiée, disjointe du train et de la validation.
    threshold, calibration_metrics = choose_threshold(y_cal, cal_prob)

    X_val, y_val = xy(val_df, features)
    val_prob = best_model.predict_proba(X_val)[:, 1]
    val_metrics = metrics(y_val, val_prob, threshold)

    candidate_dir = MODELS_DIR / "candidates"
    candidate_dir.mkdir(exist_ok=True)
    candidate_path = candidate_dir / "xgboost_optimized.joblib"
    joblib.dump(best_model, candidate_path)

    # Compare le candidat optimisé au modèle xgboost par défaut du leaderboard
    # produit par train.py (référence non optimisée).
    baseline_xgb = None
    leaderboard_path = MODELS_DIR / "leaderboard.csv"
    if leaderboard_path.exists():
        lb = pd.read_csv(leaderboard_path)
        row = lb[lb["name"] == "xgboost"]
        if not row.empty:
            baseline_xgb = row.iloc[0].to_dict()

    improvement = (
        None
        if baseline_xgb is None
        else float(val_metrics["pr_auc"] - float(baseline_xgb["pr_auc"]))
    )
    business_cost_gain = (
        None
        if baseline_xgb is None
        else float(float(baseline_xgb["business_cost"]) - val_metrics["business_cost"])
    )
    # Garde contre la division par zéro si le baseline avait un coût nul.
    business_cost_gain_pct = (
        None
        if baseline_xgb is None or float(baseline_xgb["business_cost"]) == 0
        else float(business_cost_gain / float(baseline_xgb["business_cost"]))
    )
    result = {
        "best_params": study.best_params,
        "cv_pr_auc_mean": float(study.best_value),
        "cv_pr_auc_std": float(study.best_trial.user_attrs.get("cv_std", 0.0)),
        "n_trials": int(n_trials),
        "cv_folds": int(CV_FOLDS),
        "dataset_manifest_sha256": manifest.get("manifest_sha256"),
        "threshold": threshold,
        "threshold_source": "dedicated calibration engines",
        "calibration_metrics": calibration_metrics,
        "validation_metrics": val_metrics,
        "baseline_xgboost_validation": baseline_xgb,
        "pr_auc_gain_vs_default_xgboost": improvement,
        "business_cost_gain_vs_default_xgboost": business_cost_gain,
        "business_cost_gain_pct_vs_default_xgboost": business_cost_gain_pct,
        "recall_gain_vs_default_xgboost": None if baseline_xgb is None else float(val_metrics["recall"] - float(baseline_xgb["recall"])),
        "candidate_path": str(candidate_path),
        "note": "Le jeu de test externe n'est jamais consulté pendant Optuna, le choix du seuil ou la promotion.",
    }
    (MODELS_DIR / "optimization_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (candidate_dir / "xgboost_optimized_metadata.json").write_text(
        json.dumps(
            {
                "name": "xgboost_optimized",
                "dataset_manifest_sha256": manifest.get("manifest_sha256"),
                "cv_folds": int(CV_FOLDS),
                "threshold": threshold,
                "threshold_source": "dedicated calibration engines",
                "calibration_metrics": calibration_metrics,
                "validation_metrics": val_metrics,
                "selected_features": features,
                "best_params": study.best_params,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=30)
    args = parser.parse_args()
    main(args.trials)
