from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import ID_COL, RANDOM_STATE


def split_by_engine_three_way(
    df: pd.DataFrame,
    train_fraction: float = 0.70,
    calibration_fraction: float = 0.15,
    random_state: int = RANDOM_STATE,
):
    # Sépare les moteurs en TRAIN / CALIBRATION / VALIDATION avant transformations
    if train_fraction <= 0 or calibration_fraction <= 0 or train_fraction + calibration_fraction >= 1:
        raise ValueError("Fractions invalides")
    engines = np.array(sorted(df[ID_COL].unique()))
    rng = np.random.default_rng(random_state)
    rng.shuffle(engines)
    n = len(engines)
    n_train = int(round(n * train_fraction))
    n_cal = int(round(n * calibration_fraction))
    train_engines = set(engines[:n_train].tolist())
    cal_engines = set(engines[n_train:n_train + n_cal].tolist())
    val_engines = set(engines[n_train + n_cal:].tolist())

    def subset(ids: set[int]) -> pd.DataFrame:
        # extrait les lignes des moteurs donnés, triées par moteur puis cycle
        return (
            df[df[ID_COL].isin(ids)]
            .copy()
            .sort_values([ID_COL, "cycle"])
            .reset_index(drop=True)
        )

    train_df, cal_df, val_df = subset(train_engines), subset(cal_engines), subset(val_engines)
    overlaps = {
        "train_calibration": sorted(train_engines & cal_engines),
        "train_validation": sorted(train_engines & val_engines),
        "calibration_validation": sorted(cal_engines & val_engines),
    }
    if any(overlaps.values()):
        raise RuntimeError(f"Data leakage inter-partitions: {overlaps}")
    return train_df, cal_df, val_df


def split_by_engine(df: pd.DataFrame, validation_size: float = 0.20, random_state: int = RANDOM_STATE):
    # Compatibilité : split 2-way par moteur pour tests/expériences simples
    engines = np.array(sorted(df[ID_COL].unique()))
    rng = np.random.default_rng(random_state)
    rng.shuffle(engines)
    cut = int(round(len(engines) * (1 - validation_size)))
    a, b = set(engines[:cut]), set(engines[cut:])
    train_df = df[df[ID_COL].isin(a)].copy().sort_values([ID_COL, "cycle"]).reset_index(drop=True)
    val_df = df[df[ID_COL].isin(b)].copy().sort_values([ID_COL, "cycle"]).reset_index(drop=True)
    if a & b:
        raise RuntimeError("Data leakage: engine overlap")
    return train_df, val_df
