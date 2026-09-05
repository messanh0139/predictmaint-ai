from sklearn.linear_model import LogisticRegression

from src.models.common import choose_threshold, metrics
from src.models.pipelines import build_model_pipeline
from src.models.quality_gate import evaluate_gate


# Vérifie que le pipeline du modèle impute toujours les valeurs manquantes,
# et n'ajoute une étape de mise à l'échelle que si elle est explicitement demandée.
def test_model_pipeline_always_imputes_and_optionally_scales():
    unscaled = build_model_pipeline(LogisticRegression())
    scaled = build_model_pipeline(LogisticRegression(), scale_features=True)

    assert list(unscaled.named_steps) == ["imputer", "model"]
    assert list(scaled.named_steps) == ["imputer", "scaler", "model"]


# Vérifie que le coût métier pénalise davantage les faux négatifs (pannes
# manquées) que les faux positifs, conformément à l'objectif métier du projet.
def test_metrics_business_cost_penalizes_false_negatives():
    y = [0, 0, 1, 1]
    prob = [0.1, 0.7, 0.4, 0.9]
    m = metrics(y, prob, threshold=0.5)
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["business_cost"] == 10500


# Vérifie que le seuil choisi respecte bien le rappel minimal (guardrail)
# lorsque c'est atteignable, quitte à sacrifier de la précision.
def test_threshold_respects_recall_guardrail_when_feasible():
    y = [0, 0, 0, 1, 1, 1]
    prob = [0.05, 0.1, 0.2, 0.55, 0.8, 0.95]
    threshold, report = choose_threshold(y, prob, min_recall=0.85)
    assert 0 <= threshold <= 1
    assert report["recall"] >= 0.85


# Vérifie que la quality gate rejette bien un modèle trop faible (rappel,
# PR-AUC et coût métier tous en dessous des seuils acceptables), pour éviter
# de promouvoir un modèle de mauvaise qualité en production.
def test_quality_gate_rejects_weak_model():
    weak = {
        "validation_metrics": {
            "recall": 0.5,
            "pr_auc": 0.4,
            "business_cost_per_1000": 999999,
        }
    }
    assert evaluate_gate(weak)["passed"] is False


# Vérifie que l'enregistrement local d'un modèle crée bien une entrée versionnée
# avec un hash SHA-256 de l'artefact, pour garantir la traçabilité et
# l'intégrité des modèles enregistrés.
def test_local_registry_is_versioned_and_hashes_artifact(tmp_path):
    import json

    from src.models.register import register_local_model

    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"fake-model")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_version": "v-test",
                "model_name": "dummy",
                "dataset_manifest_sha256": "abc",
                "validation_metrics": {"recall": 0.9},
            }
        ),
        encoding="utf-8",
    )
    entry = register_local_model(model_path, metadata_path, tmp_path / "registry")
    assert entry["version"] == "v-test"
    assert len(entry["model_sha256"]) == 64
    assert (tmp_path / "registry" / "v-test" / "model.joblib").exists()


# le registre local ne doit pas remplacer le champion par un modèle moins bon
def test_local_registry_never_regresses_champion_to_a_worse_version(tmp_path):
    import json

    from src.models.register import register_local_model

    def write(name: str, validation_metrics: dict):
        # crée un faux modèle et ses métadonnées pour une version donnée
        model_path = tmp_path / f"{name}.joblib"
        model_path.write_bytes(b"fake-model")
        metadata_path = tmp_path / f"{name}.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "model_version": name,
                    "model_name": "dummy",
                    "validation_metrics": validation_metrics,
                }
            ),
            encoding="utf-8",
        )
        return model_path, metadata_path

    good_metrics = {"recall": 1.0, "pr_auc": 0.95, "business_cost_per_1000": 50000.0, "brier": 0.03}
    worse_metrics = {"recall": 0.98, "pr_auc": 0.94, "business_cost_per_1000": 90000.0, "brier": 0.04}
    registry_dir = tmp_path / "registry"

    good_entry = register_local_model(*write("v-good", good_metrics), registry_dir)
    assert good_entry["local_champion_updated"] is True

    worse_entry = register_local_model(*write("v-worse", worse_metrics), registry_dir)
    assert worse_entry["local_champion_updated"] is False

    index = json.loads((registry_dir / "index.json").read_text(encoding="utf-8"))
    assert index["champion"] == "v-good"
    # il reste quand même dans l'historique des versions
    assert any(v["version"] == "v-worse" for v in index["versions"])
