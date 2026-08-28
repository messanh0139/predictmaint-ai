# PredictMaint AI

Projet Data Science / MLOps de maintenance prédictive construit à partir du **NASA C-MAPSS FD001**.

## Finalité métier

Prédire si un moteur présente un risque de défaillance dans les **30 prochains cycles** afin de prioriser les inspections et interventions de maintenance. Le projet couvre le cycle de vie complet d'un système Machine Learning : cadrage, préparation, feature engineering, sélection de variables, entraînement, optimisation, sauvegarde/versioning, API, CI/CD, monitoring, drift et réentraînement.

> Important : les coûts métier utilisés dans le projet (FN = 10 000, FP = 500) sont des hypothèses de mise en situation. Dans un projet réel, ils doivent être validés avec le commanditaire.

## Architecture fonctionnelle

```text
NASA C-MAPSS FD001
        |
        v
Validation + empreintes SHA256
        |
        v
Split par moteur AVANT transformations
  +-----------+--------------+----------------+
  |           |              |                |
TRAIN     CALIBRATION     VALIDATION      NASA TEST
  |           |              |                |
Features   Features        Features          Features
causales   causales        causales          causales
  |           |              |                |
Feature      seuil        choix modèle      évaluation
selection   décision      / promotion       externe finale
  |
  v
Logistic / Random Forest / XGBoost
  |
  v
Optuna + Group CV (TRAIN uniquement)
  |
  v
Champion / Challenger
  |
  v
MLflow + artefacts versionnés
  |
  v
FastAPI -> Docker -> CI/CD -> Google Cloud Run
  |
  +--> Prometheus/Grafana local
  +--> Cloud Logging/Monitoring GCP
  +--> prédictions + feedback -> drift/performance -> retraining
```

## Principe anti-data leakage

Le projet traite explicitement la fuite de données comme un risque de conception :

1. **Split trois voies par `engine_id` avant le feature engineering et avant toute EDA supervisée** : TRAIN / CALIBRATION / VALIDATION sont constitués de moteurs distincts.
2. **Holdout externe NASA réellement verrouillé** : `RUL_FD001.txt` n'est ni chargé ni matérialisé pendant le pipeline de développement. `test_FD001 + RUL_FD001` n'est ouvert que par `python -m src.models.evaluate` pour l'évaluation externe finale.
3. **Features temporelles causales** : une ligne au cycle `t` n'utilise que le cycle courant et les cycles passés du même moteur.
4. **Variables interdites** : `RUL`, cible, identifiant moteur et colonnes dérivées de la vérité terrain sont exclues du modèle.
5. **EDA utilisant RUL/cible et feature selection sur TRAIN seulement** : les décisions humaines de sélection ne consultent pas VALIDATION/TEST.
6. **Imputation et scaling encapsulés dans des pipelines sklearn**, ajustés pendant le `fit` du TRAIN.
7. **Seuil de décision sur CALIBRATION seulement**.
8. **Choix du champion sur VALIDATION seulement**.
9. **Optuna utilise une validation croisée groupée par moteur sur TRAIN seulement**.
10. **Le test NASA n'est pas exécuté dans le retraining automatique**, afin d'éviter qu'il ne devienne progressivement un signal de développement.

Voir `docs/04_data_leakage.md`.

## Résultats actuellement reproduits

### Qualité des données brutes

- Train : 20 631 lignes, 100 moteurs, 26 colonnes.
- Test NASA : 13 096 lignes, 100 moteurs, 26 colonnes (contrôle structurel uniquement avant l'évaluation finale).
- Valeurs manquantes : 0.
- Doublons `(engine_id, cycle)` : 0.
- Durée de vie train : min 128, médiane 199, moyenne 206,31, max 362 cycles.
- Cible `RUL <= 30` analysée après split sur TRAIN uniquement : 2 170 positifs sur 14 407 (15,06 %).

### Split de développement actuel

- TRAIN : 70 moteurs / 14 407 lignes.
- CALIBRATION : 15 moteurs / 3 160 lignes.
- VALIDATION : 15 moteurs / 3 064 lignes.
- Holdout NASA : 100 moteurs / 13 096 lignes.

### Champion de développement actuel

Après 10 essais Optuna de vérification, le challenger **XGBoost optimisé** a été promu car il améliore le critère métier sur la validation verrouillée :

- Recall validation : **1,000**
- Precision validation : ~0,564
- F1 : ~0,721
- PR-AUC : ~0,946
- ROC-AUC : ~0,988
- coût métier validation : **180 000** contre **228 000** pour le précédent champion Random Forest.

Version du champion empaqueté : `optimized-b623fc94786a`.

La promotion n'est pas basée sur la complexité du modèle : elle suit le mécanisme champion/challenger et les guardrails. Le rapport `models/promotion_report.json` conserve la décision.

### Évaluation externe NASA

Une évaluation explicite du champion actuel sur le holdout NASA donne environ :

- Recall : **~0,952**
- Precision : ~0,321
- F1 : ~0,480
- PR-AUC : ~0,767
- ROC-AUC : ~0,990

Le test externe est séparé du quality gate de CI/CD. Il doit être utilisé avec parcimonie comme preuve finale, pas comme boucle de tuning.

## Correspondance Bloc 5

Voir la matrice détaillée `docs/00_matrice_bloc5.md`.

| Compétence | Preuve principale |
|---|---|
| C5.1.1 | `docs/01_besoin_metier.md` |
| C5.1.2 | `docs/02_strategie_ml.md` |
| C5.1.3 | `docs/03_choix_technologiques.md` |
| C5.2.1 | `src/features/build_features.py`, notebook 02 |
| C5.2.2 | `src/features/select_features.py`, notebook 03 |
| C5.2.3 | `src/models/train.py`, notebook 04 |
| C5.2.4 | `src/models/optimize.py`, `models/optimization_report.json` |
| C5.3.1 | Joblib + métadonnées + MLflow |
| C5.3.2 | FastAPI + Docker + CI/CD + Cloud Run |
| C5.3.3 | PSI/Evidently + Prometheus/Grafana + performance feedback |
| C5.3.4 | `src/pipelines/retrain.py` + collecte de feedback |

## Installation

Python 3.12 recommandé pour la CI/CD et le déploiement. Le pipeline de déploiement réentraîne le modèle dans le même environnement Python que celui utilisé pour construire l’image, ce qui limite les risques de compatibilité de sérialisation.

```bash
python -m venv .venv
```

Windows PowerShell :

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints-model.txt
```

Si PowerShell bloque `Activate.ps1` :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```


## Lecture pédagogique des notebooks

Les notebooks ne masquent pas les étapes fondamentales derrière des fonctions utilitaires : le chargement avec `pd.read_csv`, le calcul du RUL, la séparation des moteurs, les contrôles de qualité, les méthodes de sélection et les métriques sont montrés explicitement. Une fois la logique comprise, la version réutilisable est appelée depuis `src/`.

Cette organisation répond à deux objectifs : **être clair pour le jury** et **rester industrialisable**. Voir `notebooks/README.md` et `docs/14_notebooks_et_code_production.md`.

## Pipeline de développement

```bash
python -m src.data.prepare
python -m src.features.select_features
python -m src.models.train
python -m src.models.quality_gate
```

Optimisation :

```bash
python -m src.models.optimize --trials 30
python -m src.models.promote
python -m src.models.quality_gate
```

Évaluation externe finale uniquement :

```bash
python -m src.models.evaluate
```

Cette commande charge le holdout NASA au dernier moment. `src.data.prepare` ne génère volontairement **aucun** `data/processed/test_features.csv`.

Réentraînement automatisable, sans consommation du test NASA :

```bash
python -m src.pipelines.retrain --optimize --trials 30
```

## API

```bash
uvicorn api.main:app --reload --port 8080
```

Endpoints :

- `GET /live` : liveness.
- `GET /ready` : modèle chargé et contrat valide.
- `GET /metrics` : métriques Prometheus.
- `POST /predict` : prédiction à partir de l'historique d'un moteur.
- `POST /feedback` : vérité terrain différée pour monitoring de performance.

## Tests

```bash
ruff check api src tests
pytest --cov=src --cov=api --cov-report=term-missing
```

Les tests vérifient notamment l'absence de chevauchement de moteurs, la causalité des features, la non-utilisation des colonnes interdites, la reconstruction RUL, le contrat API, l'exposition Prometheus et le respect du **seuil versionné de chaque prédiction** dans le monitoring multi-version. Le rapport consolidé est généré dans `reports/project_validation.json` par `python scripts/validate_project.py --tests-passed <N>`.

## Validation finale de cette archive

La version livrée a passé **19 tests automatisés** ainsi que des contrôles de cohérence des artefacts : absence de chevauchement de moteurs, concordance du manifeste SHA-256 avec le modèle, version du champion/registre/holdout, quality gate, promotion, verrouillage du test externe, seuil appris sur CALIBRATION et provisioning Grafana. Le statut consolidé est `PASS` dans `reports/project_validation.json`.

Le build Docker et le déploiement GCP ne peuvent pas être exécutés dans l'environnement de génération de cette archive : Docker n'y est pas installé et aucun projet/credential Google Cloud utilisateur n'est disponible. Les Dockerfiles, workflows et fichiers GCP ont en revanche été validés statiquement.

## Docker / monitoring local

```bash
docker compose up --build
```

- API : `http://localhost:8081`
- Prometheus : `http://localhost:9090`
- Grafana : `http://localhost:3001` (`admin` / `admin`, environnement local uniquement)
- MLflow : `http://localhost:5000`
- Dashboard Streamlit : `http://localhost:8501`

Les ports hôtes sont configurables avec `API_PORT`, `GRAFANA_PORT`, `MLFLOW_PORT`
et `DASHBOARD_PORT` dans un fichier `.env`. Pour lancer un réentraînement et envoyer
ses runs à MLflow :

```bash
docker compose run --rm trainer
```

## Google Cloud Platform

Cible : **Artifact Registry + Cloud Run**, service privé, identité runtime séparée de l'identité de déploiement. Les prédictions peuvent être historisées dans Cloud Storage.

```bash
export PROJECT_ID="mon-projet-gcp"
export REGION="europe-west1"
./infra/gcp/bootstrap.sh
./infra/gcp/deploy.sh
```

Pour GitHub Actions, le workflow utilise Workload Identity Federation et évite les clés JSON de compte de service.

Voir `docs/06_deploiement_gcp.md` et `docs/13_architecture.md`.

### Déploiement automatique sur push

Chaque push sur `main` déclenche `.github/workflows/deploy.yml`. Le workflow :

1. exécute les contrôles statiques, tests unitaires et tests anti-fuite ;
2. construit et publie une image trainer immuable ;
3. exécute le Cloud Run Job avec les prédictions et feedbacks de production stockés dans GCS ;
4. bloque le déploiement si le quality gate échoue ;
5. récupère le champion validé depuis le bucket d'artefacts ;
6. construit et déploie l'API privée et le dashboard Streamlit public ;
7. réalise des smoke tests et publie les URL dans le résumé GitHub Actions.

MLflow est alimenté si la variable GitHub `MLFLOW_TRACKING_URI` pointe vers un serveur
accessible depuis Cloud Run. Le serveur MLflow local de Docker Compose n'est pas accessible
depuis les runners GitHub hébergés.

## Boucle de données de production

L’API conserve l’historique brut ayant servi à une prédiction. Lorsqu’un feedback réel arrive, `src.data.collect_feedback` reconstruit les features causales de cette observation labellisée. Au retraining, ces nouvelles observations peuvent être ajoutées **uniquement au TRAIN** via `INCLUDE_PRODUCTION_FEEDBACK=1`, sans contaminer CALIBRATION, VALIDATION ou le holdout NASA.

Le job de retraining peut ensuite enregistrer le champion dans le registre local/MLflow et, si `MODEL_ARTIFACT_BUCKET` est configuré, persister le modèle versionné dans Cloud Storage.

## Limites connues

- C-MAPSS est un dataset simulé : les résultats ne prouvent pas une performance industrielle réelle.
- Le seuil de 30 cycles et les coûts FP/FN sont des hypothèses métier de démonstration.
- Le dataset FD001 ne représente qu'une condition opérationnelle et un mode de panne.
- Le monitoring local Prometheus/Grafana est une preuve technique ; sur GCP, Cloud Monitoring/Logging est privilégié pour la production.
- Le modèle doit être réévalué sur des données représentatives avant tout usage industriel réel.

Voir `docs/10_risques_limites.md` et `docs/11_model_card.md`.

### Raccourcis Windows PowerShell

```powershell
.\scripts\setup.ps1
.\scripts\run_pipeline.ps1
```
#   p r e d i c t m a i n t - a i  
 