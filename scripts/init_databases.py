#!/usr/bin/env python3
"""Initialisation des bases de données MongoDB et PostgreSQL"""

import importlib.util
import logging
import os
import sys
import traceback
from pathlib import Path

from pymongo import MongoClient
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

extraction_path = PROJECT_ROOT / "pipelines" / "1_etl_ingestion" / "extraction" / "load.py"
spec = importlib.util.spec_from_file_location("load", extraction_path)
load_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load_module)
load_train_fd001 = load_module.load_train_fd001

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def init_mongodb():
    """Charge les données brutes dans MongoDB"""
    logger.info("Initialisation de MongoDB")

    mongo_url = os.getenv("MONGODB_URL", "mongodb://admin:admin123@localhost:27017/")
    client = MongoClient(mongo_url)
    db = client["predictmaint"]

    logger.info("Chargement des données brutes depuis storage/raw/")
    train_data = load_train_fd001()

    db["train_raw"].drop()

    records = train_data.to_dict('records')
    result = db["train_raw"].insert_many(records)

    logger.info(f"MongoDB: {len(result.inserted_ids)} documents insérés dans train_raw")
    client.close()


def init_postgresql():
    """Crée les tables vides dans PostgreSQL"""
    logger.info("Initialisation de PostgreSQL")

    db_url = os.getenv("POSTGRESQL_URL", "postgresql://postgres:postgres@localhost:5433/predictmaint")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS train_features CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS calibration_features CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS val_features CASCADE"))
        conn.commit()

    logger.info("PostgreSQL: Tables prêtes")
    engine.dispose()


def main():
    """Initialise les deux bases de données"""
    logger.info("Initialisation des bases de données")

    try:
        init_mongodb()
        init_postgresql()
        logger.info("Initialisation terminée avec succès")
        logger.info("")
        logger.info("Prochaines étapes:")
        logger.info("1. Lancer la transformation: USE_DATABASES=1 python -m src.data.prepare")
        logger.info("2. Vérifier PostgreSQL: psql -h localhost -U postgres -d predictmaint -c '\\dt'")
        logger.info("3. Ou utiliser le DAG Airflow pipeline_1_etl_ingestion")

    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
