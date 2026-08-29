# PredictMaint AI — Maintenance Prédictive des Moteurs Turbofan

## Technologies Utilisées

**Langage**
Python

**Machine Learning**
scikit-learn · XGBoost · Optuna · Pandas · NumPy

**API et Dashboard**
FastAPI · Streamlit

**Orchestration et Tracking**
MLflow · Cloud Scheduler (planification GCP)

**Monitoring**
Prometheus · Grafana · PSI (Population Stability Index)

**Conteneurisation et CI/CD**
Docker · Docker Compose · GitHub Actions

**Cloud**
Google Cloud Platform (Cloud Run, Artifact Registry, Cloud Storage)

Le détail des alternatives comparées et la justification de chaque choix (compatibilité, coût, simplicité, performance, maintenabilité) est documenté dans `docs/03_choix_technologiques.md`.

## Objectif du Projet

Ce projet vise à prédire le risque de défaillance d'un moteur turbofan dans les **30 prochains cycles**, à partir de ses relevés de capteurs, afin de prioriser les inspections et interventions de maintenance. L'objectif n'est pas seulement de produire un modèle performant, mais de l'intégrer dans une infrastructure complète permettant de le surveiller et de le maintenir en production de manière automatique.

> Les coûts métier utilisés dans le projet (faux négatif = 10 000, faux positif = 500) sont des hypothèses posées pour la mise en situation. Sur un projet réel, ils devraient être validés avec le commanditaire avant d'être utilisés pour arbitrer entre les modèles.

Concrètement, le système :

- prédit la probabilité de défaillance de chaque moteur et retourne un niveau de risque (HIGH / LOW) avec le seuil de décision qui a servi à la calculer ;
- surveille en continu la performance du modèle en production, grâce à la vérité terrain reçue plus tard via **/feedback** ;
- détecte les dérives (drift) dans les nouvelles données par un calcul de PSI, variable par variable ;
- déclenche un réentraînement complet et automatique dès qu'un nouveau lot de données labellisées est déposé, depuis le dashboard ou directement via l'API ;
- trace chaque entraînement dans un registre local et, en option, dans MLflow, pour garantir la reproductibilité complète.

## Cibles Métier

- **Équipes de maintenance** : un score de risque par moteur et une fenêtre d'alerte de 30 cycles pour prioriser les inspections.
- **Data scientists / MLOps** : traçabilité complète (registre local + MLflow), notebooks pédagogiques explicites, empreintes SHA256 reliant chaque modèle à sa version exacte des données.
- **Responsables qualité** : quality gate versionné (`models/quality_gate.json`), model card (`docs/11_model_card.md`) et limites documentées avant tout usage industriel.
- **Toute personne relisant le projet** : une preuve de bout en bout du cycle de vie MLOps — cadrage, données, modèle, API, monitoring, réentraînement, déploiement.

## Architecture du Projet

```text
predictmaint-ai/
├── api/                     # API FastAPI (prédiction, feedback, réentraînement)
├── dashboard/               # Dashboard Streamlit (démo, performance, réentraînement)
├── data/
│   ├── raw/                 # Données brutes (train_FD001.txt, test_FD001.txt, RUL_FD001.txt)
│   ├── processed/           # Features causales construites par partition
│   ├── reference/           # Référence utilisée pour le calcul du drift (PSI)
│   └── production/          # Données de production labellisées (feedback + upload direct)
├── docs/                    # Cadrage métier, stratégie ML, data leakage, architecture, model card...
├── infra/gcp/                # Scripts de provisionnement GCP (bootstrap, déploiement, WIF, job de retraining)
├── models/                  # Artefacts entraînés, métadonnées, rapports, registre local
├── monitoring/
│   ├── prometheus/           # Configuration Prometheus
│   └── grafana/               # Dashboards et provisioning Grafana
├── notebooks/                # Analyse exploratoire et modélisation pas à pas
├── src/
│   ├── data/                  # Chargement, validation, split, cible, collecte de feedback
│   ├── features/              # Feature engineering causal et sélection de variables
│   ├── models/                 # Entraînement, optimisation, promotion, quality gate, évaluation
│   ├── monitoring/             # Drift (PSI) et performance différée
│   ├── pipelines/               # Pipeline de réentraînement bout en bout
│   ├── storage/                 # Persistance des artefacts vers Cloud Storage
│   └── utils/                    # Empreintes SHA256, métadonnées runtime
├── tests/                      # Tests unitaires et anti-fuite pytest
├── docker-compose.yml           # Orchestration des 5 services Docker
└── Dockerfile / Dockerfile.dashboard / Dockerfile.mlflow / Dockerfile.train
```

## Architecture MLOps

```text
Jeu de données FD001
        |
        v
Validation + empreintes SHA256
        |
        v
Split par moteur AVANT toute transformation
  +-----------+--------------+----------------+
  |           |              |                |
TRAIN     CALIBRATION     VALIDATION      TEST EXTERNE
  |           |              |                |
Features   Features        Features          Features
causales   causales        causales          causales
  |           |              |                |
Sélection    Seuil de      Choix du          Évaluation
de variables décision      champion          externe finale
  |
  v
Logistic Regression / Random Forest / XGBoost
  |
  v
Optuna + validation croisée groupée par moteur (TRAIN uniquement)
  |
  v
Mécanisme Champion / Challenger
  |
  v
MLflow + registre local + artefacts versionnés
  |
  v
FastAPI -> Docker -> CI/CD -> Google Cloud Run
  |
  +--> Dashboard Streamlit (démo, performance, réentraînement)
  +--> Prometheus / Grafana en local
  +--> Cloud Logging / Cloud Monitoring sur GCP
  +--> Prédictions + feedback -> détection de drift -> réentraînement
```

## Comment le projet évite les fuites de données

La fuite de données (« data leakage ») est traitée comme un risque de conception à part entière, pas comme un détail d'implémentation :

1. **Split en trois groupes par `engine_id`, avant tout feature engineering et avant toute analyse exploratoire supervisée** : TRAIN, CALIBRATION et VALIDATION portent sur des moteurs différents, jamais mélangés.
2. **Le holdout externe reste réellement verrouillé** : `RUL_FD001.txt` n'est ni chargé ni matérialisé pendant le développement. Le couple `test_FD001 + RUL_FD001` n'est ouvert que par `python -m src.models.evaluate`, pour l'évaluation externe finale.
3. **Les features temporelles sont strictement causales** : une ligne au cycle `t` n'utilise que le cycle courant et les cycles passés du même moteur, jamais le futur.
4. **Certaines variables sont interdites au modèle** : `RUL`, la cible, l'identifiant moteur et toute colonne dérivée de la vérité terrain.
5. **L'EDA qui utilise le RUL/la cible et la sélection de variables ne portent que sur TRAIN** : les décisions humaines de sélection ne consultent jamais VALIDATION ni TEST.
6. **L'imputation et le scaling sont encapsulés dans des pipelines scikit-learn**, ajustés uniquement pendant le `fit` sur TRAIN.
7. **Le seuil de décision est calé sur CALIBRATION uniquement.**
8. **Le choix du champion se fait sur VALIDATION uniquement.**
9. **Optuna utilise une validation croisée groupée par moteur, sur TRAIN uniquement.**
10. **Le test externe n'est jamais exécuté par le réentraînement automatique**, pour qu'il ne devienne pas, au fil du temps, un signal de développement déguisé.

Détails complets : `docs/04_data_leakage.md`.

## Workflow du pipeline

**Ingestion de nouvelles données de production :**

Depuis l'onglet **Réentraînement automatique** du dashboard, un CSV de nouvelles données labellisées (relevés de capteurs + vérité terrain) est déposé. Le dashboard l'envoie immédiatement à l'API sur **POST /retrain/upload**, sans action supplémentaire de l'utilisateur.

**Détection de dérive des données (indépendante du déclenchement du réentraînement) :**

`src/monitoring/drift.py` calcule un **PSI** par variable en comparant la distribution courante à une référence figée sur TRAIN. Si le volume de données est insuffisant pour conclure, le système retourne explicitement `insufficient_data` plutôt que d'interpréter à tort un PSI nul comme une absence de dérive. Une alerte est levée si une proportion significative de variables dépasse le seuil PSI (0,20 par défaut).

**Réentraînement automatique :**

Dès qu'un nouveau lot de données arrive (upload dashboard/API) ou selon une planification hebdomadaire en production (Cloud Scheduler), le pipeline complet s'exécute en arrière-plan : préparation, sélection de variables, entraînement, quality gate, enregistrement. Ces nouvelles observations ne sont ajoutées **qu'au TRAIN** ; CALIBRATION, VALIDATION et le holdout externe restent inchangés. Chaque entraînement est tracé (registre local et, en option, MLflow) avec hyperparamètres, métriques et empreinte SHA256 du jeu de données utilisé.

**Promotion champion / challenger :**

Le challenger n'est promu que si (1) les guardrails recall/PR-AUC passent, (2) il améliore le coût métier sur la VALIDATION verrouillée, (3) PR-AUC puis Brier servent de départage en cas d'égalité. Ce mécanisme évite de déployer un modèle plus complexe mais moins utile.

**Prédiction en temps réel :**

L'API FastAPI expose **POST /predict**, qui charge le champion courant et retourne pour chaque moteur sa probabilité de défaillance, son niveau de risque (HIGH/LOW) et le seuil de décision utilisé. Le dashboard affiche ce résultat dans l'onglet **Démonstration prédictive**.

**Surveillance de la performance :**

Quand une vérité terrain arrive plus tard sur **POST /feedback**, `src/monitoring/performance.py` recalcule recall, PR-AUC, F1 et coût métier, et signale tout guardrail non respecté. Pour un lot contenant plusieurs versions du modèle, **chaque prédiction est réévaluée avec le seuil versionné qui a réellement servi à la produire** — aucun seuil courant ne remplace l'historique.

## Modèles comparés

Comparaison des trois familles de modèles de base, seuil calé sur un ensemble de calibration dédié (moteurs distincts de TRAIN/VALIDATION), métriques sur VALIDATION verrouillée :

| Modèle | Precision | Recall | F1-Score | ROC-AUC | PR-AUC | Coût métier |
|---|---|---|---|---|---|---|
| Logistic Regression | 0,594 | 0,974 | 0,738 | 0,989 | 0,958 | 275 000 |
| Random Forest | 0,658 | 0,976 | 0,786 | 0,989 | 0,949 | 228 000 |
| XGBoost (défaut) | 0,598 | 0,976 | 0,742 | 0,989 | 0,949 | 262 500 |
| **XGBoost optimisé (Optuna)** | 0,564 | **1,000** | 0,721 | 0,988 | 0,946 | **180 000** |

Le **XGBoost optimisé** a été retenu comme champion de production. Il n'a ni la meilleure précision ni le meilleur F1, mais c'est le seul à atteindre un recall de 1,000 sur la validation verrouillée : aucun moteur à risque n'est manqué. Dans ce contexte métier, une défaillance non détectée (faux négatif, coût 10 000) est bien plus coûteuse qu'une inspection inutile (faux positif, coût 500) — le coût métier total est donc le critère de départage prioritaire, et l'optimisé le minimise nettement (180 000 contre 228 000 pour le meilleur modèle de base).

## Résultats actuellement reproduits

### Qualité des données brutes

- Train : 20 631 lignes, 100 moteurs, 26 colonnes.
- Test externe : 13 096 lignes, 100 moteurs, 26 colonnes (contrôle structurel uniquement, avant l'évaluation finale).
- Valeurs manquantes : 0. Doublons `(engine_id, cycle)` : 0.
- Durée de vie des moteurs sur TRAIN : minimum 128, médiane 199, moyenne 206,31, maximum 362 cycles.
- Cible `RUL <= 30`, analysée après split, sur TRAIN uniquement : 2 170 positifs sur 14 407 lignes (15,06 %).

### Split de développement actuel

- TRAIN : 70 moteurs / 14 407 lignes.
- CALIBRATION : 15 moteurs / 3 160 lignes.
- VALIDATION : 15 moteurs / 3 064 lignes.
- Holdout externe : 100 moteurs / 13 096 lignes.

### Évaluation externe

Une évaluation explicite du champion sur le holdout externe (jamais consulté pendant le développement) donne environ :

- Recall : **~0,952**
- Précision : ~0,321
- F1 : ~0,480
- PR-AUC : ~0,767
- ROC-AUC : ~0,990

Ce test externe est séparé du quality gate de CI/CD. Il doit être utilisé avec parcimonie, comme preuve finale, et jamais comme boucle de tuning.

Version du champion empaqueté : `optimized-302137b8230f` (l'identifiant est dérivé du commit git qui a produit l'artefact, pour garder une traçabilité exacte entre le code et le modèle).

## Services Disponibles

| Service | URL locale | Identifiants |
|---|---|---|
| API REST | http://localhost:8081 | aucun |
| Documentation API (Swagger) | http://localhost:8081/docs | aucun |
| Dashboard Streamlit | http://localhost:8501 | aucun |
| MLflow UI | http://localhost:5000 | aucun |
| Prometheus | http://localhost:9090 | aucun |
| Grafana | http://localhost:3001 | admin / admin (local uniquement) |

Les ports sont configurables via `API_PORT`, `GRAFANA_PORT`, `MLFLOW_PORT` et `DASHBOARD_PORT` dans `.env`, utile si l'un d'eux est déjà occupé par un autre projet sur la machine.

## Installation et Démarrage

### Prérequis

- Python 3.12 (recommandé, aligné avec la CI/CD et le déploiement)
- Docker et Docker Compose (pour la stack complète)
- Git

### 1. Cloner le dépôt

```bash
git clone https://github.com/messanh0139/predictmaint-ai.git
cd predictmaint-ai
```

### 2. Créer l'environnement Python

**Linux / macOS :**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints-model.txt
```

**Windows (PowerShell) :**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints-model.txt
```

Si PowerShell bloque l'exécution de `Activate.ps1` :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`requirements.txt` installe tout ce qu'il faut pour développer, tester et entraîner en local (il inclut `requirements-dev.txt`, qui inclut lui-même `requirements-train.txt`). Pour un environnement plus léger, `requirements-api.txt` seul suffit à faire tourner l'API avec un modèle déjà entraîné.

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Voir la section [Variables d'Environnement](#variables-denvironnement).

### 4. Entraîner un premier modèle

```bash
python -m src.data.prepare
python -m src.features.select_features
python -m src.models.train
python -m src.models.quality_gate
```

### 5. Lancer la stack complète

```bash
docker compose up --build -d
```

**Sur Linux**, les conteneurs `api` et `dashboard` tournent avec un utilisateur non-root. Comme `./data` et `./models` sont montés depuis l'hôte, il faut leur donner les droits d'écriture pour que le conteneur `api` puisse écrire (notamment pour le réentraînement automatique) :

```bash
chmod -R o+w data models
```

### 6. Arrêter les services

```bash
docker compose down
```

## Utilisation

### Prédiction via le dashboard

1. Ouvrir http://localhost:8501
2. Dans l'onglet **Démonstration prédictive**, choisir un moteur et faire varier le cycle observé
3. Cliquer sur **Analyser le risque**
4. Le modèle retourne la probabilité de défaillance, le niveau de risque et le seuil décisionnel utilisé

### Déposer de nouvelles données et déclencher un réentraînement

1. Aller sur l'onglet **Réentraînement automatique**
2. Téléverser un CSV au format attendu (un exemple téléchargeable est fourni dans l'onglet)
3. Le pipeline complet se déclenche **automatiquement**, sans action supplémentaire
4. La page affiche l'avancement en direct et bascule sur le nouveau modèle dès qu'il est prêt

### Déclencher manuellement via l'API

```bash
curl -X POST "http://localhost:8081/retrain/upload" \
  -F "file=@nouvelles_donnees.csv"

curl "http://localhost:8081/retrain/status"
```

## Développement avec Docker

L'environnement complet se lance avec une seule commande. Docker Compose orchestre 5 services (API, Dashboard, MLflow, Prometheus, Grafana) et gère les dépendances entre eux.

```bash
docker compose up --build -d
```

Pour reconstruire les images après une modification du code :

```bash
docker compose up -d --build
```

Pour consulter les logs d'un service en particulier :

```bash
docker compose logs -f api
docker compose logs -f dashboard
```

Pour lancer un réentraînement manuel complet (avec optimisation Optuna) et envoyer ses runs à MLflow :

```bash
docker compose run --rm trainer
```

## Tests

```bash
ruff check api src tests
pytest --cov=src --cov=api --cov-report=term-missing
```

Les tests vérifient notamment l'absence de chevauchement entre moteurs, la causalité des features, la non-utilisation des colonnes interdites, la reconstruction du RUL, le contrat de l'API, l'exposition Prometheus et le respect du **seuil versionné de chaque prédiction** dans le monitoring multi-version. La version livrée passe **20 tests automatisés**. Le rapport consolidé est généré dans `reports/project_validation.json` par `python scripts/validate_project.py --tests-passed <N>`.

## CI/CD (GitHub Actions)

Le workflow `.github/workflows/deploy.yml` se déclenche à chaque push sur `main` :

1. exécute les contrôles statiques, les tests unitaires et les tests anti-fuite ;
2. construit et publie une image trainer immuable ;
3. exécute le Cloud Run Job avec les prédictions et feedbacks de production stockés dans GCS ;
4. bloque le déploiement si le quality gate échoue ;
5. récupère le champion validé depuis le bucket d'artefacts ;
6. construit et déploie l'API privée et le dashboard Streamlit public, en images immuables taguées par SHA ;
7. réalise des smoke tests et publie les URL dans le résumé GitHub Actions.

Secrets nécessaires : `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOYER_SERVICE_ACCOUNT`, `GCP_RUNTIME_SERVICE_ACCOUNT`, `GCP_TRAINER_SERVICE_ACCOUNT`. Variables : `GCP_REGION`, `PREDICTION_BUCKET`, `MODEL_ARTIFACT_BUCKET`, `MLOPS_OPTUNA_TRIALS`, `MLFLOW_TRACKING_URI` (optionnelle). Le workflow manuel `.github/workflows/certification-evaluate.yml` exécute l'évaluation externe séparément, pour ne jamais en faire un signal de tuning indirect.

## Déploiement sur Google Cloud Platform

Cible de déploiement : **Artifact Registry + Cloud Run**. L'API est déployée **privée** (`--no-allow-unauthenticated`) avec une identité runtime séparée de l'identité de déploiement ; le dashboard Streamlit est déployé **public** (`--allow-unauthenticated`) et invoque l'API en interne avec un jeton d'identité de son propre compte de service. L'authentification GitHub → GCP se fait par Workload Identity Federation, sans clé JSON de compte de service stockée dans le dépôt.

> Ce dépôt n'est pas encore déployé sur un projet GCP en continu : la procédure de provisionnement (bootstrap, comptes de service, buckets, déploiement, job de réentraînement planifié) est prête et documentée dans `docs/06_deploiement_gcp.md`, à exécuter avec `./infra/gcp/bootstrap.sh` puis `./infra/gcp/deploy.sh` (API privée), `./infra/gcp/deploy_mlflow.sh` et `./infra/gcp/deploy_grafana.sh` (MLOps public, optionnels — Grafana lit Cloud Monitoring nativement, pas de Prometheus à déployer sur GCP) et enfin `./infra/gcp/deploy_dashboard.sh` (dashboard public, URL de démonstration).

## Notebooks

| Notebook | Contenu |
|---|---|
| `01_eda.ipynb` | Analyse exploratoire, qualité des données, durée de vie, déséquilibre de la cible |
| `02_feature_engineering.ipynb` | Construction des features temporelles causales |
| `03_feature_selection.ipynb` | Cinq méthodes de sélection, fit sur TRAIN uniquement |
| `04_model_training.ipynb` | Baseline explicite, calibration du seuil, comparaison des modèles |
| `05_model_evaluation.ipynb` | Optimisation/promotion puis ouverture contrôlée du holdout externe |
| `06_monitoring.ipynb` | PSI, drift, performance différée et boucle MLOps |

Les notebooks ne masquent pas les étapes fondamentales derrière des fonctions utilitaires : le chargement, le calcul du RUL, la séparation des moteurs, les contrôles de qualité et les métriques sont montrés explicitement, avant que la version réutilisable et testée ne soit appelée depuis `src/`. Voir `notebooks/README.md` et `docs/14_notebooks_et_code_production.md`.

## Fonctionnalités du Projet

**Prédiction en temps réel**
L'API expose **/predict**, qui accepte l'historique d'un moteur et retourne sa probabilité de défaillance, son niveau de risque et le seuil de décision utilisé pour la produire.

**Réentraînement automatique déclenché par upload**
Un CSV de nouvelles données labellisées déposé depuis le dashboard ou envoyé sur **/retrain/upload** déclenche immédiatement, sans intervention manuelle, le pipeline complet (préparation, sélection, entraînement, quality gate, enregistrement) et bascule l'API sur le nouveau champion dès qu'il est prêt.

**Détection de dérive des données**
`src/monitoring/drift.py` compare la distribution des nouvelles données à une référence figée sur TRAIN, variable par variable, via un score PSI.

**Surveillance de la performance en production**
La vérité terrain reçue via **/feedback** permet de recalculer recall, PR-AUC, F1 et coût métier, avec un diagnostic par version de modèle.

**Traçabilité complète**
Chaque entraînement enregistre hyperparamètres, métriques, empreinte SHA256 du jeu de données et artefact modèle, dans un registre local et en option dans MLflow.

**Dashboard métier intégré**
Le dashboard Streamlit centralise la démonstration prédictive, les métriques de performance, le déclenchement du réentraînement et le parcours de présentation, en une seule interface.

## Variables d'Environnement

Créer un fichier `.env` à la racine à partir de `.env.example` :

```bash
cp .env.example .env
```

Variables disponibles (toutes ont une valeur par défaut raisonnable en local) :

```text
MODEL_PATH=models/model.joblib
MODEL_METADATA_PATH=models/model_metadata.json
PREDICTION_LOG_PATH=/tmp/predictions.jsonl
FEEDBACK_LOG_PATH=/tmp/feedback.jsonl
PREDICTION_BUCKET=                # optionnel : active la persistance Cloud Storage
LOG_LEVEL=INFO
FALSE_NEGATIVE_COST=10000
FALSE_POSITIVE_COST=500
MIN_RECALL=0.85
MIN_PR_AUC=0.70
API_PORT=8081
GRAFANA_PORT=3001
MLFLOW_PORT=5000
DASHBOARD_PORT=8501
```

Déploiement GCP uniquement (non utilisées en local) : `GCP_PROJECT_ID`, `GCP_REGION`, `PREDICTION_BUCKET`, `MODEL_ARTIFACT_BUCKET`, `MLOPS_OPTUNA_TRIALS`, `MLFLOW_TRACKING_URI` — voir `docs/06_deploiement_gcp.md`.

## Limites connues

- Le jeu de données est simulé : les résultats ne prouvent pas une performance industrielle réelle.
- Le seuil de 30 cycles et les coûts FP/FN sont des hypothèses métier posées pour la démonstration.
- Le dataset FD001 ne représente qu'une seule condition opérationnelle et un seul mode de panne.
- Le monitoring local Prometheus/Grafana est une preuve technique ; en production sur GCP, Cloud Monitoring/Logging est privilégié.
- Le modèle doit être réévalué sur des données représentatives avant tout usage industriel réel.

Voir `docs/10_risques_limites.md` et `docs/11_model_card.md`.

## Conclusion

Ce projet démontre la mise en place d'un pipeline MLOps complet, depuis l'analyse exploratoire jusqu'au déploiement et à la surveillance en production. Le champion retenu (XGBoost optimisé) atteint un recall de 100 % sur la validation verrouillée : aucun moteur à risque de défaillance n'est manqué, ce qui représente l'apport concret attendu par les équipes de maintenance.

L'anti-fuite de données est traitée comme un risque de conception à part entière, pas comme un détail d'implémentation. Docker garantit la reproductibilité de l'environnement. Le mécanisme champion/challenger évite de promouvoir un modèle plus complexe mais moins utile. Le dashboard centralise la démonstration, le monitoring et le déclenchement du réentraînement en une seule interface.

## Contributeur

Messanh Yaovi KODJO — kmessanhyaovi@gmail.com

## Licence

Ce projet est sous licence MIT.
