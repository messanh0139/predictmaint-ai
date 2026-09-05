from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

logger = logging.getLogger(__name__)


class MongoDBLoader:
    """Charge les données brutes dans MongoDB"""

    def __init__(self, mongo_url: str, db_name: str = "predictmaint"):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]

    def load_raw_data(self, data: pd.DataFrame, collection_name: str = "raw_data"):
        """Charge les données depuis un DataFrame vers MongoDB"""
        logger.info(f"Chargement de {len(data)} lignes dans MongoDB collection {collection_name}")

        self.db[collection_name].drop()

        records = data.to_dict('records')
        result = self.db[collection_name].insert_many(records)

        logger.info(f"{len(result.inserted_ids)} documents insérés dans {collection_name}")
        return len(result.inserted_ids)

    def get_raw_data(self, collection_name: str = "raw_data") -> pd.DataFrame:
        """Récupère les données depuis MongoDB"""
        logger.info(f"Récupération depuis MongoDB collection {collection_name}")

        cursor = self.db[collection_name].find({}, {"_id": 0})
        data = list(cursor)

        if not data:
            logger.warning(f"Collection {collection_name} vide")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        logger.info(f"{len(df)} lignes récupérées")
        return df

    def close(self):
        self.client.close()


if __name__ == "__main__":
    extraction_path = Path(__file__).parent.parent / "extraction" / "load.py"
    spec = importlib.util.spec_from_file_location("load", extraction_path)
    load_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(load_module)
    load_train_fd001 = load_module.load_train_fd001

    mongo_url = os.getenv("MONGODB_URL", "mongodb://admin:admin123@localhost:27017/")
    loader = MongoDBLoader(mongo_url)

    train_data = load_train_fd001()
    count = loader.load_raw_data(train_data, collection_name="train_raw")

    logger.info(f"Chargement terminé: {count} documents dans MongoDB")
    loader.close()
