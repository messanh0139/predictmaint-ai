from sklearn.linear_model import LogisticRegression

from src.models.common import choose_threshold, metrics
from src.models.pipelines import build_model_pipeline
from src.models.quality_gate import evaluate_gate


def test_model_pipeline_always_imputes_and_optionally_scales():
    unscaled = build_model_pipeline(LogisticRegression())
    scaled = build_model_pipeline(LogisticRegression(), scale_features=True)

    assert list(unscaled.named_steps) == ["imputer", "model"]
    assert list(scaled.named_steps) == ["imputer", "scaler", "model"]


def test_metrics_business_cost_penalizes_false_negatives():
    y = [0, 0, 1, 1]
    prob = [0.1, 0.7, 0.4, 0.9]
    m = metrics(y, prob, threshold=0.5)
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["business_cost"] == 10500


def test_threshold_respects_recall_guardrail_when_feasible():
    y = [0, 0, 0, 1, 1, 1]
    prob = [0.05, 0.1, 0.2, 0.55, 0.8, 0.95]
    threshold, report = choose_threshold(y, prob, min_recall=0.85)
    assert 0 <= threshold <= 1
    assert report["recall"] >= 0.85


def test_quality_gate_rejects_weak_model():
    weak = {
        "validation_metrics": {
            "recall": 0.5,
            "pr_auc": 0.4,
            "business_cost_per_1000": 999999,
        }
    }
    assert evaluate_gate(weak)["passed"] is False


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
