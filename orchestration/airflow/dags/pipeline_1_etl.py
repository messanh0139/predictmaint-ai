# DAG Pipeline 1 : Extraction, transformation et chargement des données

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.1_etl_ingestion.extraction.load import load_train_fd001
from pipelines.1_etl_ingestion.loading.load_to_postgresql import PostgreSQLLoader
from pipelines.1_etl_ingestion.transformation.build_features import build_causal_features
from pipelines.1_etl_ingestion.transformation.prepare import main as prepare_pipeline

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'pipeline_1_etl_ingestion',
    default_args=default_args,
    description='Pipeline ETL pour maintenance prédictive',
    schedule_interval='@daily',
    catchup=False,
    tags=['etl', 'ingestion', 'pipeline-1'],
)


def extract_data(**context):
    # Extraire les données brutes
    print("Extraction des données")
    data = load_train_fd001()
    print(f"{len(data)} enregistrements extraits")
    return {"records": len(data)}


def transform_data(**context):
    # Transformer et nettoyer les données
    print("Transformation des données")
    prepare_pipeline()
    print("Données transformées et sauvegardées")
    return {"status": "completed"}


def load_to_postgresql(**context):
    # Charger les données dans PostgreSQL
    print("Chargement PostgreSQL")
    db_url = os.getenv("POSTGRESQL_URL", "postgresql://user:password@localhost:5432/predictmaint")

    loader = PostgreSQLLoader(db_url)
    processed_path = Path("storage/processed/train.csv")

    if not processed_path.exists():
        raise FileNotFoundError(f"Fichier non trouvé: {processed_path}")

    count = loader.load_processed_data(processed_path)
    print(f"{count} enregistrements chargés")
    return {"loaded_records": count}


task_extract = PythonOperator(
    task_id='extract_raw_data',
    python_callable=extract_data,
    dag=dag,
)

task_transform = PythonOperator(
    task_id='transform_clean_data',
    python_callable=transform_data,
    dag=dag,
)

task_load = PythonOperator(
    task_id='load_to_postgresql',
    python_callable=load_to_postgresql,
    dag=dag,
)

task_validate = BashOperator(
    task_id='validate_pipeline',
    bash_command='echo "Pipeline ETL terminé"',
    dag=dag,
)

task_extract >> task_transform >> task_load >> task_validate
