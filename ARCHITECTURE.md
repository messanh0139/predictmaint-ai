# Architecture

Ce document détaille l'architecture technique du projet PredictMaint AI : le pipeline de machine learning, le service d'inférence, et le déploiement en production sur Google Cloud Platform.

Le système a deux modes de fonctionnement :

- **Production (GCP Cloud Run)** : ce qui tourne réellement en continu, décrit en premier ci-dessous.
- **Développement local (Docker Compose)** : une stack plus riche (avec Airflow, MongoDB, PostgreSQL, Prometheus) utilisée pour expérimenter, mais qui n'est pas nécessaire au fonctionnement du système en production.

## Vue d'ensemble (production)

```
┌────────────────────────────────────────────────────────────────┐
│  1. Pipeline ML (src/)                                          │
│     préparation → feature engineering → sélection → entraînement│
│     → optimisation Optuna → sélection champion → quality gate   │
│     → registre (local + MLflow + GCS)                           │
└────────────────────────────────────────────────────────────────┘
                              │
                     déclenché par Cloud Scheduler (quotidien)
                     ou par un push sur main (CI/CD)
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  2. Service d'inférence (Cloud Run)                             │
│     API FastAPI (predictmaint-api) — charge le modèle champion  │
│     Dashboard React (predictmaint-dashboard)                    │
└────────────────────────────────────────────────────────────────┘
                              │
                     prédictions + feedback journalisés (GCS)
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  3. Supervision                                                 │
│     API → métriques custom → Cloud Monitoring → Grafana         │
└────────────────────────────────────────────────────────────────┘
```

Le feedback de production (résultat réel connu a posteriori) est repris automatiquement au réentraînement suivant, ce qui boucle le système sur lui-même sans intervention manuelle.

## Le pipeline de machine learning (**src/**)

Chaque étape est un script indépendant, exécutable seul ou enchaîné par **src/pipelines/retrain.py**.

### 1. Préparation des données (**src/data/prepare.py**, **src/data/split.py**)

Chargement du jeu NASA C-MAPSS FD001, puis découpage en trois ensembles **par moteur** (jamais par ligne) : entraînement, calibration, validation. Ce découpage garantit qu'aucun cycle d'un moteur donné n'apparaît dans deux ensembles différents — condition nécessaire pour éviter toute fuite de données (voir **docs/04_data_leakage.md**).

### 2. Feature engineering (**src/features/build_features.py**)

Calcul de statistiques glissantes causales par moteur (moyenne, min, max, décalage temporel) sur plusieurs fenêtres de cycles. Chaque statistique ne regarde que le passé du moteur au moment du cycle considéré.

### 3. Sélection de variables (**src/features/select_features.py**)

La sélection est ajustée uniquement sur l'ensemble d'entraînement, puis appliquée telle quelle à la calibration et à la validation.

### 4. Entraînement comparatif (**src/models/train.py**)

Trois familles de modèles sont entraînées et évaluées sur un jeu de calibration dédié : régression logistique, random forest, XGBoost. Le seuil de décision de chacun est calibré séparément pour respecter un rappel minimal.

### 5. Optimisation (**src/models/optimize.py**)

Recherche d'hyperparamètres avec Optuna, validée par une validation croisée groupée par moteur (**StratifiedGroupKFold**), pour que l'optimisation elle-même ne fuite pas d'information entre les groupes.

### 6. Sélection du champion (**src/models/promote.py**)

Le meilleur modèle est choisi par un critère à plusieurs niveaux, dans cet ordre : garde-fou sur le rappel minimal, puis coût métier, puis PR-AUC, puis score de Brier. Un candidat ne remplace le champion en place que s'il est strictement meilleur sur ce critère — c'est la règle anti-régression, appliquée de façon identique aux trois emplacements de stockage du modèle (voir plus bas).

### 7. Verrou qualité (**src/models/quality_gate.py**)

Bloque la promotion d'un modèle qui ne respecte pas des seuils minimaux fixés (rappel, précision, etc.), indépendamment de la comparaison avec le champion actuel.

### 8. Registre (**src/models/register.py**, **src/storage/model_artifacts.py**)

Le modèle retenu est versionné à trois endroits, chacun protégé par la règle anti-régression :

- **Registre local** (**storage/models/registry/index.json**) : hash SHA-256 de chaque version, métriques de validation.
- **MLflow** (**predictmaint-mlflow**) : chaque entraînement est loggé comme run, le modèle retenu reçoit l'alias **champion**.
- **Google Cloud Storage** : artefact versionné, plus un pointeur global **champion.json**.

### Jeu de test externe

Le jeu de test externe FD001 (avec son fichier RUL officiel) n'entre jamais dans cette boucle de réentraînement. Il n'est ouvert que par **src/models/evaluate.py**, exécuté séparément, pour produire une mesure finale indépendante de tout ajustement fait pendant l'entraînement ou l'optimisation.

## Service d'inférence

### API (**pipelines/3_inference_ihm/api/**, FastAPI)

- Charge le modèle champion (depuis GCS en production) au démarrage.
- **POST /predict** : renvoie le risque de panne pour un moteur donné.
- **POST /feedback** : reçoit le résultat réel une fois connu, journalisé pour le prochain réentraînement.
- **POST /retrain/*** : déclenche et suit un réentraînement manuel.
- **GET /live**, **/ready** : sondes de santé.
- Exporte ses métriques vers Cloud Monitoring (voir section Supervision).

Chaque prédiction et chaque feedback sont enregistrés avec un identifiant de moteur décalé (+1 000 000 pour une prédiction unitaire, +5 000 000 pour un import CSV en masse), pour qu'ils ne puissent jamais entrer en collision avec les identifiants des moteurs d'entraînement, de calibration ou de validation.

### Dashboard (**pipelines/3_inference_ihm/frontend/**, React 18)

Interface de démonstration : soumission d'un moteur, visualisation du risque prédit, et suivi du réentraînement.

## Déploiement en production (GCP)

### Services Cloud Run

| Service | Rôle |
|---------|------|
| **predictmaint-api** | API FastAPI |
| **predictmaint-dashboard** | Dashboard React |
| **predictmaint-mlflow** | Registre et suivi MLflow |
| **predictmaint-grafana** | Supervision (datasource Cloud Monitoring) |
| **predictmaint-retrain** (Cloud Run Job, pas un service) | Réentraînement complet |

**MLflow** est provisionné manuellement (pas d'étape dans **deploy.yml**), avec **--memory 2Gi --min-instances 1 --max-instances 1**. Son backend (**sqlite:////mlflow/mlflow.db**) et ses artefacts vivent sur le disque local du conteneur, non partagés entre instances : une seule instance suffisamment dotée en mémoire est donc nécessaire pour que l'historique survive dans le temps. Avec la limite par défaut (1 Gi), le conteneur était tué pour dépassement mémoire à chaque enregistrement de modèle, ce qui réinitialisait silencieusement toute la base à chaque redémarrage — corrigé le 2026-09-05.

### CI/CD

- **GitHub Actions** (**.github/workflows/deploy.yml**) : à chaque push sur **main**, exécute les tests, construit les images Docker, les pousse, puis déploie sur Cloud Run. Le job de réentraînement est aussi reconstruit et redéployé à cette occasion.
- **Cloud Scheduler** (**predictmaint-retrain-daily**, région **europe-west1**) : exécute directement le job Cloud Run **predictmaint-retrain** tous les jours à 3h (heure de Paris), indépendamment de tout push de code — c'est ce qui ferme la boucle de feedback de production (prédictions et retours accumulés via l'API, repris automatiquement au réentraînement suivant). Provisionné via **gcloud scheduler jobs**, sans code applicatif associé.

## Supervision

L'API exporte ses métriques vers Cloud Monitoring (**pipelines/3_inference_ihm/api/cloud_monitoring.py**, converties depuis le format Prometheus) :

- **predictmaint/predictions_total** — nombre de prédictions, par niveau de risque
- **predictmaint/prediction_latency_seconds_mean** — latence moyenne
- **predictmaint/model_ready** — disponibilité du modèle
- **predictmaint/drift_share** — part des variables en dérive
- **predictmaint/drift_psi** — indice PSI par variable, comparé à la référence d'entraînement
- **predictmaint/telemetry_errors_total** — erreurs de persistance de la télémétrie

Ces métriques sont affichées dans Grafana (dashboard **PredictMaint AI - Cloud Monitoring**), aux côtés des métriques natives Cloud Run (nombre de requêtes, etc.).

## Développement local (Docker Compose)

**infrastructure/deployment/docker-compose.yml** démarre une stack plus complète, pensée pour expérimenter en local sans dépendre de GCP :

| Service | Port | Rôle |
|---------|------|------|
| MongoDB | 27017 | Stockage brut optionnel (ingestion ETL) |
| PostgreSQL | 5432 | Stockage propre optionnel |
| MLflow | 5000 | Registre et suivi local |
| API FastAPI | 8000 | API d'inférence |
| Dashboard React | 3000 | Interface utilisateur |
| Airflow Webserver | 8080 | Orchestration ETL locale |
| Prometheus | 9090 | Collecte de métriques |
| Grafana | 3001 | Dashboards locaux |
| cAdvisor | 8082 | Métriques des conteneurs Docker |

MongoDB, PostgreSQL et Airflow servent à une ingestion ETL optionnelle (**pipelines/1_etl_ingestion/**, DAGs dans **orchestration/airflow/dags/**) : le pipeline **src/data/prepare.py** peut lire depuis MongoDB si la variable d'environnement **USE_DATABASES=1** est définie, mais lit directement le CSV FD001 par défaut. Cette ingestion n'est pas utilisée en production.

## Structure du projet

```
predictmaint-ai/
├── src/                         Pipeline ML
│   ├── config.py
│   ├── data/                    Chargement, split, cibles, validation
│   ├── features/                 Feature engineering, sélection
│   ├── models/                   Entraînement, optimisation, registre
│   ├── monitoring/               Dérive (PSI), performance
│   ├── pipelines/retrain.py      Orchestration du réentraînement
│   ├── storage/                  Persistance des artefacts modèle
│   └── utils/
├── pipelines/
│   ├── 1_etl_ingestion/          Ingestion optionnelle (dev local)
│   └── 3_inference_ihm/
│       ├── api/                  API FastAPI
│       └── frontend/              Dashboard React
├── orchestration/airflow/        DAGs pour l'ETL local (optionnel)
├── infrastructure/
│   ├── deployment/                Dockerfiles, docker-compose, scripts GCP
│   ├── monitoring/grafana/         Dashboards Grafana
│   └── tests/                     Tests unitaires et d'intégration
├── storage/
│   ├── raw/                       Données brutes FD001
│   ├── processed/                 Données préparées, splits
│   └── models/                    Registre local, rapports
├── docs/                          Documentation détaillée
├── notebooks/                     Analyses exploratoires
└── .github/workflows/deploy.yml   CI/CD
```

## Documentation complémentaire

- **README.md** — présentation générale et démarrage rapide
- **QUICK_START.md** — prise en main pas à pas
- **docs/** — besoin métier, stratégie ML, prévention du data leakage, monitoring, risques et limites
- **storage/models/** — rapports de validation, quality gate, optimisation (générés à chaque run)
