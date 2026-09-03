import json

from src.monitoring.performance import performance_report


# Petit utilitaire de test : écrit une liste de dictionnaires au format JSONL,
# comme le font les journaux de prédictions et de feedback en production.
def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


# Vérifie que le rapport de performance applique bien le seuil de décision
# propre à la version du modèle de chaque prédiction, plutôt qu'un seuil
# global unique qui fausserait les métriques en cas de changement de modèle.
def test_performance_uses_each_predictions_versioned_threshold(tmp_path):
    predictions = []
    feedback = []
    # Version A : seuil élevé ; Version B : seuil faible. Une médiane globale à 0,5
    # classerait mal les positifs de B, alors que les seuils historiques sont corrects.
    for i in range(20):
        positive = i % 2 == 1
        version = "vA" if i < 10 else "vB"
        threshold = 0.8 if version == "vA" else 0.2
        probability = (0.9 if positive else 0.7) if version == "vA" else (0.3 if positive else 0.1)
        prediction_id = f"p{i}"
        predictions.append(
            {
                "prediction_id": prediction_id,
                "failure_probability": probability,
                "threshold": threshold,
                "model_version": version,
            }
        )
        feedback.append(
            {
                "prediction_id": prediction_id,
                "actual_failure_within_30_cycles": int(positive),
            }
        )

    pred_path = tmp_path / "predictions.jsonl"
    fb_path = tmp_path / "feedback.jsonl"
    _write_jsonl(pred_path, predictions)
    _write_jsonl(fb_path, feedback)

    report = performance_report(pred_path, fb_path)
    assert report["threshold_policy"] == "per_prediction_versioned_threshold"
    assert report["recall"] == 1.0
    assert report["precision"] == 1.0
    assert set(report["per_model_version"]) == {"vA", "vB"}


# Vérifie que le rapport de drift refuse de conclure statistiquement quand
# l'échantillon courant est trop petit, pour éviter un diagnostic de dérive
# peu fiable (faux positif ou faux négatif) basé sur trop peu de données.
def test_drift_report_requires_enough_current_samples():
    import pandas as pd

    from src.monitoring.drift import statistical_drift_report

    reference = pd.DataFrame({"f1": list(range(100))})
    current = pd.DataFrame({"f1": [1, 2, 3]})
    report = statistical_drift_report(current=current, reference=reference)
    assert report["status"] == "insufficient_data"
    assert report["drifted_share"] is None
