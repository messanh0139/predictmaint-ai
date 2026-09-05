from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine

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

logger = logging.getLogger(__name__)

USE_DATABASES = os.getenv("USE_DATABASES", "0") == "1"


def _load_raw_from_mongodb() -> pd.DataFrame:
    """Charge les données depuis MongoDB"""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://admin:admin123@mongodb:27017/")
    client = MongoClient(mongo_url)
    db = client["predictmaint"]

    logger.info("Lecture des données brutes depuis MongoDB")
    cursor = db["train_raw"].find({}, {"_id": 0})
    data = list(cursor)
    client.close()

    if not data:
        logger.warning("Collection MongoDB train_raw vide, fallback sur CSV")
        return load_train_fd001()

    df = pd.DataFrame(data)
    logger.info(f"{len(df)} lignes chargées depuis MongoDB")
    return df


def _save_to_postgresql(train_features: pd.DataFrame, calibration_features: pd.DataFrame, val_features: pd.DataFrame) -> None:
    """Sauvegarde les features dans PostgreSQL"""
    db_url = os.getenv("POSTGRESQL_URL", "postgresql://postgres:postgres@postgresql:5432/predictmaint")
    engine = create_engine(db_url)

    logger.info("Sauvegarde des features dans PostgreSQL")
    train_features.to_sql("train_features", engine, if_exists="replace", index=False, method="multi", chunksize=1000)
    calibration_features.to_sql("calibration_features", engine, if_exists="replace", index=False, method="multi", chunksize=1000)
    val_features.to_sql("val_features", engine, if_exists="replace", index=False, method="multi", chunksize=1000)

    logger.info(f"Sauvegarde terminée: {len(train_features)} train, {len(calibration_features)} calibration, {len(val_features)} validation")
    engine.dispose()


def _positive_rate(df: pd.DataFrame) -> float:
    """Proportion de lignes en classe positive"""
    return float(df[TARGET_COL].mean())


def load_supplemental_features(path: Path, columns) -> pd.DataFrame:
    """Charge les features de production optionnelles"""
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
    """Prépare les partitions de développement"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    if USE_DATABASES:
        logger.info("Mode USE_DATABASES activé: lecture depuis MongoDB")
        raw_train = _load_raw_from_mongodb()
    else:
        logger.info("Mode standard: lecture depuis CSV")
        raw_train = load_train_fd001()

    train_quality = validate_raw(raw_train)

    labelled_train = add_train_targets(raw_train)

    train_raw, calibration_raw, val_raw = split_by_engine_three_way(labelled_train)

    train_features = build_causal_features(train_raw)
    calibration_features = build_causal_features(calibration_raw)
    val_features = build_causal_features(val_raw)

    supplemental_rows = 0
    supplemental_path = Path(
        os.getenv("SUPPLEMENTAL_FEATURES_PATH", "storage/production/feedback_features.csv")
    )
    if os.getenv("INCLUDE_PRODUCTION_FEEDBACK", "0") == "1":
        supplemental = load_supplemental_features(supplemental_path, train_features.columns)
        if not supplemental.empty:
            production_engines = set(supplemental[ID_COL].unique())

            forbidden = set(val_raw[ID_COL].unique()) | set(calibration_raw[ID_COL].unique())
            overlap = production_engines & forbidden

            if overlap:
                print(
                    f"{len(overlap)} moteurs du feedback sont aussi dans validation/calibration: "
                    f"{sorted(overlap)[:5]}{'...' if len(overlap) > 5 else ''}"
                )
                print("Ces moteurs sont retirés pour éviter les fuites de données.")
                supplemental = supplemental[~supplemental[ID_COL].isin(forbidden)].copy()
                supplemental_rows = int(len(supplemental))
                print(f"Il reste {supplemental_rows} lignes utilisables après filtrage.")
            else:
                supplemental_rows = int(len(supplemental))

            if supplemental_rows > 0:
                train_features = pd.concat([train_features, supplemental], ignore_index=True)

    train_features.to_csv(PROCESSED_DIR / "train_features.csv", index=False)
    calibration_features.to_csv(PROCESSED_DIR / "calibration_features.csv", index=False)
    val_features.to_csv(PROCESSED_DIR / "val_features.csv", index=False)

    if USE_DATABASES:
        logger.info("Sauvegarde des features dans PostgreSQL")
        _save_to_postgresql(train_features, calibration_features, val_features)

    legacy_test_features = PROCESSED_DIR / "test_features.csv"
    if legacy_test_features.exists():
        legacy_test_features.unlink()

    reference_cols = [
        c for c in train_features.columns if c not in {ID_COL, TARGET_COL, RUL_COL}
    ]
    train_features[reference_cols].sample(
        min(5000, len(train_features)), random_state=42
    ).to_csv(REFERENCE_DIR / "reference_features.csv", index=False)

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
