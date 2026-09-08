"""Pipeline ETL pour extraction, transformation et chargement des données"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

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
    # Pas de planning : la machine ne tourne pas en continu, on déclenche à la main
    schedule_interval=None,
    catchup=False,
    tags=['etl', 'ingestion', 'pipeline-1'],
)


HOST_PROJECT_ROOT = os.environ['HOST_PROJECT_ROOT']
STORAGE_MOUNT = Mount(
    source=f"{HOST_PROJECT_ROOT}/storage",
    target='/app/storage',
    type='bind',
)

# Ces deux tâches tournent dans l'image de l'api, pas dans Airflow (dépendances manquantes)
task_extract = DockerOperator(
    task_id='extract_to_mongodb',
    image='deployment-api:latest',
    # load_to_mongodb.py peut être lancé tel quel, il lit MONGODB_URL et charge les données
    command='python pipelines/1_etl_ingestion/loading/load_to_mongodb.py',
    working_dir='/app',
    network_mode='deployment_mlops-network',
    mount_tmp_dir=False,
    auto_remove='success',
    environment={
        # Le dossier commence par un chiffre, "python -m" ne marche pas, d'où PYTHONPATH
        'PYTHONPATH': '/app',
        # Par défaut le script cherche MongoDB sur localhost, ici il faut le nom du service
        'MONGODB_URL': 'mongodb://admin:admin123@mongodb:27017/',
    },
    mounts=[
        STORAGE_MOUNT,
        # Ce dossier n'est pas copié dans l'image de l'api, on le monte à part.
        Mount(
            source=f"{HOST_PROJECT_ROOT}/pipelines/1_etl_ingestion",
            target='/app/pipelines/1_etl_ingestion',
            type='bind',
        ),
    ],
    dag=dag,
)

task_prepare = DockerOperator(
    task_id='prepare_transform_load',
    image='deployment-api:latest',
    command='python -m src.data.prepare',
    working_dir='/app',
    network_mode='deployment_mlops-network',
    mount_tmp_dir=False,
    auto_remove='success',
    environment={'USE_DATABASES': '1'},
    mounts=[STORAGE_MOUNT],
    dag=dag,
)

task_validate = BashOperator(
    task_id='validate_pipeline',
    bash_command='echo "Pipeline ETL terminé - MongoDB puis Transformation puis PostgreSQL"',
    dag=dag,
)

# Déclenche pipeline_2 directement : en mode manuel, un capteur qui compare les dates ne marcherait pas
task_trigger_pipeline_2 = TriggerDagRunOperator(
    task_id='trigger_pipeline_2',
    trigger_dag_id='pipeline_2_training_mlops',
    dag=dag,
)

task_extract >> task_prepare >> task_validate >> task_trigger_pipeline_2
