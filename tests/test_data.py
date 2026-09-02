import pandas as pd

from src.data.load import load_test_inputs_fd001, load_train_fd001
from src.data.prepare import load_supplemental_features
from src.data.split import split_by_engine, split_by_engine_three_way
from src.data.targets import add_test_targets, add_train_targets
from src.data.validate import validate_raw, validate_rul_alignment


def test_dataset_shape_and_quality_without_opening_holdout_labels():
    # Vérifie les dimensions attendues du dataset FD001 (NASA C-MAPSS) et l'absence
    # de doublons, sans jamais charger les vraies étiquettes RUL du holdout (test).
    train = load_train_fd001()
    test = load_test_inputs_fd001()
    assert train.shape == (20631, 26)
    assert test.shape == (13096, 26)
    assert validate_raw(train)["engines"] == 100
    assert validate_raw(test)["duplicated_engine_cycle_keys"] == 0


def test_three_way_group_split_has_no_engine_leakage():
    # Le split fit/calibration/validation doit se faire par moteur (engine_id) et non
    # par ligne, pour éviter toute fuite : un même moteur ne doit apparaître que dans
    # un seul des trois sous-ensembles.
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
    # Variante à deux sous-ensembles (rétrocompatibilité) : même exigence d'absence
    # de fuite d'un moteur entre les deux groupes.
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
    # Vérifie la reconstitution d'une ligne de features labellisée à partir d'une
    # prédiction de production (historique brut) rapprochée de son feedback réel
    # (panne survenue ou non), utilisée ensuite pour le retraining.
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
    # Les moteurs de production sont réindexés dans un espace d'ID dédié (offset 1_000_000)
    # pour ne jamais entrer en collision avec les engine_id du dataset d'entraînement.
    assert int(out.iloc[0]["engine_id"]) == 1_000_007
    assert int(out.iloc[0]["failure_within_30_cycles"]) == 1
    assert "sensor_2_mean_5" in out.columns


def test_load_supplemental_features_missing_file_returns_empty(tmp_path):
    # Un fichier de features supplémentaires absent ne doit pas faire échouer le
    # chargement : il doit simplement renvoyer un DataFrame vide.
    result = load_supplemental_features(tmp_path / "does_not_exist.csv", columns=["a", "b"])
    assert result.empty


def test_load_supplemental_features_handles_empty_file_without_crashing(tmp_path):
    # Cas réel : collect_feedback.py peut produire un fichier sans aucune ligne
    # labellisée exploitable (aucune prédiction de production n'a encore reçu de
    # feedback). pandas lève EmptyDataError sur un CSV vide ; ça doit être absorbé.
    path = tmp_path / "feedback_features.csv"
    path.write_text("\n", encoding="utf-8")
    result = load_supplemental_features(path, columns=["engine_id", "cycle", "failure_within_30_cycles"])
    assert result.empty


def test_load_supplemental_features_rejects_missing_required_columns(tmp_path):
    # Un CSV présent mais auquel il manque une colonne requise (ici la cible
    # failure_within_30_cycles) doit être traité comme invalide -> résultat vide,
    # plutôt que de propager un DataFrame incomplet en aval.
    path = tmp_path / "feedback_features.csv"
    pd.DataFrame({"engine_id": [1], "cycle": [1]}).to_csv(path, index=False)
    result = load_supplemental_features(path, columns=["engine_id", "cycle", "failure_within_30_cycles"])
    assert result.empty


def test_load_supplemental_features_reindexes_to_target_columns(tmp_path):
    # Le CSV source peut avoir moins de colonnes que le schéma de features cible
    # (ex. certaines features calculées manquantes) : elles doivent être ajoutées
    # en NaN plutôt que de faire échouer le chargement.
    path = tmp_path / "feedback_features.csv"
    pd.DataFrame(
        {"engine_id": [1_000_007], "cycle": [3], "failure_within_30_cycles": [1]}
    ).to_csv(path, index=False)
    result = load_supplemental_features(
        path, columns=["engine_id", "cycle", "failure_within_30_cycles", "sensor_2_mean_5"]
    )
    assert list(result.columns) == ["engine_id", "cycle", "failure_within_30_cycles", "sensor_2_mean_5"]
    assert len(result) == 1
    assert pd.isna(result.iloc[0]["sensor_2_mean_5"])
