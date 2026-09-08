from __future__ import annotations

import json
import sys

from src.config import MAX_VALIDATION_COST_PER_1000, MIN_PR_AUC, MIN_RECALL, MODELS_DIR


def evaluate_gate(metadata: dict) -> dict:
    # Vérifie que le modèle respecte les seuils de qualité minimum avant déploiement :
    m = metadata["validation_metrics"]
    checks = {
        # Rappel minimum : on ne veut pas manquer trop de pannes réelles.
        "recall": {"value": m["recall"], "min": MIN_RECALL, "passed": m["recall"] >= MIN_RECALL},
        # PR-AUC : métrique globale robuste au déséquilibre de classes.
        "pr_auc": {"value": m["pr_auc"], "min": MIN_PR_AUC, "passed": m["pr_auc"] >= MIN_PR_AUC},
        # Coût métier normalisé pour 1000 prédictions : plafond au-delà duquel
        # le modèle n'est pas acceptable économiquement.
        "business_cost_per_1000": {
            "value": m["business_cost_per_1000"],
            "max": MAX_VALIDATION_COST_PER_1000,
            "passed": m["business_cost_per_1000"] <= MAX_VALIDATION_COST_PER_1000,
        },
    }
    return {"passed": all(x["passed"] for x in checks.values()), "checks": checks}


def main() -> None:
    # Lit les métadonnées du modèle champion et vérifie qu'il passe la porte de qualité
    metadata = json.loads((MODELS_DIR / "model_metadata.json").read_text(encoding="utf-8"))
    result = evaluate_gate(metadata)
    (MODELS_DIR / "quality_gate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        # Code de sortie non nul pour bloquer le déploiement en CI/CD.
        sys.exit(2)


if __name__ == "__main__":
    main()
