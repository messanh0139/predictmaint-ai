# Architecture MLOps - Maintenance Prédictive

Ce document décrit l'architecture technique complète du système de maintenance prédictive, basée sur une approche moderne MLOps intégrant ingénierie des données, automatisation et développement full-stack.

## Vue d'ensemble

Le système repose sur trois pipelines fonctionnels orchestrés par Apache Airflow, avec un écosystème complet de monitoring et de déploiement en production.

```
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE 1: ETL/INGESTION                   │
│                                                                  │
│  Sources puis MongoDB/Data Lake puis Transformation puis PostgreSQL│
│                     (brut)                             (propre)  │
└─────────────────────────────────────────────────────────────────┘
                              |
                     Apache Airflow Orchestration
                              |
┌─────────────────────────────────────────────────────────────────┐
│                  PIPELINE 2: TRAINING & MLOPS                   │
│                                                                  │
│  PostgreSQL puis Experimentation (3+ modèles) puis Optimisation │
│             puis Tracking MLflow puis Stockage GCP              │
└─────────────────────────────────────────────────────────────────┘
                              |
                     Modèle Champion
                              |
┌─────────────────────────────────────────────────────────────────┐
│              PIPELINE 3: INFERENCE & INTERFACE                  │
│                                                                  │
│  FastAPI (Backend) avec React (Frontend)                        │
│       |                                                          │
│  GCP Storage (Modèle optimal)                                   │
└─────────────────────────────────────────────────────────────────┘
                              |
┌─────────────────────────────────────────────────────────────────┐
│                  SUPERVISION & MONITORING                       │
│                                                                  │
│  cAdvisor puis Prometheus puis Grafana                          │
└─────────────────────────────────────────────────────────────────┘
```

## Stack Technique Globale

### Orchestration
- **Apache Airflow** : Planification et gestion des dépendances entre pipelines

### Stockage & Ingestion
- **MongoDB** ou **Data Lake (MinIO/S3)** : Persistance des données brutes
- **PostgreSQL** : Base de données relationnelle pour les données propres

### Traitement & Modélisation
- **Python** : Pandas, Scikit-learn, XGBoost, PyTorch

### MLOps & Registry
- **MLflow** : Tracking des expérimentations
- **Google Cloud Platform** : Stockage des artefacts modèles

### API & Interface (IHM)
- **FastAPI** : Backend d'inférence temps réel
- **React** : Interface utilisateur interactive

### Supervision & Monitoring
- **Prometheus** : Collecte et centralisation des métriques
- **Grafana** : Tableaux de bord et visualisation
- **cAdvisor** : Monitoring des conteneurs Docker

---

## Pipeline 1 : ETL et Ingestion

### Objectif
Centraliser la collecte des données brutes, garantir la traçabilité de l'historique et préparer des données propres pour la modélisation.

### Étapes

#### 1. Extraction
- Connexion aux sources externes (APIs, bases transactionnelles, fichiers plats)
- Scripts d'extraction planifiés via Airflow
- Gestion des erreurs et retry automatique

**Localisation** : `pipelines/1_etl_ingestion/extraction/`

#### 2. Stockage Brut
- Persistance immédiate dans **MongoDB** ou **Data Lake (MinIO/S3)**
- Données brutes stockées SANS transformation préalable
- Garantie de traçabilité complète de l'historique

#### 3. Transformation
- Scripts Python orchestrés par Airflow
- Nettoyage des données
- Gestion des valeurs manquantes
- Feature engineering de base

**Localisation** : `src/data/prepare.py`, `src/features/build_features.py`

#### 4. Chargement
- Injection des données tabulaires propres dans **PostgreSQL**
- Base relationnelle optimisée pour l'analyse
- Indexation pour performances

**Localisation** : `pipelines/1_etl_ingestion/loading/`

### DAG Airflow
**Fichier** : `orchestration/airflow/dags/pipeline_1_etl.py`

**Planification** : @daily

**Workflow** :
```
extract_raw_data puis transform_clean_data puis load_to_postgresql puis validate_pipeline
```

---

## Pipeline 2 : Entraînement et MLOps

### Objectif
Automatiser l'apprentissage itératif, comparer rigoureusement plusieurs architectures de modèles et versionner le meilleur artefact.

### Étapes

#### 1. Extraction Data
- Requêtage de la base PostgreSQL propre
- Extraction des datasets d'entraînement et de test
- Split train/validation/test

#### 2. Expérimentation comparative
Entraînement et évaluation d'au moins **3 modèles distincts** :
- Régression Logistique
- Random Forest
- XGBoost / Réseau de Neurones

**Localisation** : `src/models/train.py`

#### 3. Ajustement d'hyperparamètres
- Optimisation fine des performances de chaque modèle
- Techniques : Grid Search, Random Search, ou Optuna
- Validation croisée pour robustesse

**Localisation** : `src/models/optimize.py`

#### 4. Tracking & Sélection
Enregistrement dans **MLflow** :
- Paramètres de chaque expérimentation
- Métriques (Accuracy, F1-Score, MSE, PR-AUC, Recall)
- Artefacts versionnés
- Sélection automatique du modèle champion

**Localisation** : `src/models/promote.py`, `src/models/register.py`

#### 5. Stockage Model
- Exportation de l'artefact du meilleur modèle validé
- Stockage vers **GCP Cloud Storage**
- Versioning complet et traçabilité

### DAG Airflow
**Fichier** : `orchestration/airflow/dags/pipeline_2_mlops.py`

**Planification** : @weekly

**Dépendances** : Attend la fin du Pipeline 1

**Workflow** :
```
wait_for_pipeline_1 puis extract_from_postgresql puis train_multiple_models
  puis optimize_hyperparameters puis evaluate_select_champion
  puis [register_model_to_gcp, track_with_mlflow] puis validate_pipeline
```

---

## Pipeline 3 : Inférence et Interface Utilisateur

### Objectif
Exposer le modèle de Machine Learning sous forme de service web et offrir un outil de visualisation aux utilisateurs finaux.

### Composants

#### 1. API d'Inférence (FastAPI)
- Chargement du modèle optimal depuis GCP au démarrage
- Traitement des requêtes de prédiction en temps réel
- Endpoints REST :
  - `/predict` : Prédictions
  - `/health` : Health check
  - `/metrics` : Métriques Prometheus
  - `/feedback` : Collecte de feedback terrain

**Localisation** : `pipelines/3_inference_ihm/api/`

#### 2. Interface Utilisateur (React)
- Tableau de bord interactif
- Fonctionnalités :
  - Soumission de données
  - Visualisation des résultats (graphiques, KPIs)
  - Monitoring des prédictions
  - Déclenchement du réentraînement

**Localisation** : `pipelines/3_inference_ihm/frontend/`

**Technologies** :
- React 18
- Recharts (visualisations)
- Material-UI (composants)
- Axios (appels API)

---

## Supervision, Orchestration et Infrastructure

### Orchestration globale

**Apache Airflow** pilote l'enchaînement séquentiel et conditionnel des DAGs :
- Pipeline 1 (ETL) puis Pipeline 2 (MLOps)
- Gestion des erreurs
- Alertes automatiques
- Relances automatiques

**Structure** :
```
orchestration/airflow/
├── dags/           # DAGs Python
├── plugins/        # Plugins personnalisés
└── config/         # Configuration Airflow
```

### Monitoring des conteneurs

#### cAdvisor
- Collecte en continu l'utilisation des ressources :
  - CPU
  - Mémoire
  - Réseau
  - Disque
- Par conteneur Docker

#### Prometheus
- Centralise les métriques :
  - cAdvisor (conteneurs)
  - Bases de données (PostgreSQL, MongoDB)
  - API FastAPI
- Stockage time-series
- Système d'alerting

**Configuration** : `infrastructure/monitoring/prometheus/prometheus.yml`

#### Grafana
- Tableaux de bord unifiés
- Visualisation en temps réel
- Alertes visuelles
- Dashboards :
  - Vue d'ensemble infrastructure
  - Performances bases de données
  - Métriques modèles ML
  - État conteneurs Docker

**Configuration** : `infrastructure/monitoring/grafana/`

### Déploiement

#### Docker Compose
Orchestration des services :
1. MongoDB (données brutes)
2. PostgreSQL (données propres)
3. PostgreSQL Airflow (métadonnées)
4. MLflow (tracking)
5. API FastAPI (inférence)
6. Dashboard React (frontend)
7. Airflow Webserver
8. Airflow Scheduler
9. Prometheus
10. Grafana
11. cAdvisor

**Fichier** : `infrastructure/deployment/docker-compose.yml`

#### Dockerfiles
- `Dockerfile.api` : Image API FastAPI
- `Dockerfile.dashboard` : Image React (build multi-stage avec nginx)
- `Dockerfile.mlflow` : Image MLflow
- `Dockerfile.grafana` : Image Grafana personnalisée

#### CI/CD
- GitHub Actions (`.github/workflows/`)
- Cloud Build GCP (`cloudbuild.yaml`)

---

## Flux de données complet

```
1. Sources externes
     ↓
2. Extraction vers MongoDB/Data Lake (brut)
     ↓
3. Transformation Python (orchestrée par Airflow)
     ↓
4. PostgreSQL (propre)
     ↓
5. Entraînement comparatif (3+ modèles)
     ↓
6. Optimisation hyperparamètres (Optuna)
     ↓
7. Tracking MLflow + Sélection champion
     ↓
8. Stockage GCP Cloud Storage
     ↓
9. API FastAPI charge modèle
     ↓
10. Dashboard React affiche prédictions
     ↓
11. Prometheus/Grafana monitore tout
```

---

## Technologies et versions

| Couche | Technologies |
|--------|--------------|
| Orchestration | Apache Airflow 2.8.1 |
| Stockage brut | MongoDB 7.0, MinIO/S3 |
| Stockage propre | PostgreSQL 16 |
| Traitement | Python 3.11, Pandas, NumPy |
| ML | Scikit-learn, XGBoost, PyTorch |
| MLOps | MLflow, Optuna |
| API | FastAPI, Uvicorn |
| Frontend | React 18, Recharts, Material-UI |
| Monitoring | Prometheus, Grafana, cAdvisor |
| Conteneurisation | Docker, Docker Compose |
| Cloud | Google Cloud Platform |
| CI/CD | GitHub Actions, Cloud Build |

---

## Ports des services

| Service | Port | Description |
|---------|------|-------------|
| MongoDB | 27017 | Base données brutes |
| PostgreSQL | 5432 | Base données propres |
| MLflow | 5000 | UI tracking expérimentations |
| API FastAPI | 8000 | API inférence |
| Dashboard React | 3000 | Interface utilisateur |
| Airflow Webserver | 8080 | UI Airflow |
| Prometheus | 9090 | Métriques monitoring |
| Grafana | 3001 | Dashboards visualisation |
| cAdvisor | 8082 | Métriques conteneurs |

---

## Points clés de l'architecture

L'architecture mise en place permet de :

1. **Traçabilité complète** : Lien entre données brutes, transformations, modèles et résultats via versioning et registre MLflow

2. **Automatisation end-to-end** : Orchestration Airflow des pipelines ETL, entraînement et déploiement

3. **Monitoring proactif** : Surveillance continue de l'infrastructure (cAdvisor + Prometheus) et des modèles en production

4. **Comparaison rigoureuse** : Expérimentation de multiples architectures de modèles avec tracking MLflow

5. **Déploiement cloud-ready** : Infrastructure containerisée déployable sur GCP

6. **Interface utilisateur moderne** : Dashboard React interactif pour visualisation et feedback terrain

---

## Structure du projet

```
predictmaint-ai/
├── pipelines/
│   ├── 1_etl_ingestion/
│   │   ├── extraction/
│   │   ├── transformation/
│   │   └── loading/
│   ├── 2_training_mlops/
│   │   ├── experimentation/
│   │   ├── optimization/
│   │   └── registry/
│   └── 3_inference_ihm/
│       ├── api/
│       └── frontend/
├── orchestration/
│   └── airflow/
│       ├── dags/
│       ├── plugins/
│       └── config/
├── infrastructure/
│   ├── deployment/
│   ├── monitoring/
│   └── scripts/
├── storage/
│   ├── raw/
│   ├── processed/
│   └── models/
└── src/
    ├── config.py
    ├── data/
    ├── features/
    ├── models/
    ├── monitoring/
    ├── storage/
    └── utils/
```

---

## Documentation

- **Guide de démarrage rapide** : `QUICK_START.md`
- **Rapports de validation** : `storage/models/`
- **Configuration Airflow** : `orchestration/airflow/config/`
- **Dashboards Grafana** : `infrastructure/monitoring/grafana/dashboards/`
