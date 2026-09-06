from __future__ import annotations

from sklearn.base import BaseEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_model_pipeline(
    estimator: BaseEstimator,
    *,
    scale_features: bool = False,
) -> Pipeline:
    # Pipeline de prétraitement commun à tous les modèles candidats
    steps: list[tuple[str, BaseEstimator]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    # Standardisation optionnelle : nécessaire pour les modèles linéaires,
    # inutile (et sans effet) pour les modèles à base d'arbres.
    if scale_features:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)
