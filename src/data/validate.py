from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import BASE_COLUMNS, ID_COL, TIME_COL


def validate_raw(df: pd.DataFrame) -> dict:
    """Valide les invariants structurels du dataset brut.

    Cette validation ne corrige pas silencieusement les données. Elle échoue si un
    invariant important est violé afin d'éviter qu'un pipeline poursuive avec des
    données incohérentes.
    """
    missing_cols = sorted(set(BASE_COLUMNS) - set(df.columns))
    extra_cols = sorted(set(df.columns) - set(BASE_COLUMNS))
    duplicated_keys = int(df.duplicated([ID_COL, TIME_COL]).sum()) if not missing_cols else -1
    nulls = int(df[BASE_COLUMNS].isna().sum().sum()) if not missing_cols else -1

    numeric_non_finite = 0
    non_monotonic = 0
    invalid_ids = 0
    invalid_cycles = 0
    if not missing_cols:
        numeric = df[BASE_COLUMNS].select_dtypes(include=[np.number])
        numeric_non_finite = int((~np.isfinite(numeric.to_numpy())).sum())
        invalid_ids = int((df[ID_COL] < 1).sum())
        invalid_cycles = int((df[TIME_COL] < 1).sum())
        for _, g in df.groupby(ID_COL, sort=False):
            if not g[TIME_COL].is_monotonic_increasing:
                non_monotonic += 1

    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "engines": int(df[ID_COL].nunique()) if ID_COL in df else 0,
        "missing_columns": missing_cols,
        "extra_columns": extra_cols,
        "duplicated_engine_cycle_keys": duplicated_keys,
        "total_null_values": nulls,
        "non_finite_numeric_values": numeric_non_finite,
        "non_monotonic_engines": non_monotonic,
        "invalid_engine_ids": invalid_ids,
        "invalid_cycles": invalid_cycles,
    }

    fatal = (
        bool(missing_cols)
        or duplicated_keys > 0
        or nulls > 0
        or numeric_non_finite > 0
        or non_monotonic > 0
        or invalid_ids > 0
        or invalid_cycles > 0
    )
    if fatal:
        raise ValueError(f"Validation raw échouée: {report}")
    return report


def validate_rul_alignment(test_df: pd.DataFrame, rul_df: pd.DataFrame) -> dict:
    engines = sorted(test_df[ID_COL].unique())
    if len(engines) != len(rul_df):
        raise ValueError(
            f"RUL_FD001 contient {len(rul_df)} lignes pour {len(engines)} moteurs de test"
        )
    if rul_df.isna().any().any() or (rul_df.iloc[:, 0] < 0).any():
        raise ValueError("RUL_FD001 contient des valeurs manquantes ou négatives")
    return {"test_engines": len(engines), "rul_rows": int(len(rul_df)), "aligned": True}
