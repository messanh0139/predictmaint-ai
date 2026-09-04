# Démonstration du Retraining Automatique

Ce guide présente 3 scénarios pour démontrer le retraining automatique.

## Scénario 1 : Démonstration Locale avec Airflow (Développement)

### Contexte
Vous développez en local et voulez montrer l'orchestration Airflow des pipelines ETL → MLOps.

### Étapes

#### 1. Démarrer la stack locale
```bash
cd infrastructure/deployment
docker-compose up -d
```

Services démarrés :
- PostgreSQL (données propres)
- Airflow Webserver + Scheduler
- MLflow (tracking)
- Prometheus + Grafana (monitoring)

#### 2. Accéder à Airflow
URL : http://localhost:8080
Login : `admin` / `admin`

#### 3. Activer les DAGs
Dans l'interface Airflow :
- Chercher `pipeline_1_etl_ingestion` → Toggle ON
- Chercher `pipeline_2_training_mlops` → Toggle ON

#### 4. Déclencher Pipeline 1 manuellement
- Cliquer sur `pipeline_1_etl_ingestion`
- Bouton "Play" → Trigger DAG

#### 5. Observer l'exécution
**Pipeline 1 - ETL** (5-10 min) :
```
extract_data → transform_data → load_to_postgresql → build_features → validate_pipeline
```

**Pipeline 2 - MLOps** (se déclenche automatiquement après Pipeline 1) :
```
wait_for_etl_completion (attend Pipeline 1)
         ↓
extract_from_postgresql
         ↓
train_multiple_models (Logistic, Random Forest, XGBoost)
         ↓
optimize_hyperparameters (Optuna 30 trials)
         ↓
evaluate_select_champion
         ↓
register_model_to_gcp + track_with_mlflow
         ↓
validate_pipeline
```

#### 6. Vérifier MLflow
URL : http://localhost:5000

Vous verrez :
- **Experiments** : Runs de tous les modèles entraînés
- **Metrics** : Accuracy, Precision, Recall, F1-Score, PR-AUC, ROC-AUC
- **Parameters** : Hyperparamètres de chaque modèle
- **Artifacts** : Modèles joblib sauvegardés

#### 7. Points à montrer dans votre mémoire

**Captures d'écran à inclure :**
1. Airflow Graph View des 2 DAGs avec toutes les tâches vertes
2. Airflow Tree View montrant l'historique d'exécution
3. Logs d'une tâche (ex: `train_multiple_models`)
4. MLflow : Table de comparaison des 3+ modèles
5. MLflow : Courbes de métriques (ROC, PR)
6. MLflow : Paramètres du modèle champion

**Narrative pour le mémoire :**

> "L'orchestration des pipelines est assurée par Apache Airflow. Le Pipeline 1 (ETL) s'exécute quotidiennement pour ingérer et transformer les données capteurs, puis les charger dans PostgreSQL. Le Pipeline 2 (MLOps) attend la complétion du Pipeline 1 via un ExternalTaskSensor, garantissant ainsi la disponibilité des données fraîches avant l'entraînement.
>
> Le Pipeline 2 compare rigoureusement au moins 3 architectures de modèles (Régression Logistique, Random Forest, XGBoost), optimise les hyperparamètres via Optuna (30 trials), et sélectionne automatiquement le champion selon les métriques métier (recall, PR-AUC, coût de maintenance). Toutes les expérimentations sont trackées dans MLflow pour assurer la traçabilité et la reproductibilité."

---

## Scénario 2 : Démonstration Production avec GitHub Actions

### Contexte
Vous avez déjà configuré GCP et voulez montrer le déploiement automatique en production.

### Étapes

#### 1. Préparer un changement à déployer
```bash
cd /home/jes/Bureau/predictmaint-ai

# Option A : Modifier un paramètre (ex: nombre de trials Optuna)
# Éditer src/config.py ou un fichier de config

# Option B : Ajouter simplement une mise à jour
echo "Retraining automatique production" >> CHANGELOG.md

git add .
git commit -m "deploy: trigger production retraining"
git push origin main
```

#### 2. Observer GitHub Actions en temps réel
1. Aller sur https://github.com/messanh0139/predictmaint-ai/actions
2. Cliquer sur le workflow "MLOps - Retrain and Deploy" en cours
3. Observer les étapes (15-20 minutes) :

```
✓ Checkout code
✓ Setup Python
✓ Install dependencies
✓ Static checks (ruff)
✓ Unit tests (pytest)
✓ Validate GCP config
✓ Authenticate to GCP
✓ Build trainer image
✓ Deploy retrain job
✓ Execute retrain job (récupère feedback GCS → retrain → quality gate)
✓ Download champion model
✓ Build API/Dashboard/Grafana images
✓ Deploy API (Cloud Run)
✓ Deploy Dashboard (Cloud Run)
✓ Deploy Grafana (Cloud Run)
✓ Smoke tests
```

#### 3. Récupérer les URLs publiques
Dans l'onglet "Summary" du workflow, vous verrez :

```
### Production deployed
- Dashboard React: https://predictmaint-dashboard-abc123.run.app
- API: https://predictmaint-api-abc123.run.app
- Grafana: https://predictmaint-grafana-abc123.run.app (mot de passe admin dans Secret Manager)
- Cloud Monitoring: métriques custom sous custom.googleapis.com/predictmaint/*
- Model image tag: abc123def456
```

#### 4. Tester l'API déployée
```bash
API_URL="https://predictmaint-api-abc123.run.app"

# Health check
curl "${API_URL}/ready"

# Documentation Swagger
open "${API_URL}/docs"

# Test de prédiction
curl -X POST "${API_URL}/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 999,
    "history": [
      {
        "cycle": 1,
        "setting_1": 0.0015,
        "setting_2": 0.0003,
        "setting_3": 100.0,
        "sensor_1": 518.67,
        "sensor_2": 641.82,
        "sensor_3": 1589.7,
        "sensor_4": 1400.6,
        "sensor_5": 14.62,
        "sensor_6": 21.61,
        "sensor_7": 554.36,
        "sensor_8": 2388.06,
        "sensor_9": 9046.19,
        "sensor_10": 1.3,
        "sensor_11": 47.47,
        "sensor_12": 521.66,
        "sensor_13": 2388.02,
        "sensor_14": 8138.62,
        "sensor_15": 8.4195,
        "sensor_16": 0.03,
        "sensor_17": 392,
        "sensor_18": 2388,
        "sensor_19": 100.0,
        "sensor_20": 39.06,
        "sensor_21": 23.419
      }
    ]
  }'
```

#### 5. Accéder au Dashboard public
Ouvrir dans le navigateur : `https://predictmaint-dashboard-abc123.run.app`

Vous verrez :
- Interface de prédiction interactive
- Sélection de moteurs
- Visualisation des résultats
- Graphiques de métriques

#### 6. Accéder à Grafana
```bash
# Récupérer le mot de passe admin
gcloud secrets versions access latest --secret="predictmaint-grafana-admin"

# Ouvrir Grafana
open "https://predictmaint-grafana-abc123.run.app"
# Login: admin
# Password: (mot de passe récupéré ci-dessus)
```

Dans Grafana vous verrez :
- Métriques de drift PSI par feature
- Drift share global
- Métriques de prédictions (total, latence)
- Alertes configurées

#### 7. Points à montrer dans votre mémoire

**Captures d'écran à inclure :**
1. GitHub Actions workflow en succès (toutes les étapes vertes)
2. GitHub Actions Summary avec les URLs publiques
3. API Swagger UI (documentation auto-générée)
4. Dashboard React avec prédiction
5. Grafana : Dashboard de monitoring drift
6. GCP Console : Cloud Run services déployés

**Narrative pour le mémoire :**

> "Le déploiement en production est entièrement automatisé via GitHub Actions et Google Cloud Platform. À chaque push sur la branche main, le workflow CI/CD exécute les tests de validation, déclenche un job de retraining sur Cloud Run qui récupère automatiquement le feedback production depuis Cloud Storage, entraîne les modèles candidats, applique un quality gate (recall ≥ 85%, PR-AUC ≥ 75%), et ne déploie que si le nouveau modèle surpasse le champion actuel.
>
> Les services (API FastAPI, Dashboard React, Grafana) sont déployés sur Cloud Run avec mise à l'échelle automatique (0 à 5 instances), permettant de gérer les pics de charge tout en minimisant les coûts en période creuse. L'ensemble du système est exposé via des URLs publiques sécurisées et surveillées en temps réel par Prometheus et Grafana."

---

## Scénario 3 : Démonstration Interactive avec Upload CSV

### Contexte
Vous voulez montrer comment un utilisateur métier peut déclencher un retraining en uploadant de nouvelles données terrain.

### Étapes

#### 1. Préparer un fichier CSV de nouvelles données

Créer `nouvelles_donnees.csv` :
```csv
engine_id,cycle,setting_1,setting_2,setting_3,sensor_1,sensor_2,sensor_3,sensor_4,sensor_5,sensor_6,sensor_7,sensor_8,sensor_9,sensor_10,sensor_11,sensor_12,sensor_13,sensor_14,sensor_15,sensor_16,sensor_17,sensor_18,sensor_19,sensor_20,sensor_21,actual_failure_within_30_cycles
1001,1,0.0015,0.0003,100.0,518.67,641.82,1589.7,1400.6,14.62,21.61,554.36,2388.06,9046.19,1.3,47.47,521.66,2388.02,8138.62,8.4195,0.03,392,2388,100.0,39.06,23.419,0
1001,2,-0.0005,-0.0002,100.0,518.67,641.81,1589.6,1401.5,14.62,21.61,554.35,2388.05,9046.10,1.3,47.48,521.65,2388.01,8138.60,8.4190,0.03,392,2388,100.0,39.05,23.420,0
1002,1,0.0012,0.0004,100.0,518.70,641.85,1589.8,1400.8,14.63,21.62,554.40,2388.10,9046.25,1.3,47.50,521.70,2388.05,8138.70,8.4200,0.03,393,2389,100.0,39.10,23.425,1
```

#### 2. Uploader via l'API
```bash
API_URL="https://predictmaint-api-abc123.run.app"  # Ou http://localhost:8000 en local

curl -X POST "${API_URL}/retrain/upload" \
  -F "file=@nouvelles_donnees.csv"
```

Réponse :
```json
{
  "status": "retrain_triggered",
  "rows_added": 3
}
```

#### 3. Suivre l'avancement du retraining
```bash
# Polling du statut
while true; do
  curl "${API_URL}/retrain/status" | jq
  sleep 10
done
```

Pendant l'exécution :
```json
{
  "state": "running",
  "started_at": "2026-09-04T16:00:00.123456Z",
  "finished_at": null,
  "rows_added": 3,
  "error": null,
  "model_version": null
}
```

Après succès :
```json
{
  "state": "completed",
  "started_at": "2026-09-04T16:00:00.123456Z",
  "finished_at": "2026-09-04T16:08:32.987654Z",
  "rows_added": 3,
  "error": null,
  "model_version": "optimized-abc123def456"
}
```

#### 4. Vérifier que le nouveau modèle est chargé
```bash
# L'API recharge automatiquement le modèle
curl "${API_URL}/ready"
```

Le modèle en mémoire est maintenant la nouvelle version.

#### 5. Points à montrer dans votre mémoire

**Captures d'écran à inclure :**
1. Requête curl d'upload du CSV
2. Réponse JSON "retrain_triggered"
3. Polling du status (running → completed)
4. Logs de l'API montrant le retraining en background

**Narrative pour le mémoire :**

> "L'API expose un endpoint /retrain/upload permettant aux équipes métier de soumettre de nouvelles données terrain labelisées. Le système déclenche automatiquement un pipeline de retraining en arrière-plan (thread daemon) qui fusionne les nouvelles données avec l'historique, entraîne les modèles candidats, applique le quality gate, et recharge le nouveau champion en mémoire sans interruption de service.
>
> Cette approche permet un retraining ad-hoc piloté par les utilisateurs métier, complémentaire au retraining planifié hebdomadaire orchestré par Airflow."

---

## Récapitulatif : Quelle méthode pour quelle démo ?

| Méthode | Environnement | Durée | Public cible | Points forts |
|---------|--------------|-------|--------------|--------------|
| **Airflow local** | Développement | 15-20 min | Technique (jury) | Orchestration, dépendances, logs détaillés |
| **GitHub Actions** | Production GCP | 15-20 min | Tous | CI/CD, URLs publiques, qualité production |
| **API Upload** | Local ou Prod | 5-10 min | Métier | Interactivité, simplicité utilisateur |

**Recommandation pour votre soutenance :**
1. **Démo principale** : GitHub Actions (URLs publiques à partager)
2. **Démo technique** : Airflow (Graph View + MLflow)
3. **Démo bonus** : Upload CSV interactif

Vous pouvez inclure les 3 dans votre mémoire avec des sections différentes :
- Partie "Architecture technique" → Airflow
- Partie "Déploiement production" → GitHub Actions
- Partie "Utilisation métier" → API Upload
