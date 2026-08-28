import pandas as pd
from src.config import FAILURE_WINDOW, ID_COL, TIME_COL, TARGET_COL, RUL_COL


def add_train_targets(df: pd.DataFrame, failure_window: int = FAILURE_WINDOW) -> pd.DataFrame:
    """Construit le label à partir de la trajectoire run-to-failure.

    max_cycle est utilisé UNIQUEMENT pour construire la vérité terrain et est supprimé des features.
    """
    out = df.copy()
    max_cycle = out.groupby(ID_COL)[TIME_COL].transform("max")
    out[RUL_COL] = max_cycle - out[TIME_COL]
    out[TARGET_COL] = (out[RUL_COL] <= failure_window).astype("int8")
    return out


def add_test_targets(test_df: pd.DataFrame, rul_last: pd.DataFrame, failure_window: int = FAILURE_WINDOW) -> pd.DataFrame:
    """Reconstruit le RUL vrai de chaque ligne du test NASA.

    Pour un moteur, NASA donne le RUL au dernier cycle observé. Pour une ligne antérieure :
    RUL_ligne = (dernier_cycle_observe - cycle) + RUL_dernier_cycle.
    """
    out = test_df.copy()
    max_observed = out.groupby(ID_COL)[TIME_COL].max().rename("max_observed_cycle")
    mapping = pd.DataFrame({
        ID_COL: sorted(out[ID_COL].unique()),
        "RUL_at_last_observation": rul_last["RUL_at_last_observation"].to_numpy(),
    })
    out = out.merge(max_observed, on=ID_COL, how="left").merge(mapping, on=ID_COL, how="left")
    out[RUL_COL] = (out["max_observed_cycle"] - out[TIME_COL]) + out["RUL_at_last_observation"]
    out[TARGET_COL] = (out[RUL_COL] <= failure_window).astype("int8")
    return out.drop(columns=["max_observed_cycle", "RUL_at_last_observation"])
