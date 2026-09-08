# PredictMaint AI

Système de maintenance prédictive pour moteurs d'avion, basé sur le jeu de données NASA C-MAPSS (FD001). Le projet prédit si un moteur va tomber en panne dans les 30 prochains cycles, à partir de son historique de mesures capteurs.

Ce dépôt couvre l'ensemble de la chaîne : préparation des données, entraînement et sélection du modèle, service de prédiction en ligne, et déploiement en production sur Google Cloud avec supervision continue.

## Objectif métier

Sur une flotte de moteurs, une panne non anticipée coûte beaucoup plus cher qu'une intervention de maintenance programmée à l'avance. Le modèle doit donc privilégier le rappel (ne pas manquer une panne réelle) tout en gardant un nombre raisonnable de fausses alertes. C'est ce compromis qui pilote le choix du modèle final, via un coût métier calculé explicitement (faux négatif largement plus pénalisé qu'un faux positif).

## Architecture du dépôt

```text
predictmaint-ai/
├── src/                        Pipeline ML (le cœur du projet)
│   ├── data/                   Préparation, split par moteur, validation, cibles
│   ├── features/                Feature engineering causal, sélection de variables
│   ├── models/                  Entraînement, optimisation Optuna, quality gate, registre
│   ├── monitoring/               Dérive des données (PSI), suivi de performance
│   └── pipelines/retrain.py     Orchestration du réentraînement complet
├── pipelines/
│   ├── 1_etl_ingestion/         Ingestion optionnelle vers MongoDB/PostgreSQL (dev local)
│   └── 3_inference_ihm/
│       ├── api/                 API FastAPI (prédiction, feedback, réentraînement)
│       └── frontend/             Dashboard React
├── infrastructure/
│   ├── deployment/               Dockerfiles, docker-compose (dev local), scripts GCP
│   ├── monitoring/grafana/       Dashboards Grafana
│   └── tests/                    Tests unitaires et d'intégration
├── orchestration/airflow/        DAGs Airflow pour l'ETL en local (optionnel)
├── docs/                         Documentation détaillée (besoin métier, data leakage, etc.)
├── notebooks/                    Analyses exploratoires
└── .github/workflows/deploy.yml  CI/CD : tests, build, déploiement GCP
```

Le détail de l'architecture (schémas, flux de données, choix de conception) est dans [ARCHITECTURE.md](ARCHITECTURE.md).

## Pipeline de machine learning

Le pipeline vit entièrement dans **src/** et s'exécute comme une suite de scripts indépendants (orchestrés par **src/pipelines/retrain.py**) :

1. **Préparation** (**src/data/prepare.py**) : chargement du jeu FD001, découpage train / calibration / validation **par moteur** (jamais par ligne), pour qu'aucun cycle d'un même moteur ne se retrouve à la fois en entraînement et en évaluation.
2. **Feature engineering** (**src/features/build_features.py**) : statistiques glissantes causales (moyenne, min, max, lag) calculées uniquement à partir du passé de chaque moteur.
3. **Sélection de variables** (**src/features/select_features.py**) : ajustée uniquement sur le jeu d'entraînement, pour éviter toute fuite d'information depuis la validation.
4. **Entraînement comparatif** (**src/models/train.py**) : régression logistique, random forest et XGBoost sont entraînés et évalués sur un jeu de calibration dédié.
5. **Optimisation** (**src/models/optimize.py**) : recherche d'hyperparamètres Optuna avec validation croisée groupée par moteur (**StratifiedGroupKFold**), pour ne pas optimiser sur une fuite de données.
6. **Sélection du champion** (**src/models/promote.py**) : le meilleur modèle est choisi par un critère à plusieurs niveaux : garde-fou sur le rappel, puis coût métier, puis PR-AUC, puis score de Brier. Un nouveau modèle ne remplace jamais un modèle existant s'il est moins bon sur ce critère (anti-régression).
7. **Verrou qualité** (**src/models/quality_gate.py**) : bloque la mise en production d'un modèle qui ne respecte pas les seuils minimaux définis.
8. **Registre** (**src/models/register.py**, **src/storage/model_artifacts.py**) : le modèle retenu est versionné à trois endroits en parallèle (registre local avec hash SHA-256, MLflow avec un alias **champion**, et Google Cloud Storage), chacun protégé par la même règle anti-régression.

Le jeu de test externe n'est jamais utilisé par cette boucle : il sert uniquement à **src/models/evaluate.py**, exécuté séparément, pour une mesure finale indépendante de toute optimisation.

### Résultats de la dernière comparaison

Sur le jeu de calibration dédié (3 064 cycles, 465 pannes réelles) :

| Modèle | Précision | Rappel | PR-AUC | Coût métier / 1000 |
|--------|-----------|--------|--------|---------------------|
| Random Forest | 0,557 | 0,978 | 0,925 | 91 710 |
| Logistic Regression | 0,626 | 0,961 | 0,932 | 102 317 |
| XGBoost | 0,596 | 0,957 | 0,921 | 114 556 |

Le candidat retenu à l'issue de l'optimisation Optuna atteint un rappel de 100 % (aucune panne manquée) avec une PR-AUC de 0,946, mais n'est promu champion que s'il fait mieux que le champion déjà en place selon la règle décrite ci-dessus. Le champion réellement actif est donc toujours celui enregistré dans **storage/models/registry/index.json** (local) et dans MLflow (alias **champion**), pas un chiffre figé dans ce fichier.

## Service d'inférence

- **API** (**pipelines/3_inference_ihm/api/**, FastAPI) : charge le modèle champion au démarrage, expose **/predict** pour une prédiction, **/feedback** pour recevoir le résultat réel a posteriori, et **/retrain/*** pour déclencher ou suivre un réentraînement.
- **Dashboard** (**pipelines/3_inference_ihm/frontend/**, React) : interface de démonstration pour soumettre un moteur et visualiser le risque prédit.

Chaque prédiction et chaque retour de feedback sont journalisés (localement ou sur GCS selon l'environnement) avec un identifiant de moteur décalé (+1 000 000 pour une prédiction unitaire, +5 000 000 pour un import CSV en masse), pour garantir qu'ils ne puissent jamais entrer en collision avec les moteurs utilisés à l'entraînement.

## Déploiement en production (GCP)

Le projet tourne en production sur Cloud Run :

| Service | Rôle |
|---------|------|
| **predictmaint-api** | API FastAPI de prédiction |
| **predictmaint-dashboard** | Dashboard React |
| **predictmaint-mlflow** | Registre et suivi d'expérimentations MLflow |
| **predictmaint-grafana** | Supervision (Cloud Monitoring comme source de données) |
| **predictmaint-retrain** (Cloud Run Job) | Réentraînement complet du pipeline |

Le déploiement est automatisé par GitHub Actions (**.github/workflows/deploy.yml**) : à chaque push sur **main**, les tests s'exécutent, les images Docker sont construites et poussées, puis les services Cloud Run sont mis à jour. Un Cloud Scheduler déclenche en plus **predictmaint-retrain** chaque nuit, indépendamment de tout push de code, pour boucler sur le feedback de production collecté depuis la veille.

Le script **scripts/check_production_urls.sh** retrouve les URLs des services déployés et leurs identifiants d'accès.

## Supervision

En production, l'API exporte ses métriques vers Cloud Monitoring (prédictions par minute, latence, part de variables en dérive, PSI par variable, disponibilité du modèle), affichées dans Grafana. En développement local, la stack complète ajoute Prometheus et cAdvisor pour le suivi des conteneurs.

## Installation en local

### Prérequis

- Python 3.11+
- Docker et Docker Compose
- Git

### Démarrage rapide

```bash
git clone https://github.com/messanh0139/predictmaint-ai.git
cd predictmaint-ai
cp .env.example .env

cd infrastructure/deployment
docker compose up --build -d
```

Cette commande démarre l'API, le dashboard, MLflow, Grafana, Prometheus, cAdvisor, ainsi qu'une stack Airflow + MongoDB + PostgreSQL optionnelle pour l'ingestion ETL (désactivée par défaut dans le pipeline, activable via la variable **USE_DATABASES=1**).

| Service | URL locale |
|---------|------------|
| API (Swagger) | http://localhost:8001/docs |
| Dashboard | http://localhost:3002 |
| MLflow | http://localhost:5001 |
| Grafana | http://localhost:3001 (admin / admin) |
| Airflow | http://localhost:8081 (admin / admin) |

Pour tout arrêter : **docker compose down** depuis **infrastructure/deployment/**.

### Lancer le pipeline manuellement

```bash
python -m src.pipelines.retrain --optimize
```

## Tests

```bash
pytest infrastructure/tests/ -v --cov
```

## Documentation complémentaire

- [ARCHITECTURE.md](ARCHITECTURE.md) — architecture détaillée et choix de conception
- [QUICK_START.md](QUICK_START.md) — prise en main pas à pas
- [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md) — guide d'utilisation de l'API et du dashboard
- [docs/](docs/) — besoin métier, stratégie ML, prévention du data leakage, monitoring, risques et limites

## Auteur

Messanh Yaovi KODJO — kmessanhyaovi@gmail.com

## Licence

MIT.
