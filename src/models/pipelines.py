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
    """Build the preprocessing pipeline shared by all model candidates.

    Imputation is always fitted as part of the pipeline to prevent leakage.
    Scaling is opt-in because linear models need it while tree models do not.
    """
    steps: list[tuple[str, BaseEstimator]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    # Standardisation optionnelle : nécessaire pour les modèles linéaires,
    # inutile (et sans effet) pour les modèles à base d'arbres.
    if scale_features:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)
