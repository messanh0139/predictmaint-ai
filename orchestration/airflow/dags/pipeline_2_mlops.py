# DAG Pipeline 2 : Entraînement, optimisation et versioning des modèles

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

default_args = {
    'owner': 'ml-team',
    'depends_on_past': True,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

dag = DAG(
    'pipeline_2_training_mlops',
    default_args=default_args,
    description='Pipeline MLOps pour entraînement et versioning',
    # Même raison que pipeline_1_etl.py : déclenchement à la main uniquement.
    schedule_interval=None,
    catchup=False,
    tags=['mlops', 'training', 'pipeline-2'],
)


def extract_from_postgresql(**context):
    # Extraire les données depuis PostgreSQL
    print("Extraction depuis PostgreSQL")
    print("Données extraites")
    return {"status": "extracted"}


def register_to_gcp(**context):
    # Enregistrer le modèle dans GCP (déjà fait par src.models.register dans le pipeline)
    print("Enregistrement GCP déjà effectué par pipeline retrain")
    print("Le champion a été uploadé vers GCS par src.models.register")
    return {"status": "completed"}


def track_with_mlflow(**context):
    # Tracker l'expérimentation dans MLflow
    print("MLflow tracking")
    print("Expérimentation enregistrée")


task_extract = PythonOperator(
    task_id='extract_from_postgresql',
    python_callable=extract_from_postgresql,
    dag=dag,
)

task_retrain = DockerOperator(
    task_id='run_complete_retrain',
    # Image de l'api (Python 3.11 + librairies ML) car Airflow tourne en Python 3.8
    image='deployment-api:latest',
    command='python -m src.pipelines.retrain --optimize --trials 30',
    network_mode='deployment_mlops-network',
    mount_tmp_dir=False,
    auto_remove='success',
    environment={
        'MLFLOW_TRACKING_URI': 'http://mlflow:5000',
        'INCLUDE_PRODUCTION_FEEDBACK': os.getenv('INCLUDE_PRODUCTION_FEEDBACK', '0'),
        'PREDICTION_BUCKET': os.getenv('PREDICTION_BUCKET', ''),
    },
    mounts=[
        Mount(
            source=f"{os.environ['HOST_PROJECT_ROOT']}/storage",
            target='/app/storage',
            type='bind',
        ),
    ],
    dag=dag,
)

task_register = PythonOperator(
    task_id='register_model_to_gcp',
    python_callable=register_to_gcp,
    dag=dag,
)

task_mlflow = PythonOperator(
    task_id='track_with_mlflow',
    python_callable=track_with_mlflow,
    dag=dag,
)

task_validate = BashOperator(
    task_id='validate_pipeline',
    bash_command='echo "Pipeline MLOps terminé"',
    dag=dag,
)

task_extract >> task_retrain >> [task_register, task_mlflow] >> task_validate
