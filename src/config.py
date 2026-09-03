from __future__ import annotations

import os
from pathlib import Path

# Chemins du projet
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "storage" / "raw"
PROCESSED_DIR = ROOT / "storage" / "processed"
REFERENCE_DIR = ROOT / "storage" / "reference"
MODELS_DIR = ROOT / "storage" / "models"
REPORTS_DIR = ROOT / "storage" / "reports"

# Paramètres d'entraînement
FAILURE_WINDOW = int(os.getenv("FAILURE_WINDOW", "30"))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "42"))
VALIDATION_SIZE = float(os.getenv("VALIDATION_SIZE", "0.20"))
CV_FOLDS = int(os.getenv("CV_FOLDS", "5"))

# Hypothèses métier
FALSE_NEGATIVE_COST = float(os.getenv("FALSE_NEGATIVE_COST", "10000"))
FALSE_POSITIVE_COST = float(os.getenv("FALSE_POSITIVE_COST", "500"))
MIN_RECALL = float(os.getenv("MIN_RECALL", "0.85"))
MIN_PR_AUC = float(os.getenv("MIN_PR_AUC", "0.70"))
MAX_VALIDATION_COST_PER_1000 = float(os.getenv("MAX_VALIDATION_COST_PER_1000", "250000"))

ID_COL = "engine_id"
TIME_COL = "cycle"
TARGET_COL = "failure_within_30_cycles"
RUL_COL = "RUL"

BASE_COLUMNS = [
    "engine_id", "cycle", "setting_1", "setting_2", "setting_3",
    *[f"sensor_{i}" for i in range(1, 22)],
]

# Capteurs et fenêtres pour features temporelles
ROLLING_SENSORS = [
    "sensor_2", "sensor_3", "sensor_4", "sensor_7", "sensor_11",
    "sensor_12", "sensor_15", "sensor_17", "sensor_20", "sensor_21",
]
ROLLING_WINDOWS = [5, 10, 20]

# Colonnes interdites pour éviter la fuite de données
FORBIDDEN_MODEL_COLUMNS = {
    ID_COL,
    TARGET_COL,
    RUL_COL,
    "max_cycle",
    "max_observed_cycle",
    "RUL_at_last_observation",
}
