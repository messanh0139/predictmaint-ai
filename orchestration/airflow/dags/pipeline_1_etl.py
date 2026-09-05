"""Pipeline ETL pour extraction, transformation et chargement des données"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

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


def extract_to_mongodb(**context):
    """Charge les données brutes dans MongoDB"""
    sys.path.insert(0, str(Path('/opt/airflow')))

    etl_path = Path('/opt/airflow/pipelines/1_etl_ingestion')

    spec = importlib.util.spec_from_file_location(
        "load_to_mongodb",
        etl_path / "loading/load_to_mongodb.py"
    )
    mongodb_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mongodb_module)
    MongoDBLoader = mongodb_module.MongoDBLoader

    spec = importlib.util.spec_from_file_location(
        "load",
        etl_path / "extraction/load.py"
    )
    load_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(load_module)
    load_train_fd001 = load_module.load_train_fd001

    mongo_url = os.getenv("MONGODB_URL", "mongodb://admin:admin123@mongodb:27017/")
    loader = MongoDBLoader(mongo_url)

    train_data = load_train_fd001()
    count = loader.load_raw_data(train_data, collection_name="train_raw")
    loader.close()

    print(f"MongoDB: {count} documents insérés")
    return {"count": count}


task_extract = PythonOperator(
    task_id='extract_to_mongodb',
    python_callable=extract_to_mongodb,
    dag=dag,
)

task_prepare = BashOperator(
    task_id='prepare_transform_load',
    bash_command='cd /opt/airflow && USE_DATABASES=1 python -m src.data.prepare',
    env={
        'USE_DATABASES': '1',
        'MONGODB_URL': 'mongodb://admin:admin123@mongodb:27017/',
        'POSTGRESQL_URL': 'postgresql://postgres:postgres@postgresql:5432/predictmaint',
    },
    dag=dag,
)

task_validate = BashOperator(
    task_id='validate_pipeline',
    bash_command='echo "Pipeline ETL terminé - MongoDB puis Transformation puis PostgreSQL"',
    dag=dag,
)

task_extract >> task_prepare >> task_validate
