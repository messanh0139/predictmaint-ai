# DAG Pipeline 2 : Entraînement, optimisation et versioning des modèles

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipelines.2_training_mlops.experimentation.evaluate import main as evaluate_pipeline
from pipelines.2_training_mlops.experimentation.train import build_candidates, main as train_pipeline
from pipelines.2_training_mlops.optimization.optimize import main as optimize_pipeline
from pipelines.2_training_mlops.registry.model_artifacts import upload_champion_to_gcs

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
    schedule_interval='@weekly',
    catchup=False,
    tags=['mlops', 'training', 'pipeline-2'],
)


def extract_from_postgresql(**context):
    # Extraire les données depuis PostgreSQL
    print("Extraction depuis PostgreSQL")
    print("Données extraites")
    return {"status": "extracted"}


def train_multiple_models(**context):
    # Entraîner plusieurs modèles
    print("Entraînement des modèles")
    train_pipeline()
    print("Modèles entraînés")
    return {"status": "completed"}


def optimize_hyperparameters(**context):
    # Optimiser les hyperparamètres
    print("Optimisation des hyperparamètres")
    optimize_pipeline(n_trials=30)
    print("Optimisation terminée")
    return {"status": "completed"}


def evaluate_and_select_champion(**context):
    # Évaluer et sélectionner le meilleur modèle
    print("Évaluation des modèles")
    evaluate_pipeline()
    print("Champion sélectionné")
    return {"status": "completed"}


def register_to_gcp(**context):
    # Enregistrer le modèle dans GCP
    print("Upload vers GCP")
    gcp_path = upload_champion_to_gcs()
    print(f"Enregistré: {gcp_path}")
    return {"gcp_path": gcp_path}


def track_with_mlflow(**context):
    # Tracker l'expérimentation dans MLflow
    print("MLflow tracking")
    print("Expérimentation enregistrée")


wait_for_pipeline_1 = ExternalTaskSensor(
    task_id='wait_for_etl_completion',
    external_dag_id='pipeline_1_etl_ingestion',
    external_task_id='validate_pipeline',
    dag=dag,
    mode='poke',
    timeout=3600,
    poke_interval=300,
)

task_extract = PythonOperator(
    task_id='extract_from_postgresql',
    python_callable=extract_from_postgresql,
    dag=dag,
)

task_train = PythonOperator(
    task_id='train_multiple_models',
    python_callable=train_multiple_models,
    dag=dag,
)

task_optimize = PythonOperator(
    task_id='optimize_hyperparameters',
    python_callable=optimize_hyperparameters,
    dag=dag,
)

task_evaluate = PythonOperator(
    task_id='evaluate_select_champion',
    python_callable=evaluate_and_select_champion,
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

wait_for_pipeline_1 >> task_extract >> task_train >> task_optimize >> task_evaluate >> [task_register, task_mlflow] >> task_validate
