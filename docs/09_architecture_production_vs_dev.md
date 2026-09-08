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

---

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
- Coût très faible (~1€/mois)

#### 3. Compute : Cloud Run Services

**Services déployés** :

| Service | URL | Auto-scaling | Coût au repos |
|---------|-----|--------------|---------------|
| API FastAPI | **https://predictmaint-api-xxx.run.app** | 0-5 instances | 0€ |
| Dashboard React | **https://predictmaint-dashboard-xxx.run.app** | 0-3 instances | 0€ |
| Grafana | **https://predictmaint-grafana-xxx.run.app** | 0-2 instances | 0€ |

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

---

## Comparaison Détaillée

### Orchestration

| Critère | Airflow (Dev) | GitHub Actions (Prod) |
|---------|---------------|----------------------|
| **Accessibilité** | Local uniquement | Public (GitHub + URLs Cloud Run) |
| **Planification** | Cron local | Cloud Scheduler + Cron GitHub |
| **Logs** | Local | Persistés, recherchables |
| **Coût** | Gratuit (local) | Gratuit (2000 min/mois) |
| **Scalabilité** | 1 worker | Illimitée |
| **Maintenance** | Docker à maintenir | Zéro maintenance |
| **Interface démo** | http://localhost:8081 | https://github.com/.../actions |

**Verdict** : Pour la production et la démonstration professionnelle, GitHub Actions est **supérieur** à Airflow local.

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

---

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
   https://predictmaint-api-xxx.run.app
   https://predictmaint-dashboard-xxx.run.app
   https://predictmaint-grafana-xxx.run.app
   ↓
5. Partage des URLs dans le mémoire
```

---

## Architecture Recommandée pour le Mémoire

### Phase 1 : Démonstration Locale (Airflow)

**Pour montrer la compréhension des concepts MLOps** :
1. Présenter les DAGs Airflow (captures d'écran)
2. Expliquer l'orchestration Pipeline 1 puis Pipeline 2
3. Montrer MLflow local (comparaison modèles)

**Slides mémoire** :
- Screenshot Airflow Graph View
- Screenshot MLflow Experiments
- Explication : "En développement, Airflow orchestre..."

### Phase 2 : Production Serverless (GitHub Actions + Cloud Run)

**Pour montrer la mise en production professionnelle** :
1. URLs publiques accessibles par le jury
2. GitHub Actions comme orchestrateur production
3. Infrastructure 100% serverless

**Slides mémoire** :
- Screenshot GitHub Actions workflow en succès
- URLs publiques cliquables
- Explication : "En production, GitHub Actions remplace Airflow pour..."

### Phase 3 : Justification Architecturale

**Argument dans le mémoire** :

> "L'architecture de développement utilise Apache Airflow pour orchestrer les pipelines ETL et MLOps, permettant une visualisation claire des dépendances et une gestion robuste des erreurs. Cependant, pour le déploiement en production, nous adoptons une approche serverless avec GitHub Actions et Cloud Run, offrant plusieurs avantages :
>
> 1. **Accessibilité** : URLs publiques vs interface locale
> 2. **Coût** : Scale-to-zero vs serveurs dédiés (100€+/mois)
> 3. **Maintenance** : Infrastructure managée vs administration manuelle
> 4. **Scalabilité** : Auto-scaling natif vs capacité fixe
> 5. **Sécurité** : HTTPS automatique, isolation par design
>
> Cette architecture hybride démontre la compréhension des concepts MLOps (Airflow) tout en appliquant les meilleures pratiques cloud-native en production (GitHub Actions + Cloud Run)."

---

## Migration Airflow vers Cloud Scheduler (Optionnel)

Si vous voulez aller plus loin, vous pouvez ajouter **Cloud Scheduler** pour planifier le retraining hebdomadaire :

```bash
# Créer un job Cloud Scheduler qui déclenche le retraining
gcloud scheduler jobs create http predictmaint-weekly-retrain \
  --location=europe-west1 \
  --schedule="0 2 * * 1" \
  --uri="https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/predictmaint-retrain:run" \
  --http-method=POST \
  --oauth-service-account-email=predictmaint-deployer@PROJECT_ID.iam.gserviceaccount.com
```

Cela remplace complètement le **@weekly** d'Airflow par une solution cloud-native.

---

## Conclusion : Quelle Architecture Présenter ?

### Pour la Soutenance

**Présentez les DEUX architectures** :

1. **Architecture de développement** (Airflow + Docker)
   - Montrez votre compréhension des pipelines ML
   - Captures d'écran Airflow + MLflow
   - "Environnement de développement et tests"

2. **Architecture de production** (GitHub Actions + Cloud Run)
   - Donnez les URLs publiques au jury
   - Montrez le workflow GitHub Actions
   - "Déploiement production serverless"

**Message clé** :
> "Airflow est excellent pour le développement et la démonstration des concepts MLOps. En production, nous adoptons une approche serverless avec GitHub Actions et Cloud Run, offrant une meilleure scalabilité, disponibilité et économie tout en conservant les mêmes garanties d'orchestration."

### Avantages de cette Approche

- **Montre votre expertise technique** (Airflow, DAGs, orchestration)
- **Démontre votre pragmatisme** (choisir la bonne techno selon le contexte)
- **Fournit une démo production réelle** (URLs publiques)
- **Respecte les contraintes budgétaires** (serverless économique)
- **Prouve votre compréhension MLOps** (dev vs prod)

---

## Résumé : Ce qui est Professionnel

| Composant | Non Professionnel | Professionnel |
|-----------|---------------------|------------------|
| **Orchestration** | Airflow uniquement local | Airflow (dev) + GitHub Actions (prod) |
| **Démo** | Screenshots uniquement | URLs publiques cliquables |
| **Accessibilité** | localhost:8081 | https://github.com/user/project/actions |
| **Prédictions** | curl localhost | https://predictmaint-api-xxx.run.app/docs |
| **Monitoring** | Grafana local | https://predictmaint-grafana-xxx.run.app |
| **Infrastructure** | "à faire tourner" | Déjà déployée 24/7 |

**Votre architecture actuelle est DÉJÀ professionnelle** grâce à GitHub Actions + Cloud Run ! Il suffit de bien l'expliquer dans votre mémoire.
