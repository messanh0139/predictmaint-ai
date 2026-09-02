from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import pandas as pd

from src.config import ID_COL, MODELS_DIR, TIME_COL
from src.data.load import load_external_test_fd001
from src.data.targets import add_test_targets
from src.data.validate import validate_raw, validate_rul_alignment
from src.features.build_features import build_causal_features
from src.models.common import load_selected_features, metrics, xy


def main() -> None:
    """Évaluation finale EXTERNE sur le holdout verrouillé.

    Le holdout est chargé et labellisé ici, au dernier moment. Cette commande ne
    fait partie ni du retraining automatique ni du quality gate de déploiement.
    """
    raw_test, rul = load_external_test_fd001()
    # Contrôles qualité des données brutes et de l'alignement RUL avant tout calcul.
    test_quality = validate_raw(raw_test)
    rul_quality = validate_rul_alignment(raw_test, rul)

    test_labelled = add_test_targets(raw_test, rul)
    test_df = build_causal_features(test_labelled)

    features = load_selected_features(MODELS_DIR / "selected_features.json")
    metadata = json.loads((MODELS_DIR / "model_metadata.json").read_text(encoding="utf-8"))
    model = joblib.load(MODELS_DIR / "model.joblib")

    X_test, y_test = xy(test_df, features)
    prob = model.predict_proba(X_test)[:, 1]
    # Réutilise le seuil déjà calibré et figé dans les métadonnées du modèle
    # (pas de re-calibration sur le holdout externe).
    result = metrics(y_test, prob, float(metadata["threshold"]))
    result.update(
        {
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_name": metadata["model_name"],
            "model_version": metadata.get("model_version"),
            "dataset": "FD001 external holdout",
            "locked_external_holdout": True,
            "holdout_loaded_only_at_evaluation": True,
            "raw_test_quality": test_quality,
            "rul_alignment": rul_quality,
            "warning": "Do not use these metrics to iteratively tune the model.",
        }
    )
    (MODELS_DIR / "test_metrics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pd.DataFrame(
        {
            ID_COL: test_df[ID_COL].astype(int),
            TIME_COL: test_df[TIME_COL].astype(int),
            "y_true": y_test.to_numpy(),
            "probability": prob,
            "prediction": (prob >= float(metadata["threshold"])).astype(int),
        }
    ).to_csv(MODELS_DIR / "test_predictions.csv", index=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
