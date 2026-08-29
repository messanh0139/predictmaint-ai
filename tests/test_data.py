import pandas as pd

from src.data.load import load_test_inputs_fd001, load_train_fd001
from src.data.split import split_by_engine, split_by_engine_three_way
from src.data.targets import add_test_targets, add_train_targets
from src.data.validate import validate_raw, validate_rul_alignment


def test_dataset_shape_and_quality_without_opening_holdout_labels():
    train = load_train_fd001()
    test = load_test_inputs_fd001()
    assert train.shape == (20631, 26)
    assert test.shape == (13096, 26)
    assert validate_raw(train)["engines"] == 100
    assert validate_raw(test)["duplicated_engine_cycle_keys"] == 0


def test_three_way_group_split_has_no_engine_leakage():
    train = load_train_fd001()
    labelled = add_train_targets(train)
    fit, calibration, validation = split_by_engine_three_way(labelled)
    a, b, c = set(fit.engine_id), set(calibration.engine_id), set(validation.engine_id)
    assert a.isdisjoint(b)
    assert a.isdisjoint(c)
    assert b.isdisjoint(c)
    assert len(a) == 70
    assert len(b) == 15
    assert len(c) == 15


def test_two_way_group_split_compatibility():
    train = load_train_fd001()
    a, b = split_by_engine(add_train_targets(train))
    assert set(a.engine_id).isdisjoint(set(b.engine_id))


def test_test_rul_reconstruction_on_synthetic_holdout():
    # Test de la formule sans ouvrir la vérité terrain réelle du holdout externe.
    test = pd.DataFrame(
        {
            "engine_id": [1, 1, 1, 2, 2],
            "cycle": [1, 2, 3, 1, 2],
        }
    )
    for c in ["setting_1", "setting_2", "setting_3"]:
        test[c] = 0.0
    for i in range(1, 22):
        test[f"sensor_{i}"] = float(i)

    rul = pd.DataFrame({"RUL_at_last_observation": [10, 20]})
    assert validate_rul_alignment(test, rul)["aligned"] is True

    labelled = add_test_targets(test, rul)
    last = labelled.sort_values(["engine_id", "cycle"]).groupby("engine_id").tail(1)
    assert last.sort_values("engine_id")["RUL"].astype(int).to_list() == [10, 20]
    # Pour le moteur 1 : dernier cycle observé 3, donc au cycle 1 RUL = (3-1)+10 = 12.
    assert int(labelled[(labelled.engine_id == 1) & (labelled.cycle == 1)]["RUL"].iloc[0]) == 12


def test_feedback_dataset_builds_labelled_production_row():
    from src.data.collect_feedback import build_feedback_feature_dataset

    history = []
    for cycle in [1, 2, 3]:
        snap = {"cycle": cycle, "setting_1": 0.0, "setting_2": 0.0, "setting_3": 100.0}
        snap.update({f"sensor_{i}": float(i + cycle) for i in range(1, 22)})
        history.append(snap)
    predictions = [{"prediction_id": "p1", "engine_id": 7, "raw_history": history}]
    feedback = [{"prediction_id": "p1", "actual_failure_within_30_cycles": 1}]
    out = build_feedback_feature_dataset(predictions, feedback)
    assert len(out) == 1
    assert int(out.iloc[0]["engine_id"]) == 1_000_007
    assert int(out.iloc[0]["failure_within_30_cycles"]) == 1
    assert "sensor_2_mean_5" in out.columns
