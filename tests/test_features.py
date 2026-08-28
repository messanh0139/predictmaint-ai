import pandas as pd

from src.config import FORBIDDEN_MODEL_COLUMNS
from src.features.build_features import build_causal_features, candidate_feature_columns


def _toy_df():
    return pd.DataFrame(
        {
            "engine_id": [1, 1, 1, 1, 2, 2],
            "cycle": [1, 2, 3, 4, 1, 2],
            "setting_1": [0.0] * 6,
            "setting_2": [0.0] * 6,
            "setting_3": [0.0] * 6,
            **{
                f"sensor_{i}": ([10, 20, 30, 40, 100, 200] if i == 2 else [1.0] * 6)
                for i in range(1, 22)
            },
        }
    )


def test_rolling_features_are_engine_isolated_and_causal():
    out = build_causal_features(_toy_df())
    e1c2 = out[(out.engine_id == 1) & (out.cycle == 2)].iloc[0]
    e2c1 = out[(out.engine_id == 2) & (out.cycle == 1)].iloc[0]
    assert e1c2["sensor_2_mean_5"] == 15
    assert pd.isna(e2c1["sensor_2_lag_1"])
    assert e2c1["sensor_2_mean_5"] == 100


def test_future_mutation_does_not_change_past_features():
    base_df = _toy_df().query("engine_id == 1").copy()
    base = build_causal_features(base_df)
    mutated = base_df.copy()
    mutated.loc[mutated["cycle"] == 4, "sensor_2"] = 999999
    after = build_causal_features(mutated)
    cols = [c for c in base.columns if c.startswith("sensor_2_")]
    pd.testing.assert_series_equal(base.iloc[1][cols], after.iloc[1][cols], check_names=False)


def test_forbidden_columns_are_not_candidate_features():
    df = _toy_df()
    df["RUL"] = 10
    df["failure_within_30_cycles"] = 1
    candidates = candidate_feature_columns(df)
    assert FORBIDDEN_MODEL_COLUMNS.isdisjoint(candidates)
