# Architecture Production vs Développement

## Vue d'ensemble

Ce document explique les différences entre l'architecture de développement (locale) et l'architecture de production (GCP Cloud) pour le projet PredictMaint AI.

## Architecture de Développement (Locale)

### Objectif
Environnement local pour le développement, les tests et la démonstration des concepts MLOps.

### Stack
```
┌─────────────────────────────────────────┐
│         Docker Compose Local             │
├─────────────────────────────────────────┤
│ • Apache Airflow (port 8080)            │
│   Orchestration DAGs                     │
│   Interface web locale                   │
│                                          │
│ • PostgreSQL (port 5432)                │
│   Stockage données propres               │
│                                          │
│ • MongoDB (port 27017)                   │
│   Stockage données brutes                │
│                                          │
│ • MLflow (port 5000)                     │
│   Tracking expérimentations              │
│                                          │
│ • API FastAPI (port 8000)                │
│   Tests d'inférence locaux               │
│                                          │
│ • Dashboard React (port 3000)            │
│   Développement frontend                 │
│                                          │
│ • Prometheus + Grafana                   │
│   Monitoring local                       │
└─────────────────────────────────────────┘
```

### Utilisation
- Démonstration technique des DAGs Airflow
- Tests en local avant déploiement
- Captures d'écran pour le mémoire
- Développement itératif


## Architecture de Production (GCP Cloud)

### Objectif
Infrastructure serverless scalable, hautement disponible et économique pour la production.

### Stack Complète

```
┌────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS (CI/CD)                   │
│  Remplace Airflow pour l'orchestration production           │
└──────────────────────┬─────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        |              |              |
    ┌───────┐    ┌──────────┐   ┌──────────┐
    │ Tests │    │ Retrain  │   │  Deploy  │
    │ & QA  │ puis│   Job    │puis│ Services │
    └───────┘    └──────────┘   └──────────┘
                       │
        ┌──────────────┼──────────────┐
        |              |              |
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ Cloud Run    │ │   GCS    │ │  Cloud Run   │
│ Job          │ │ Buckets  │ │  Services    │
│              │ │          │ │              │
│ Retraining   │ │ Models   │ │ • API        │
│ (on-demand)  │ │ Predict. │ │ • Dashboard  │
│              │ │ Feedback │ │ • Grafana    │
└──────────────┘ └──────────┘ └──────────────┘
```

### Composants Production

#### 1. Orchestration : GitHub Actions + Cloud Scheduler

**Remplace complètement Airflow** avec des avantages :

| Airflow Local | GitHub Actions Production |
|---------------|---------------------------|
| Interface web locale | Interface web publique GitHub |
| Planification cron | Cloud Scheduler + GitHub workflow_dispatch |
| DAG Python | Workflow YAML |
| Logs locaux | Logs persistés GitHub + Cloud Logging |
| 1 serveur dédié | Serverless (0 coût au repos) |

**Workflow Production (**.github/workflows/deploy.yml**)** :
```yaml
on:
  push:
    branches: [main]        # Déclenchement automatique
  schedule:
    - cron: '0 2 * * 1'     # Hebdomadaire (lundi 2h)
  workflow_dispatch:        # Déclenchement manuel

jobs:
  validate-retrain-deploy:
    steps:
      - Tests & Validation  # = Task Airflow
      - Retrain Job         # = Task Airflow
      - Quality Gate        # = Task Airflow
      - Deploy Services     # = Task Airflow
```

#### 2. Stockage : GCS (Google Cloud Storage)

**Remplace PostgreSQL + MongoDB** :
- **gs://predictmaint-models/** : Artefacts modèles
- **gs://predictmaint-predictions/** : Prédictions production
- **gs://predictmaint-feedback/** : Vérité terrain

**Avantages** :
- Serverless (pas de base à maintenir)
- Versioning natif
- Intégration directe Cloud Run

#### 3. Compute : Cloud Run Services

**Services déployés** :

| Service | URL |
|---------|-----|
| API FastAPI | **https://predictmaint-api-6iao6qpasa-ew.a.run.app** |
| Dashboard React | **https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app** |
| Grafana | **https://predictmaint-grafana-6iao6qpasa-ew.a.run.app​** |

**Cloud Run Job** (retraining) :
- Exécuté à la demande (GitHub Actions ou Cloud Scheduler)
- Coût uniquement pendant l'exécution (~0.50€/run)
- Timeout 1h, retry automatique

#### 4. Monitoring : Cloud Monitoring + Grafana

**Cloud Monitoring** (natif GCP) :
- Métriques custom : **custom.googleapis.com/predictmaint/***
- Logs centralisés (Cloud Logging)
- Alerting intégré

**Grafana Cloud Run** :
- Dashboard public pour démonstration
- Connecté à Cloud Monitoring API
- Mot de passe sécurisé (Secret Manager)


## Comparaison Détaillée

### Orchestration

| Critère | Airflow (Dev) | GitHub Actions (Prod) |
|---------|---------------|----------------------|
| **Accessibilité** | Local uniquement | Public (GitHub + URLs Cloud Run) |
| **Planification** | Cron local | Cloud Scheduler + Cron GitHub |
| **Logs** | Local | Persistés, recherchables |
| **Coût** | Gratuit (local) | Gratuit |
| **Scalabilité** | 1 worker | Illimitée |
| **Maintenance** | Docker à maintenir | Zéro maintenance |
| **Interface démo** | http://localhost:8081 | https://github.com/messanh0139/predictmaint-ai/actions |


### Stockage

| Critère | PostgreSQL (Dev) | GCS (Prod) |
|---------|------------------|------------|
| **Accessibilité** | Local uniquement | Global, répliqué |
| **Versioning** | Manuel | Natif |
| **Backup** | Manuel | Automatique |
| **Coût** | Gratuit (local) | ~1€/mois |
| **Intégration** | Connexion DB | API native |

**Verdict** : GCS est plus adapté pour un système ML en production.

### Compute

| Critère | Docker Local | Cloud Run |
|---------|--------------|-----------|
| **Accessibilité** | localhost | URLs publiques HTTPS |
| **Certificats SSL** | Aucun | Automatiques |
| **Auto-scaling** | Non | Oui (0 à N instances) |
| **Coût repos** | Ressources locales | 0€ (scale to zero) |
| **Haute dispo** | Non | Oui (multi-zone) |

**Verdict** : Cloud Run permet une vraie démonstration production avec URLs publiques.


## Workflow Complet : Production vs Développement

### Workflow de Développement (Local)

```
1. Développeur modifie le code
   ↓
2. Lance Docker Compose
   docker-compose up -d
   ↓
3. Accède Airflow local
   http://localhost:8081
   ↓
4. Déclenche DAG manuellement
   Pipeline 1 (ETL) puis Pipeline 2 (MLOps)
   ↓
5. Vérifie MLflow local
   http://localhost:5001
   ↓
6. Teste API local
   http://localhost:8001/docs
   ↓
7. Capture d'écran pour mémoire
```

### Workflow de Production (Cloud)

```
1. Développeur push sur main
   git push origin main
   ↓
2. GitHub Actions détecte automatiquement
   ↓
3. Workflow exécute séquentiellement:
   ├─ Tests & Validation (pytest, ruff)
   ├─ Build Trainer Image
   ├─ Deploy Cloud Run Job
   ├─ Execute Retraining
   │  ├─ Fetch feedback depuis GCS
   │  ├─ Train 3+ modèles
   │  ├─ Optimize (Optuna)
   │  ├─ Quality Gate (recall ≥ 85%)
   │  └─ Upload champion sur GCS
   ├─ Build Service Images (API, Dashboard, Grafana)
   ├─ Deploy Services sur Cloud Run
   └─ Smoke Tests
   ↓
4. URLs publiques disponibles:
   https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app ​
   https://predictmaint-api-6iao6qpasa-ew.a.run.app ​
   https://predictmaint-mlflow-6iao6qpasa-ew.a.run.app ​
   https://predictmaint-grafana-6iao6qpasa-ew.a.run.app​
   ↓
5. Partage des URLs dans le mémoire
```





