from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


class PostgreSQLLoader:
    # Charge les données transformées dans PostgreSQL

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)

    def load_processed_data(self, data_path: Path, table_name: str = "predictive_maintenance"):
        # Charge les données depuis CSV ou Parquet vers PostgreSQL
        logger.info(f"Chargement depuis {data_path}")

        if data_path.suffix == '.csv':
            df = pd.read_csv(data_path)
        elif data_path.suffix == '.parquet':
            df = pd.read_parquet(data_path)
        else:
            raise ValueError(f"Format non supporté: {data_path.suffix}")

        df.to_sql(
            table_name,
            self.engine,
            if_exists='replace',
            index=False,
            method='multi',
            chunksize=1000
        )

        logger.info(f"{len(df)} lignes chargées dans {table_name}")
        return len(df)


if __name__ == "__main__":
    db_url = os.getenv("POSTGRESQL_URL", "postgresql://user:password@localhost:5432/predictmaint")
    loader = PostgreSQLLoader(db_url)

    processed_path = Path("storage/processed/train.csv")
    if processed_path.exists():
        loader.load_processed_data(processed_path)
