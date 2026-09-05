import json

from sklearn.linear_model import LogisticRegression

GOOD_METRICS = {"recall": 1.0, "pr_auc": 0.95, "business_cost_per_1000": 50000.0, "brier": 0.03}
WORSE_METRICS = {"recall": 0.98, "pr_auc": 0.94, "business_cost_per_1000": 90000.0, "brier": 0.04}


def _write_model_files(tmp_path, validation_metrics: dict, version: str):
    import joblib

    tmp_path.mkdir(parents=True, exist_ok=True)
    model = LogisticRegression().fit([[0.0], [1.0]], [0, 1])
    model_path = tmp_path / "model.joblib"
    joblib.dump(model, model_path)
    metadata_path = tmp_path / "model_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "model_name": "logistic_regression",
                "validation_metrics": validation_metrics,
            }
        ),
        encoding="utf-8",
    )
    return model_path, metadata_path


# Régression reproduite en production le 2026-09-05 : chaque exécution enregistrait
# une nouvelle version MLflow sans jamais marquer laquelle est réellement la
# championne, et le registre local/GCS pouvait de la même façon régresser vers un
# modèle moins bon. Vérifie que l'alias "champion" (models:/<name>@champion) ne se
# déplace que vers une version réellement meilleure, sur un vrai backend MLflow
# (sqlite local), sans mock.
def test_mlflow_champion_alias_never_regresses_to_a_worse_version(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_MODEL_NAME", "predictmaint-fd001-test")

    from src.models.register import register_mlflow

    good_model_path, good_metadata_path = _write_model_files(tmp_path / "good", GOOD_METRICS, "v-good")
    good_result = register_mlflow(good_model_path, good_metadata_path)
    assert good_result["status"] == "registered"
    assert good_result["registry_champion_updated"] is True

    worse_model_path, worse_metadata_path = _write_model_files(tmp_path / "worse", WORSE_METRICS, "v-worse")
    worse_result = register_mlflow(worse_model_path, worse_metadata_path)
    assert worse_result["status"] == "registered"
    assert worse_result["registry_champion_updated"] is False

    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    champion = client.get_model_version_by_alias("predictmaint-fd001-test", "champion")
    assert str(champion.version) == good_result["registered_version"]
