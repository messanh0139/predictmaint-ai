from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import (
    ID_COL,
    PROCESSED_DIR,
    RAW_DIR,
    REFERENCE_DIR,
    RUL_COL,
    TARGET_COL,
)
from src.data.load import load_train_fd001
from src.data.split import split_by_engine_three_way
from src.data.targets import add_train_targets
from src.data.validate import validate_raw
from src.features.build_features import build_causal_features
from src.utils.fingerprints import canonical_json_sha256, sha256_file


def _positive_rate(df: pd.DataFrame) -> float:
    """Proportion de lignes en classe positive (panne imminente), pour le manifeste."""
    return float(df[TARGET_COL].mean())


def load_supplemental_features(path: Path, columns) -> pd.DataFrame:
    """Charge le lot optionnel de features de production (feedback ou upload direct).

    Retourne un DataFrame vide si le fichier est absent, vide ou sans les colonnes
    minimales requises : c'est un cas normal (aucune donnée de production pour le
    moment, par exemple avant la première vraie prédiction en production), pas une
    erreur qui doit interrompre la préparation.
    """
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        supplemental = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    required = {ID_COL, TARGET_COL, "cycle"}
    if not required.issubset(supplemental.columns) or supplemental.empty:
        return pd.DataFrame()
    return supplemental.reindex(columns=columns)


def main() -> None:
    """Prépare uniquement les partitions de développement.

    Le holdout externe (`test_FD001.txt` + `RUL_FD001.txt`) n'est ni chargé, ni
    labellisé, ni matérialisé ici. Il reste fermé jusqu'à `src.models.evaluate`.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    raw_train = load_train_fd001()
    train_quality = validate_raw(raw_train)

    # Opération de labellisation : RUL/max-cycle servent uniquement à construire y.
    labelled_train = add_train_targets(raw_train)

    # Etape critique anti-leakage : séparation PAR MOTEUR avant feature engineering
    # et avant toute statistique supervisée utilisée pour prendre une décision.
    train_raw, calibration_raw, val_raw = split_by_engine_three_way(labelled_train)

    # Features causales, calculées séparément par partition.
    train_features = build_causal_features(train_raw)
    calibration_features = build_causal_features(calibration_raw)
    val_features = build_causal_features(val_raw)

    supplemental_rows = 0
    supplemental_path = Path(
        os.getenv("SUPPLEMENTAL_FEATURES_PATH", "data/production/feedback_features.csv")
    )
    if os.getenv("INCLUDE_PRODUCTION_FEEDBACK", "0") == "1":
        supplemental = load_supplemental_features(supplemental_path, train_features.columns)
        if not supplemental.empty:
            supplemental_rows = int(len(supplemental))
            train_features = pd.concat([train_features, supplemental], ignore_index=True)

    train_features.to_csv(PROCESSED_DIR / "train_features.csv", index=False)
    calibration_features.to_csv(PROCESSED_DIR / "calibration_features.csv", index=False)
    val_features.to_csv(PROCESSED_DIR / "val_features.csv", index=False)

    # Supprime un ancien artefact éventuel afin d'éviter de croire que le holdout
    # fait partie du pipeline standard.
    legacy_test_features = PROCESSED_DIR / "test_features.csv"
    if legacy_test_features.exists():
        legacy_test_features.unlink()

    # Echantillon de référence (features uniquement, sans ID/cible) pour le monitoring
    # de dérive en production : taille plafonnée à 5000 lignes, seed fixe pour la reproductibilité.
    reference_cols = [
        c for c in train_features.columns if c not in {ID_COL, TARGET_COL, RUL_COL}
    ]
    train_features[reference_cols].sample(
        min(5000, len(train_features)), random_state=42
    ).to_csv(REFERENCE_DIR / "reference_features.csv", index=False)

    # Garde-fou anti-fuite : un même moteur ne doit apparaître que dans une seule partition.
    train_engines = set(map(int, train_raw[ID_COL].unique()))
    calibration_engines = set(map(int, calibration_raw[ID_COL].unique()))
    val_engines = set(map(int, val_raw[ID_COL].unique()))
    overlap = sorted(
        (train_engines & calibration_engines)
        | (train_engines & val_engines)
        | (calibration_engines & val_engines)
    )
    if overlap:
        raise RuntimeError(f"Data leakage: moteurs communs entre partitions: {overlap}")

    # Les fichiers externes sont fingerprintés sans être ouverts/interprétés.
    raw_fingerprints = {
        name: sha256_file(RAW_DIR / name)
        for name in ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]
    }
    supplemental_sha256 = (
        sha256_file(supplemental_path)
        if supplemental_rows > 0 and supplemental_path.exists()
        else None
    )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "FD001",
        "raw_sha256": raw_fingerprints,
        "train_engines": sorted(train_engines),
        "calibration_engines": sorted(calibration_engines),
        "validation_engines": sorted(val_engines),
        "engine_overlap": overlap,
        "external_test": {
            "files": ["test_FD001.txt", "RUL_FD001.txt"],
            "status": "LOCKED_NOT_MATERIALIZED_IN_DEVELOPMENT_PIPELINE",
            "opened_by": "python -m src.models.evaluate only",
        },
        "raw_train_quality": train_quality,
        "supplemental_production_feedback": {
            "rows": supplemental_rows,
            "sha256": supplemental_sha256,
        },
        "rows": {
            "train": int(len(train_features)),
            "calibration": int(len(calibration_features)),
            "validation": int(len(val_features)),
            "external_test": "locked_until_explicit_evaluation",
        },
        "positive_rate": {
            "train": _positive_rate(train_features),
            "calibration": _positive_rate(calibration_features),
            "validation": _positive_rate(val_features),
            "external_test": "unknown_until_explicit_evaluation",
        },
        "anti_leakage_controls": [
            "three-way engine split before supervised EDA and feature engineering",
            "causal features only (current/past of same engine)",
            "selection/preprocessing/model fit on train only",
            "threshold fit on dedicated calibration engines",
            "champion decision on locked validation engines",
            "external holdout not loaded/materialized by development preparation",
        ],
    }

    stable_manifest = {k: v for k, v in manifest.items() if k != "created_at_utc"}
    manifest["manifest_sha256"] = canonical_json_sha256(stable_manifest)
    (PROCESSED_DIR / "split_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
