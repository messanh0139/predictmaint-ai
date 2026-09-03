from __future__ import annotations

import json
import shutil


from src.config import MIN_PR_AUC, MIN_RECALL, MODELS_DIR
from src.models.common import validation_sort_key
from src.utils.fingerprints import runtime_metadata


def main() -> dict:
    # Compare le candidat optimisé (issu de optimize
    champion_meta_path = MODELS_DIR / "model_metadata.json"
    candidate_meta_path = MODELS_DIR / "candidates" / "xgboost_optimized_metadata.json"
    candidate_model_path = MODELS_DIR / "candidates" / "xgboost_optimized.joblib"

    if not candidate_meta_path.exists() or not candidate_model_path.exists():
        result = {"promoted": False, "reason": "optimized candidate not found"}
        (MODELS_DIR / "promotion_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return result

    champion = json.loads(champion_meta_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_meta_path.read_text(encoding="utf-8"))
    champ_val = champion["validation_metrics"]
    cand_val = candidate["validation_metrics"]

    # Garde-fous qualité : le candidat doit rester au-dessus des seuils minimums,
    # indépendamment de sa comparaison avec le champion.
    guardrails_ok = cand_val["recall"] >= MIN_RECALL and cand_val["pr_auc"] >= MIN_PR_AUC
    # Comparaison selon le même ordre de priorité que la sélection de modèle
    # (recall -> coût métier -> PR-AUC -> Brier), défini dans validation_sort_key.
    better = validation_sort_key(cand_val) < validation_sort_key(champ_val)
    promoted = bool(guardrails_ok and better)

    result = {
        "promoted": promoted,
        "guardrails_ok": guardrails_ok,
        "candidate_better_on_locked_validation": better,
        "champion": {"name": champion["model_name"], "validation_metrics": champ_val},
        "candidate": {"name": candidate["name"], "validation_metrics": cand_val},
        "decision_rule": "validation only; recall guardrail -> business cost -> PR-AUC -> Brier",
    }

    if promoted:
        shutil.copy2(candidate_model_path, MODELS_DIR / "model.joblib")
        runtime = runtime_metadata()
        # Version = sha git court si disponible, sinon fallback sur le hash du dataset.
        version_token = runtime["git_sha"][:12] if runtime["git_sha"] != "unknown" else champion.get("dataset_manifest_sha256", "unknown")[:12]
        champion.update(runtime)
        champion.update(
            {
                "model_name": candidate["name"],
                "model_version": f"optimized-{version_token}",
                "threshold": candidate["threshold"],
                "threshold_source": candidate.get("threshold_source", "dedicated calibration engines"),
                "validation_metrics": cand_val,
                "optimization": {"best_params": candidate["best_params"]},
            }
        )
        champion_meta_path.write_text(
            json.dumps(champion, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    (MODELS_DIR / "promotion_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
