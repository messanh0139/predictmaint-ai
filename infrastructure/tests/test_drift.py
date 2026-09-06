import numpy as np
import pandas as pd

from src.monitoring.drift import psi, statistical_drift_report


def test_psi_is_near_zero_when_distributions_are_identical():
    rng = np.random.default_rng(0)
    values = rng.normal(size=500)
    reference = pd.Series(values)
    current = pd.Series(values.copy())
    assert psi(reference, current) < 0.01


def test_psi_detects_a_shifted_distribution():
    rng = np.random.default_rng(0)
    reference = pd.Series(rng.normal(loc=0.0, scale=1.0, size=1000))
    # décalage net de la moyenne : doit dépasser le seuil d'alerte usuel (0.20)
    current = pd.Series(rng.normal(loc=3.0, scale=1.0, size=1000))
    assert psi(reference, current) > 0.20


def test_psi_returns_zero_below_minimum_sample_size():
    reference = pd.Series(range(10))
    current = pd.Series(range(10))
    assert psi(reference, current) == 0.0


def test_psi_bins_are_learned_only_on_reference():
    # les bornes des bins doivent venir uniquement de la référence : une valeur
    # de "current" hors de la plage de référence ne doit ni planter ni être ignorée
    reference = pd.Series(np.linspace(0, 100, 200))
    current = pd.Series(np.concatenate([np.linspace(0, 100, 190), np.full(10, 10_000.0)]))
    value = psi(reference, current)
    assert value > 0.0
    assert np.isfinite(value)


def test_psi_ignores_non_numeric_and_missing_values():
    reference = pd.Series([1.0] * 15 + [2.0] * 15)
    current = pd.Series([1.0] * 10 + [None] * 5 + ["invalide"] * 5 + [2.0] * 10)
    value = psi(reference, current)
    assert np.isfinite(value)


def test_statistical_drift_report_flags_alert_when_share_exceeds_threshold():
    rng = np.random.default_rng(0)
    reference = pd.DataFrame(
        {
            "stable": rng.normal(size=200),
            "derive_1": rng.normal(size=200),
            "derive_2": rng.normal(size=200),
        }
    )
    current = pd.DataFrame(
        {
            "stable": rng.normal(size=200),
            "derive_1": rng.normal(loc=5.0, size=200),
            "derive_2": rng.normal(loc=5.0, size=200),
        }
    )
    report = statistical_drift_report(current, reference=reference)
    assert report["status"] == "alert"
    assert report["drifted_share"] == len(report["drifted_features"]) / report["features_checked"]
    assert "stable" not in report["drifted_features"]
    assert "derive_1" in report["drifted_features"]
    assert "derive_2" in report["drifted_features"]


def test_statistical_drift_report_insufficient_data():
    reference = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    current = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    report = statistical_drift_report(current, reference=reference, min_samples=20)
    assert report["status"] == "insufficient_data"
    assert report["drifted_share"] is None
