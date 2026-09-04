# PredictMaint AI : Maintenance Prédictive MLOps

## Architecture MLOps Professionnelle

Ce projet implémente un système complet de maintenance prédictive suivant les meilleures pratiques MLOps. L'architecture repose sur trois pipelines fonctionnels orchestrés par Apache Airflow, avec un système de monitoring et de déploiement continu en production.

## Stack Technique Globale

| Composant | Technologies |
|-----------|-------------|
| **Orchestration** | Apache Airflow (DAGs, planification, gestion des dépendances) |
| **Stockage & Ingestion** | MongoDB (données brutes), PostgreSQL (données propres), GCP Cloud Storage |
| **Traitement & Modélisation** | Python (Pandas, Scikit-learn, XGBoost, PyTorch) |
| **MLOps & Registry** | MLflow (Tracking expérimentations), GCP Cloud Storage |
| **API & Interface (IHM)** | FastAPI (Backend d'inférence), React/Streamlit (Dashboard interactif) |
| **Supervision & Monitoring** | Prometheus, Grafana, cAdvisor (métriques conteneurs & bases de données) |

## Architecture du Projet

```text
predictmaint-ai/
├── pipelines/                           # Les 3 pipelines fonctionnels
│   ├── 1_etl_ingestion/                # Pipeline 1: Extraction, Transformation, Loading
│   │   ├── extraction/                  # Connexion sources externes, APIs
│   │   ├── transformation/              # Nettoyage, feature engineering Python
│   │   └── loading/                     # Injection PostgreSQL
│   │
│   ├── 2_training_mlops/               # Pipeline 2: Entraînement & MLOps
│   │   ├── experimentation/             # Comparaison modèles (Logistic, RF, XGBoost)
│   │   ├── optimization/                # Ajustement hyperparamètres (Optuna)
│   │   └── registry/                    # Tracking MLflow + Stockage GCP
│   │
│   └── 3_inference_ihm/                # Pipeline 3: Inférence & Interface
│       ├── api/                         # FastAPI - Chargement modèle GCP
│       └── frontend/                    # React/Streamlit - Visualisation KPIs
│
├── orchestration/                       # Orchestration globale
│   └── airflow/
│       ├── dags/                        # DAGs Airflow (Pipeline 1 vers 2)
│       ├── plugins/                     # Plugins personnalisés
│       └── config/                      # Configuration Airflow
│
├── storage/                             # Stockage centralisé
│   ├── raw/                             # Données brutes (MongoDB/Data Lake)
│   ├── processed/                       # Données propres (PostgreSQL)
│   └── models/                          # Artefacts modèles (local + GCP)
│
├── infrastructure/                      # Infrastructure & Monitoring
│   ├── monitoring/                      # Prometheus, Grafana, cAdvisor
│   │   ├── prometheus/                  # Configuration Prometheus
│   │   ├── grafana/                     # Dashboards Grafana
│   │   ├── drift.py                     # Monitoring dérive données
│   │   └── performance.py               # Monitoring performance modèles
│   │
│   ├── deployment/                      # Déploiement & Conteneurisation
│   │   ├── docker-compose.yml           # Orchestration services
│   │   ├── Dockerfile.api               # Image API
│   │   ├── Dockerfile.dashboard         # Image Dashboard
│   │   ├── Dockerfile.mlflow            # Image MLflow
│   │   ├── Dockerfile.grafana           # Image Grafana
│   │   └── cloudbuild.yaml              # CI/CD GCP
│   │
│   ├── tests/                           # Tests unitaires & intégration
│   └── scripts/                         # Scripts utilitaires
│
├── docs/                                # Documentation projet
├── notebooks/                           # Analyses exploratoires
├── mlruns/                              # Runs MLflow locaux
├── .github/workflows/                   # CI/CD GitHub Actions
├── requirements*.txt                    # Dépendances Python
├── .env.example                         # Variables d'environnement
└── README.md                            # Ce fichier
```

## Les 3 Pipelines Fonctionnels

### Pipeline 1: ETL/Ingestion

**Objectif**: Centraliser la collecte des données brutes, garantir la traçabilité et préparer des données propres pour la modélisation.

- **Extraction** (`pipelines/1_etl_ingestion/extraction/`): Connexion aux sources externes (APIs, bases transactionnelles, fichiers plats)
- **Stockage Brut**: Persistance immédiate dans MongoDB ou Data Lake (MinIO/S3) sans transformation
- **Transformation** (`pipelines/1_etl_ingestion/transformation/`): Scripts Python orchestrés par Airflow pour nettoyage, gestion valeurs manquantes, feature engineering
- **Chargement** (`pipelines/1_etl_ingestion/loading/`): Injection données tabulaires propres dans PostgreSQL

**DAG Airflow**: `orchestration/airflow/dags/pipeline_1_etl.py`

### Pipeline 2: Training & MLOps

**Objectif**: Automatiser l'apprentissage itératif, comparer rigoureusement plusieurs modèles et versionner le meilleur artefact.

- **Extraction Data**: Requêtage PostgreSQL pour extraire datasets d'entraînement/test
- **Expérimentation comparative** (`pipelines/2_training_mlops/experimentation/`):
  - Entraînement/évaluation d'au moins 3 modèles distincts (Logistic Regression, Random Forest, XGBoost)
- **Ajustement hyperparamètres** (`pipelines/2_training_mlops/optimization/`):
  - Optimisation fine via Grid Search, Random Search ou Optuna
- **Tracking & Sélection** (`pipelines/2_training_mlops/registry/`):
  - Enregistrement paramètres, métriques (Accuracy, F1-Score, MSE) via MLflow
  - Sélection automatique du modèle champion
- **Stockage Model**: Exportation artefact vers GCP Cloud Storage

**DAG Airflow**: `orchestration/airflow/dags/pipeline_2_mlops.py`

### Pipeline 3: Inférence & Interface Utilisateur

**Objectif**: Exposer le modèle ML sous forme de service web et offrir un outil de visualisation.

- **API d'Inférence** (`pipelines/3_inference_ihm/api/`):
  - FastAPI charge le modèle optimal depuis GCP au démarrage
  - Traite les requêtes de prédiction en temps réel
- **Tableau de Bord** (`pipelines/3_inference_ihm/frontend/`):
  - Interface interactive React/Streamlit
  - Soumission données et visualisation résultats (graphiques, KPIs)

## Supervision, Orchestration et Infrastructure

### Orchestration globale

**Apache Airflow** (`orchestration/airflow/`) pilote l'enchaînement séquentiel et conditionnel des DAGs:
- Pipeline 1 (ETL) puis Pipeline 2 (MLOps)
- Gestion des erreurs, alertes et relances automatiques

### Monitoring des conteneurs

**cAdvisor** collecte en continu l'utilisation des ressources:
- CPU, mémoire, réseau de chaque conteneur Docker

### Collecte et Visualisation

- **Prometheus** (`infrastructure/monitoring/prometheus/`): Centralise métriques cAdvisor et bases de données
- **Grafana** (`infrastructure/monitoring/grafana/`): Tableaux de bord de supervision unifiés pour contrôler la santé globale en temps réel

## Modèles Comparés

Comparaison des modèles sur ensemble de validation verrouillé:

| Modèle | Precision | Recall | F1-Score | ROC-AUC | PR-AUC | Coût métier |
|--------|-----------|--------|----------|---------|--------|-------------|
| Logistic Regression | 0.594 | 0.974 | 0.738 | 0.989 | 0.958 | 275 000 |
| Random Forest | 0.658 | 0.976 | 0.786 | 0.989 | 0.949 | 228 000 |
| XGBoost (défaut) | 0.598 | 0.976 | 0.742 | 0.989 | 0.949 | 262 500 |
| **XGBoost optimisé (Optuna)** | 0.564 | **1.000** | 0.721 | 0.988 | 0.946 | **180 000** |

**Champion retenu**: XGBoost optimisé (recall 100%, coût métier minimal)

## Installation et Démarrage

### Prérequis

- Python 3.11+
- Docker et Docker Compose
- Git

### 1. Cloner le dépôt

```bash
git clone https://github.com/messanh0139/predictmaint-ai.git
cd predictmaint-ai
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
```

### 3. Lancer la stack complète

```bash
cd infrastructure/deployment
docker compose up --build -d
```

Cette commande lance:
- MongoDB (port 27017)
- PostgreSQL (port 5432)
- MLflow (port 5000)
- API FastAPI (port 8000)
- Dashboard Streamlit (port 8501)
- Airflow Webserver (port 8080)
- Prometheus (port 9090)
- Grafana (port 3000)
- cAdvisor (port 8082)

### 4. Accéder aux services

| Service | URL | Identifiants |
|---------|-----|--------------|
| API REST | http://localhost:8000 | aucun |
| Documentation API (Swagger) | http://localhost:8000/docs | aucun |
| Dashboard Streamlit | http://localhost:8501 | aucun |
| MLflow UI | http://localhost:5000 | aucun |
| Airflow Webserver | http://localhost:8080 | admin / admin |
| Prometheus | http://localhost:9090 | aucun |
| Grafana | http://localhost:3000 | admin / admin |
| cAdvisor | http://localhost:8082 | aucun |

### 5. Arrêter les services

```bash
cd infrastructure/deployment
docker compose down
```

## Utilisation

### Lancer un pipeline ETL (Pipeline 1)

Via l'interface Airflow (http://localhost:8080):
1. Activer le DAG `pipeline_1_etl_ingestion`
2. Déclencher manuellement ou attendre l'exécution planifiée

### Entraîner des modèles (Pipeline 2)

Via l'interface Airflow:
1. Attendre la fin du Pipeline 1
2. Le Pipeline 2 se déclenche automatiquement
3. Suivre l'avancement dans MLflow (http://localhost:5000)

### Faire des prédictions (Pipeline 3)

Via le Dashboard (http://localhost:8501):
1. Onglet "Démonstration prédictive"
2. Sélectionner un moteur et un cycle
3. Cliquer sur "Analyser le risque"

Via l'API:
```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 1,
    "cycle": 150,
    "sensors": {...}
  }'
```

### Surveiller le système

Grafana (http://localhost:3000):
- Métriques conteneurs (CPU, mémoire)
- Performances bases de données
- Métriques modèles ML

## Tests

```bash
# Depuis la racine du projet
pytest infrastructure/tests/ -v --cov
```

## CI/CD

Le workflow GitHub Actions (`.github/workflows/deploy.yml`) se déclenche à chaque push sur `main`:

1. Tests unitaires et linting
2. Construction images Docker
3. Déploiement sur GCP Cloud Run
4. Smoke tests production

## Documentation

La documentation complète du projet se trouve dans le dossier `docs/` avec:
- Architecture détaillée
- Choix technologiques
- Data leakage prevention
- Model card
- Déploiement GCP

## Notebooks

| Notebook | Contenu |
|----------|---------|
| `01_eda.ipynb` | Analyse exploratoire, qualité données |
| `02_feature_engineering.ipynb` | Features temporelles causales |
| `03_feature_selection.ipynb` | Sélection variables |
| `04_model_training.ipynb` | Entraînement comparatif modèles |
| `05_model_evaluation.ipynb` | Optimisation et évaluation |
| `06_monitoring.ipynb` | PSI, drift, performance |

## Contributeur

Messanh Yaovi KODJO — kmessanhyaovi@gmail.com

## Licence

Ce projet est sous licence MIT.
