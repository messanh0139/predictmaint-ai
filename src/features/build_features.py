from __future__ import annotations

# Construction des features d'ingénierie pour la maintenance prédictive :
# uniquement des transformations causales (lags, fenêtres glissantes, EWM) par moteur.
import numpy as np
import pandas as pd

from src.config import (
    FORBIDDEN_MODEL_COLUMNS,
    ID_COL,
    ROLLING_SENSORS,
    ROLLING_WINDOWS,
    TIME_COL,
)


def build_causal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construit des features temporelles strictement causales, moteur par moteur.

    Une feature à l'instant t ne dépend que des observations du même moteur dont le
    cycle est <= t. Aucune fenêtre centrée, aucun shift négatif et aucune agrégation
    inter-moteurs ne sont autorisés.
    """
    out = df.copy().sort_values([ID_COL, TIME_COL]).reset_index(drop=True)
    engineered: dict[str, pd.Series] = {}

    for sensor in ROLLING_SENSORS:
        grouped = out.groupby(ID_COL, sort=False)[sensor]
        engineered[f"{sensor}_lag_1"] = grouped.shift(1)
        engineered[f"{sensor}_lag_3"] = grouped.shift(3)
        engineered[f"{sensor}_diff_1"] = grouped.diff(1)

        for w in ROLLING_WINDOWS:
            rolling = grouped.rolling(w, min_periods=1)
            # reset_index permet de réaligner la série sur l'index original.
            mean = rolling.mean().reset_index(level=0, drop=True).sort_index()
            min_ = rolling.min().reset_index(level=0, drop=True).sort_index()
            max_ = rolling.max().reset_index(level=0, drop=True).sort_index()
            std = grouped.rolling(w, min_periods=2).std().reset_index(level=0, drop=True).sort_index()
            engineered[f"{sensor}_mean_{w}"] = mean
            engineered[f"{sensor}_std_{w}"] = std
            engineered[f"{sensor}_min_{w}"] = min_
            engineered[f"{sensor}_max_{w}"] = max_
            engineered[f"{sensor}_range_{w}"] = max_ - min_
            engineered[f"{sensor}_dev_mean_{w}"] = out[sensor] - mean

        # EWM est également causal : il ne voit que l'historique jusqu'à t.
        engineered[f"{sensor}_ewm_10"] = grouped.transform(
            lambda s: s.ewm(span=10, adjust=False).mean()
        )

    engineered["cycle_sqrt"] = np.sqrt(out[TIME_COL].clip(lower=0))
    engineered["cycle_log1p"] = np.log1p(out[TIME_COL].clip(lower=0))

    result = pd.concat([out, pd.DataFrame(engineered, index=out.index)], axis=1)
    return result


def candidate_feature_columns(df: pd.DataFrame) -> list[str]:
    """Liste les colonnes utilisables par le modèle (exclut ID, cible et colonnes de fuite)."""
    return [c for c in df.columns if c not in FORBIDDEN_MODEL_COLUMNS]
