from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-passed", type=int, default=None)
    parser.add_argument("--output", default="reports/project_validation.json")
    args = parser.parse_args()

    manifest = read_json("data/processed/split_manifest.json")
    metadata = read_json("models/model_metadata.json")
    optimization = read_json("models/optimization_report.json")
    promotion = read_json("models/promotion_report.json")
    quality_gate = read_json("models/quality_gate.json")
    external = read_json("models/test_metrics.json")
    registry = read_json("models/registry/index.json")

    model_path = ROOT / "models/model.joblib"
    registry_entry = next(
        (x for x in registry.get("versions", []) if x.get("version") == registry.get("champion")),
        None,
    )

    checks = {
        "split_has_no_engine_overlap": not manifest.get("engine_overlap"),
        "manifest_matches_model_metadata": (
            manifest.get("manifest_sha256") == metadata.get("dataset_manifest_sha256")
        ),
        "model_version_matches_manifest_prefix": metadata.get("model_version", "").endswith(
            str(manifest.get("manifest_sha256", ""))[:12]
        ),
        "registry_champion_matches_model": registry.get("champion") == metadata.get("model_version"),
        "external_holdout_matches_model": external.get("model_version") == metadata.get("model_version"),
        "quality_gate_passed": bool(quality_gate.get("passed")),
        "promotion_completed": bool(promotion.get("promoted")),
        "model_artifact_exists": model_path.exists(),
        "registry_model_hash_matches": bool(
            registry_entry and model_path.exists() and registry_entry.get("model_sha256") == sha256(model_path)
        ),
        "external_holdout_locked": bool(external.get("locked_external_holdout")),
        "holdout_not_materialized_in_development": (
            isinstance(manifest.get("external_test"), dict)
            and manifest["external_test"].get("status") == "LOCKED_NOT_MATERIALIZED_IN_DEVELOPMENT_PIPELINE"
            and not (ROOT / "data/processed/test_features.csv").exists()
        ),
        "holdout_loaded_only_at_evaluation": bool(external.get("holdout_loaded_only_at_evaluation")),
        "threshold_fitted_on_calibration": metadata.get("threshold_source") == "dedicated calibration engines",
        "grafana_provisioning_present": (ROOT / "monitoring/grafana/provisioning/datasources/prometheus.yml").exists() and (ROOT / "monitoring/grafana/provisioning/dashboards/predictmaint.yml").exists(),
    }
    if args.tests_passed is not None:
        checks["automated_tests_passed"] = args.tests_passed > 0

    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "project": "PredictMaint AI",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_status": status,
        "automated_tests": (
            f"{args.tests_passed} passed" if args.tests_passed is not None else "not supplied"
        ),
        "validation_checks": checks,
        "data_manifest_sha256": manifest.get("manifest_sha256"),
        "partitions": manifest.get("rows", {}),
        "engine_overlap": manifest.get("engine_overlap", []),
        "champion": {
            "name": metadata.get("model_name"),
            "version": metadata.get("model_version"),
            "threshold": metadata.get("threshold"),
            "validation_metrics": metadata.get("validation_metrics", {}),
            "model_sha256": sha256(model_path) if model_path.exists() else None,
        },
        "optimization": {
            "trials": optimization.get("n_trials"),
            "cv_pr_auc_mean": optimization.get("cv_pr_auc_mean"),
            "business_cost_gain_vs_default_xgboost": optimization.get(
                "business_cost_gain_vs_default_xgboost"
            ),
            "business_cost_gain_pct_vs_default_xgboost": optimization.get(
                "business_cost_gain_pct_vs_default_xgboost"
            ),
        },
        "promotion": promotion,
        "quality_gate": quality_gate,
        "external_holdout": external,
        "registry": {
            "champion": registry.get("champion"),
            "registered_versions": [x.get("version") for x in registry.get("versions", [])],
        },
        "notes": [
            "External test dataset is excluded from retraining and deployment quality gates.",
            "Monitoring replays the threshold stored with each prediction, including multi-version batches.",
            "GCP deployment assets are prepared but require the user's Google Cloud project and credentials.",
            "MLflow/GCS integrations activate when their dependencies and environment variables are configured.",
        ],
    }

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(output), "checks": checks}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
