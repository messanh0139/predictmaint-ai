# Guide de Démarrage Rapide

Ce guide vous permet de démarrer rapidement le système complet de maintenance prédictive avec tous ses composants MLOps.

## Prérequis

- **Docker** et **Docker Compose** installés
- **Python 3.11+** (pour développement local)
- **Node.js 18+** (pour le frontend React)
- **Git** pour le versioning
- Au moins **8 GB de RAM** disponible
- **Google Cloud Platform** (optionnel, pour le stockage cloud des modèles)

## Installation Rapide (Docker Compose)

### 1. Cloner le repository

```bash
git clone <votre-repo>
cd predictmaint-ai
```

### 2. Configuration des variables d'environnement

Créer un fichier **.env** à la racine :

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre_password_securise
POSTGRES_DB=predictmaint

# MongoDB
MONGO_PASSWORD=votre_password_mongodb

# GCP (optionnel)
GCP_PROJECT_ID=votre-project-id
GCP_BUCKET=votre-bucket-models

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
```

### 3. Lancer tous les services

```bash
cd infrastructure/deployment
docker-compose up -d
```

Cette commande démarre :
- MongoDB (données brutes)
- PostgreSQL (données propres)
- Apache Airflow (orchestration)
- MLflow (tracking)
- API FastAPI (inférence)
- Dashboard React (interface)
- Prometheus + Grafana + cAdvisor (monitoring)

### 4. Vérifier que tous les services sont lancés

```bash
docker-compose ps
```

Tous les services doivent être dans l'état **Up** (healthy).

### 5. Accéder aux interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dashboard React** | http://localhost:3002 | Aucun |
| **API Documentation** | http://localhost:8001/docs | Aucun |
| **Airflow** | http://localhost:8081 | admin / admin |
| **MLflow** | http://localhost:5001 | Aucun |
| **Grafana** | http://localhost:3001 | admin / admin |
| **Prometheus** | http://localhost:9090 | Aucun |

---

## Utilisation des Pipelines

### Pipeline 1 : ETL & Ingestion

**Objectif** : Extraire, transformer et charger les données dans PostgreSQL.

```bash
# Exécution manuelle du pipeline
python -m src.data.prepare
```

Ou via Airflow :
1. Accéder à http://localhost:8081
2. Activer le DAG **pipeline_1_etl_ingestion**
3. Déclencher manuellement ou attendre la planification (@daily)

### Pipeline 2 : Training & MLOps

**Objectif** : Entraîner des modèles, optimiser et sélectionner le champion.

```bash
# Sélection des features (sur TRAIN uniquement)
python -m src.features.select_features

# Entraînement de base
python -m src.models.train

# Optimisation hyperparamètres
python -m src.models.optimize

# Évaluation sur holdout (certification externe, hors boucle de retrain)
python -m src.models.evaluate
```

Ou via Airflow :
1. Activer le DAG **pipeline_2_training_mlops**
2. Ce pipeline attend automatiquement la fin du Pipeline 1
3. Planification : @weekly

### Pipeline 3 : Inférence & Interface

**L'API et le dashboard démarrent automatiquement** avec Docker Compose.

**Tester l'API manuellement** :

```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 1,
    "history": [
      {
        "cycle": 1,
        "setting_1": 0.0,
        "setting_2": 0.0,
        "setting_3": 100.0,
        "sensor_1": 518.67,
        "sensor_2": 641.82
      }
    ]
  }'
```

---

## Développement Local

### Frontend React

```bash
cd pipelines/3_inference_ihm/frontend
npm install
npm start
```

Le dashboard sera accessible sur http://localhost:3000

### API FastAPI

```bash
cd pipelines/3_inference_ihm/api
pip install -r requirements-api.txt
uvicorn main:app --reload
```

L'API sera accessible sur http://localhost:8001

### Tests

```bash
# Installer les dépendances de dev
pip install -r infrastructure/requirements-dev.txt

# Lancer les tests
pytest tests/ -v
```

---

## Monitoring

### Grafana

1. Accéder à http://localhost:3001
2. Login : **admin** / **admin**
3. Dashboards préconfigurés :
   - **MLOps Overview** : Vue d'ensemble du système
   - **Model Performance** : Métriques des modèles
   - **Infrastructure** : Métriques conteneurs et bases de données

### Prometheus

Accéder à http://localhost:9090 pour :
- Explorer les métriques brutes
- Tester des requêtes PromQL
- Vérifier les cibles (targets)

### MLflow

Accéder à http://localhost:5001 pour :
- Comparer les expérimentations
- Visualiser les métriques d'entraînement
- Télécharger les artefacts de modèles

---

## Workflows Complets

### Workflow 1 : Entraînement Complet

```bash
# 1. Préparer les données
python -m src.data.prepare

# 2. Sélectionner les features (sur TRAIN uniquement)
python -m src.features.select_features

# 3. Entraîner plusieurs modèles
python -m src.models.train

# 4. Optimiser le meilleur
python -m src.models.optimize

# 5. Évaluer sur holdout (certification externe, hors boucle de retrain)
python -m src.models.evaluate

# 6. Vérifier dans MLflow
open http://localhost:5001
```

### Workflow 2 : Prédiction Interactive

1. Accéder au dashboard : http://localhost:3002
2. Sélectionner un moteur dans l'onglet "Démonstration prédictive"
3. Ajuster le cycle avec le slider
4. Cliquer sur "Analyser le risque"
5. Visualiser la prédiction (HIGH / LOW)
6. (Optionnel) Enregistrer le feedback terrain

### Workflow 3 : Réentraînement Automatique

1. Accéder au dashboard : http://localhost:3002
2. Onglet "Réentraînement automatique"
3. Télécharger l'exemple CSV
4. Upload le fichier avec de nouvelles données
5. Le pipeline se déclenche automatiquement
6. Suivre l'avancement dans l'interface
7. Le nouveau modèle champion est déployé automatiquement

---

## Troubleshooting

### Les conteneurs ne démarrent pas

```bash
# Vérifier les logs
docker-compose logs <service-name>

# Exemples :
docker-compose logs api
docker-compose logs airflow-webserver
docker-compose logs postgresql
```

### Problèmes de permissions

```bash
# Donner les permissions sur les volumes
sudo chown -R $USER:$USER storage/
sudo chown -R $USER:$USER orchestration/airflow/logs/
```

### L'API ne trouve pas le modèle

```bash
# Vérifier que le modèle existe
ls storage/models/production/

# Lancer un entraînement si nécessaire
python -m src.models.train
```

### Airflow : DAG non visible

1. Vérifier les erreurs de syntaxe Python dans le DAG
2. Vérifier les logs : **docker-compose logs airflow-scheduler**
3. Rafraîchir la liste des DAGs dans l'interface Airflow

### Dashboard React : Erreur de connexion API

```bash
# Vérifier que l'API est accessible
curl http://localhost:8001/health

# Vérifier les variables d'environnement React
cat pipelines/3_inference_ihm/frontend/.env
```

---

## Arrêter les Services

```bash
# Arrêter tous les conteneurs
cd infrastructure/deployment
docker-compose down

# Arrêter et supprimer les volumes (les données seront perdues)
docker-compose down -v
```

---

## Prochaines Étapes

1. **Personnaliser les hyperparamètres** : Modifier **src/config.py**
2. **Ajouter des modèles** : Étendre **src/models/pipelines.py**
3. **Configurer GCP** : Suivre **infrastructure/deployment/gcp/**
4. **Créer des dashboards Grafana** : Personnaliser **infrastructure/monitoring/grafana/**
5. **Automatiser avec CI/CD** : Configurer **.github/workflows/**

---

## Documentation

- **Architecture complète** : [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Documentation** : http://localhost:8001/docs
- **Airflow Documentation** : https://airflow.apache.org/
- **MLflow Documentation** : https://mlflow.org/
- **React Documentation** : https://react.dev/

---

## Support

Pour toute question ou problème :
1. Consulter la documentation complète dans **ARCHITECTURE.md**
2. Vérifier les logs des conteneurs
3. Consulter les issues GitHub du projet
