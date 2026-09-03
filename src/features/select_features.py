from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import MODELS_DIR, PROCESSED_DIR, RANDOM_STATE, TARGET_COL
from src.features.build_features import candidate_feature_columns


def _normalize(s: pd.Series) -> pd.Series:
    # Ramène un score sur [0, 1] (division par le max) pour rendre comparables des méthodes hétérogènes
    s = s.astype(float).abs()
    m = float(s.max()) if len(s) else 0.0
    return s / m if m > 0 else s * 0.0


def select_features(
    train_df: pd.DataFrame,
    max_features: int = 40,
    corr_threshold: float = 0.98,
):
    # Sélection de variables ajustée exclusivement sur TRAIN
    features = candidate_feature_columns(train_df)
    X = train_df[features].replace([np.inf, -np.inf], np.nan)
    y = train_df[TARGET_COL].astype(int)

    # 1) Variance nulle / constante.
    nunique = X.nunique(dropna=False)
    non_constant = nunique[nunique > 1].index.tolist()
    X = X[non_constant]

    # 2) Corrélation : réduction des variables quasi redondantes sur TRAIN seulement.
    corr = X.corr(numeric_only=True).abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop_corr = [column for column in upper.columns if (upper[column] > corr_threshold).any()]
    X_reduced = X.drop(columns=to_drop_corr)

    imputer = SimpleImputer(strategy="median")
    X_imp = pd.DataFrame(
        imputer.fit_transform(X_reduced), columns=X_reduced.columns, index=X_reduced.index
    )

    # 3) Information mutuelle : dépendances potentiellement non linéaires.
    mi_s = pd.Series(
        mutual_info_classif(X_imp, y, random_state=RANDOM_STATE),
        index=X_imp.columns,
        name="mutual_information",
    )

    # 4) Méthode incorporée par modèle d'arbres.
    rf = RandomForestClassifier(
        n_estimators=160,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight="balanced_subsample",
        min_samples_leaf=2,
    )
    rf.fit(X_imp, y)
    rf_s = pd.Series(rf.feature_importances_, index=X_imp.columns, name="rf_importance")

    # 5) L1 : sélection parcimonieuse, après imputation et standardisation.
    l1 = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l1",
                    alpha=0.001,
                    class_weight="balanced",
                    max_iter=1500,
                    tol=1e-3,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    l1.fit(X_reduced, y)
    l1_coef = pd.Series(
        np.abs(l1.named_steps["model"].coef_[0]),
        index=X_reduced.columns,
        name="l1_abs_coef",
    )

    report = pd.concat([mi_s, rf_s, l1_coef], axis=1).fillna(0.0)
    report["mi_norm"] = _normalize(report["mutual_information"])
    report["rf_norm"] = _normalize(report["rf_importance"])
    report["l1_norm"] = _normalize(report["l1_abs_coef"])
    # Pondération équilibrée : aucune méthode ne décide seule.
    report["consensus_score"] = report[["mi_norm", "rf_norm", "l1_norm"]].mean(axis=1)
    report["selected_by_l1"] = report["l1_abs_coef"] > 0
    report = report.sort_values(
        ["consensus_score", "mutual_information"], ascending=[False, False]
    )

    selected = report.head(min(max_features, len(report))).index.tolist()
    removals = {
        "constant_removed": sorted(set(features) - set(non_constant)),
        "correlated_removed": to_drop_corr,
        "corr_threshold": corr_threshold,
        "selection_fit_scope": "TRAIN only",
        "methods": ["variance", "correlation", "mutual_information", "random_forest", "l1"],
    }
    return selected, report, removals


def main() -> None:
    # Point d'entrée CLI : lance la sélection sur le train et écrit rapport + variables retenues sur disque
    MODELS_DIR.mkdir(exist_ok=True)
    train = pd.read_csv(PROCESSED_DIR / "train_features.csv")
    selected, report, removals = select_features(train)
    report.to_csv(MODELS_DIR / "feature_selection_report.csv", index_label="feature")
    (MODELS_DIR / "selected_features.json").write_text(
        json.dumps(selected, indent=2), encoding="utf-8"
    )
    (MODELS_DIR / "feature_selection_removals.json").write_text(
        json.dumps(removals, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{len(selected)} variables sélectionnées sur TRAIN uniquement")


if __name__ == "__main__":
    main()
