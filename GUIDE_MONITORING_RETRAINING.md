# Guide Monitoring & Retraining Automatique

Ce guide explique comment injecter de nouvelles données, monitorer les performances et déclencher le retraining automatique.

## 🔄 Vue d'ensemble du flux

```
┌─────────────────┐
│ 1. PRÉDICTION   │  ← Nouvelles données capteurs
│    POST /predict│
└────────┬────────┘
         │
         ├──► Logs local : /tmp/predictions.jsonl
         ├──► GCS bucket : predictions/{id}.json
         └──► Métriques Prometheus/Cloud Monitoring

┌─────────────────┐
│ 2. FEEDBACK     │  ← Vérité terrain (30 jours après)
│  POST /feedback │
└────────┬────────┘
         │
         ├──► Logs local : /tmp/feedback.jsonl
         └──► GCS bucket : feedback/{id}.json

┌─────────────────────┐
│ 3. MONITORING       │  ← Calcul automatique
│  Dérive des données │
└────────┬────────────┘
         │
         ├──► Drift PSI par feature (toutes les 5 min)
         ├──► Drift share global
         └──► Alertes Grafana si PSI > seuil

┌────────────────────────┐
│ 4. RETRAINING          │  ← Déclenchement manuel ou auto
│  POST /retrain/upload  │
│  ou Cloud Run Job      │
└────────┬───────────────┘
         │
         ├──► Collecte feedback GCS
         ├──► Fusion avec données TRAIN
         ├──► Entraînement 3+ modèles
         ├──► Quality gate (recall, PR-AUC)
         ├──► Promotion champion
         └──► Upload GCS + Reload API
```

---

## 📡 1. Envoyer des nouvelles données de prédiction

### Endpoint : `POST /predict`

Chaque fois qu'un moteur est en fonctionnement, vous envoyez l'historique complet de ses cycles avec les relevés capteurs.

### Format de la requête

```json
{
  "engine_id": 42,
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
    },
    {
      "cycle": 2,
      "setting_1": -0.0005,
      "setting_2": -0.0002,
      "setting_3": 100.0,
      "sensor_1": 518.67,
      ...
    }
  ]
}
```

### Réponse

```json
{
  "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-09-04T15:30:00.123456Z",
  "engine_id": 42,
  "last_cycle": 2,
  "failure_probability": 0.23,
  "risk": "LOW",
  "threshold": 0.48,
  "model_name": "XGBoost",
  "model_version": "optimized-6114941abc"
}
```

### ⚠️ Important

- L'`engine_id` est l'identifiant unique de votre moteur physique
- L'`history` doit contenir **tous les cycles depuis le début** du moteur (ou sa dernière maintenance)
- Les cycles doivent être strictement croissants et uniques
- Seul le **dernier cycle** est prédit, les précédents servent aux features temporelles

### Exemple avec curl

```bash
API_URL="https://predictmaint-api-xxx.run.app"
ID_TOKEN=$(gcloud auth print-identity-token --audiences="${API_URL}")

curl -X POST "${API_URL}/predict" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @prediction_request.json
```

### Exemple avec Python

```python
import requests
import subprocess

API_URL = "https://predictmaint-api-xxx.run.app"

# Obtenir le token d'authentification GCP
id_token = subprocess.check_output([
    "gcloud", "auth", "print-identity-token", f"--audiences={API_URL}"
]).decode().strip()

headers = {
    "Authorization": f"Bearer {id_token}",
    "Content-Type": "application/json"
}

payload = {
    "engine_id": 42,
    "history": [
        # ... vos données capteurs
    ]
}

response = requests.post(f"{API_URL}/predict", headers=headers, json=payload)
prediction = response.json()

print(f"Prédiction ID: {prediction['prediction_id']}")
print(f"Probabilité de panne: {prediction['failure_probability']:.2%}")
print(f"Risque: {prediction['risk']}")
```

### 📊 Ce qui se passe automatiquement

1. **Persistance locale** : `/tmp/predictions.jsonl` (pour monitoring)
2. **Persistance GCS** : `gs://{PREDICTION_BUCKET}/predictions/{prediction_id}.json`
3. **Métriques Prometheus** :
   - `predictmaint_predictions_total{risk="HIGH|LOW"}`
   - `predictmaint_prediction_latency_seconds`
4. **Export Cloud Monitoring** (toutes les 60s) :
   - `custom.googleapis.com/predictmaint/predictions_total`
   - `custom.googleapis.com/predictmaint/prediction_latency_seconds_mean`

---

## ✅ 2. Soumettre la vérité terrain (feedback)

**Environ 30 jours après une prédiction**, vous savez si le moteur est réellement tombé en panne ou non.

### Endpoint : `POST /feedback`

```json
{
  "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "actual_failure_within_30_cycles": 0,
  "actual_rul": 150
}
```

- `prediction_id` : ID reçu lors du `/predict`
- `actual_failure_within_30_cycles` : `1` si panne dans les 30 cycles, `0` sinon
- `actual_rul` : (optionnel) nombre de cycles réels avant panne

### Exemple avec curl

```bash
curl -X POST "${API_URL}/feedback" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "actual_failure_within_30_cycles": 0
  }'
```

### Exemple avec Python

```python
feedback_data = {
    "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "actual_failure_within_30_cycles": 0,  # Pas de panne
    "actual_rul": 150  # Optionnel
}

response = requests.post(f"{API_URL}/feedback", headers=headers, json=feedback_data)
print(response.json())
```

### 📊 Ce qui se passe automatiquement

1. **Persistance locale** : `/tmp/feedback.jsonl`
2. **Persistance GCS** : `gs://{PREDICTION_BUCKET}/feedback/{prediction_id}.json`
3. **Prêt pour retraining** : Les prédictions + feedback sont fusionnés lors du prochain retraining

---

## 📊 3. Monitoring automatique de la dérive (Drift)

L'API calcule **automatiquement toutes les 5 minutes** :

### Métriques de dérive

- **PSI (Population Stability Index)** par feature
  - Compare la distribution actuelle (prédictions récentes) vs distribution TRAIN
  - PSI > 0.1 → dérive modérée
  - PSI > 0.25 → dérive forte

- **Drift share** : pourcentage de features en dérive

### Métriques Prometheus exposées

```
GET /metrics
```

Retourne :
```
# Dérive globale
predictmaint_drift_share 0.12

# Dérive par feature
predictmaint_drift_psi{feature="sensor_2"} 0.08
predictmaint_drift_psi{feature="sensor_4"} 0.15
predictmaint_drift_psi{feature="rolling_std_sensor_2_5"} 0.32
```

### Visualisation dans Grafana

Grafana (déployé automatiquement) affiche :
- Graphiques PSI par feature dans le temps
- Alerte si drift_share > 20%
- Alerte si PSI > 0.25 pour plusieurs features

**URL Grafana** : Visible dans le GitHub Actions Summary après déploiement

---

## 🔄 4. Déclencher le retraining automatique

Il existe **2 méthodes** pour déclencher un retraining :

### Méthode A : Upload de données labellisées (manuel)

**Quand l'utiliser** : Vous avez un fichier CSV de nouvelles données terrain complètes.

#### Format du CSV attendu

```csv
engine_id,cycle,setting_1,setting_2,setting_3,sensor_1,sensor_2,...,sensor_21,actual_failure_within_30_cycles
1001,1,0.0015,0.0003,100.0,518.67,641.82,...,23.419,0
1001,2,-0.0005,-0.0002,100.0,518.67,641.81,...,23.420,0
1001,3,0.0010,0.0001,100.0,518.68,641.83,...,23.421,0
...
1002,1,0.0012,0.0004,100.0,518.70,641.85,...,23.425,1
```

**Colonnes obligatoires** :
- `engine_id` : identifiant moteur
- `cycle` : numéro de cycle
- `setting_1`, `setting_2`, `setting_3` : réglages opérationnels
- `sensor_1` à `sensor_21` : relevés capteurs
- `actual_failure_within_30_cycles` : `0` ou `1` (label)

#### Endpoint : `POST /retrain/upload`

```bash
curl -X POST "${API_URL}/retrain/upload" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -F "file=@nouvelles_donnees.csv"
```

#### Exemple avec Python

```python
with open("nouvelles_donnees.csv", "rb") as f:
    files = {"file": ("data.csv", f, "text/csv")}
    response = requests.post(
        f"{API_URL}/retrain/upload",
        headers={"Authorization": f"Bearer {id_token}"},
        files=files
    )
    print(response.json())
```

**Réponse** :
```json
{
  "status": "retrain_triggered",
  "rows_added": 245
}
```

#### Ce qui se passe ensuite

Le retraining se fait **en arrière-plan** (thread daemon) :

1. ✅ **Préparation** : `python -m src.data.prepare` (avec `INCLUDE_PRODUCTION_FEEDBACK=1`)
2. ✅ **Sélection features** : `python -m src.features.select_features`
3. ✅ **Entraînement** : `python -m src.models.train` (3+ modèles)
4. ✅ **Quality gate** : `python -m src.models.quality_gate` (vérifie recall, PR-AUC)
5. ✅ **Promotion** : `python -m src.models.register` (si meilleur que champion)
6. ✅ **Reload** : Rechargement automatique du modèle en mémoire

#### Suivre l'avancement

```bash
curl "${API_URL}/retrain/status" \
  -H "Authorization: Bearer ${ID_TOKEN}"
```

**Réponse pendant l'exécution** :
```json
{
  "state": "running",
  "started_at": "2026-09-04T16:00:00.123456Z",
  "finished_at": null,
  "rows_added": 245,
  "error": null,
  "model_version": null
}
```

**Réponse après succès** :
```json
{
  "state": "completed",
  "started_at": "2026-09-04T16:00:00.123456Z",
  "finished_at": "2026-09-04T16:08:32.987654Z",
  "rows_added": 245,
  "error": null,
  "model_version": "optimized-abc123def456"
}
```

---

### Méthode B : Cloud Run Job (automatique via GitHub Actions ou manuel)

**Quand l'utiliser** : Déploiement en production avec données sur GCS.

Le job Cloud Run `predictmaint-retrain` est déployé automatiquement par GitHub Actions.

#### Déclenchement manuel du job

```bash
gcloud run jobs execute predictmaint-retrain \
  --region europe-west1 \
  --wait
```

#### Ce qui se passe

1. Le job télécharge **tous les fichiers** de :
   - `gs://{PREDICTION_BUCKET}/predictions/*.json`
   - `gs://{PREDICTION_BUCKET}/feedback/*.json`

2. Fusionne prédictions + feedback pour créer le dataset de retraining

3. Exécute le pipeline complet :
   - Préparation données (avec feedback production)
   - Sélection features
   - Entraînement 3+ modèles (Logistic Regression, Random Forest, XGBoost)
   - Optimisation Optuna (10 trials par défaut)
   - Quality gate (MIN_RECALL, MIN_PR_AUC)
   - Promotion si meilleur que champion
   - Upload sur GCS : `gs://{MODEL_ARTIFACT_BUCKET}/models/{version}/`

4. Met à jour le pointeur global :
   - `gs://{MODEL_ARTIFACT_BUCKET}/models/champion.json`

5. Le prochain déploiement API récupèrera automatiquement ce champion

#### Déclenchement automatique

Le job est exécuté automatiquement par GitHub Actions :
- À chaque push sur `main` (workflow `deploy.yml`)
- Ou manuellement via **Actions → MLOps - Retrain and Deploy → Run workflow**

---

## 📈 5. Visualiser les performances en production

### Monitoring des performances réelles

Le module `src/monitoring/performance.py` croise prédictions et feedback pour calculer les métriques réelles.

#### Endpoint à créer (optionnel)

Vous pouvez ajouter un endpoint dans l'API :

```python
@app.get("/monitoring/performance")
def performance_report():
    from src.monitoring.performance import performance_report
    report = performance_report(PREDICTION_LOG_PATH, FEEDBACK_LOG_PATH)
    return report
```

**Réponse** :
```json
{
  "labelled_predictions": 1523,
  "status": "ok",
  "recall": 0.89,
  "precision": 0.76,
  "pr_auc": 0.82,
  "roc_auc": 0.91,
  "brier_score": 0.14,
  "threshold_policy": "per_prediction_versioned_threshold",
  "alerts": {
    "recall_below_guardrail": false,
    "pr_auc_below_guardrail": false
  },
  "per_model_version": {
    "optimized-abc123": {
      "labelled_predictions": 1000,
      "status": "ok",
      "recall": 0.91,
      ...
    },
    "optimized-def456": {
      "labelled_predictions": 523,
      "status": "ok",
      "recall": 0.87,
      ...
    }
  }
}
```

---

## 🎯 Résumé : Flux complet bout-en-bout

### Semaine 1-4 : Collecte initiale

```bash
# Chaque jour : nouvelles prédictions
for engine in moteurs_actifs:
    POST /predict avec historique complet
    → Stocké sur GCS + monitoring drift
```

### Semaine 5 : Feedback arrive (30 jours après)

```bash
# Pour chaque prédiction de la semaine 1
for prediction_id in predictions_semaine_1:
    POST /feedback avec actual_failure_within_30_cycles
    → Stocké sur GCS
```

### Semaine 5 : Retraining automatique

**Option 1 : Via GitHub Actions (recommandé)**
```bash
git commit -m "trigger retrain"
git push origin main
→ GitHub Actions exécute le job Cloud Run
→ Récupère feedback GCS
→ Retrain + Quality gate
→ Redéploie API avec nouveau champion
```

**Option 2 : Job manuel**
```bash
gcloud run jobs execute predictmaint-retrain --region europe-west1
```

**Option 3 : Upload CSV direct**
```bash
curl -X POST "${API_URL}/retrain/upload" -F "file=@data.csv"
→ Retrain en background
→ Nouveau modèle chargé automatiquement
```

### Monitoring continu

- **Grafana** : Drift PSI, métriques business
- **Cloud Monitoring** : Métriques custom GCP
- **Prometheus** : Métriques temps réel

---

## ⚙️ Configuration des seuils

### Variables d'environnement

```bash
# API
LOG_LEVEL=INFO
PREDICTION_BUCKET=mon-bucket-predictions
MODEL_PATH=storage/models/model.joblib
MODEL_METADATA_PATH=storage/models/model_metadata.json

# Monitoring
DRIFT_CHECK_INTERVAL_SECONDS=300  # 5 minutes
CLOUD_MONITORING_FLUSH_INTERVAL_SECONDS=60  # 1 minute

# Retraining
INCLUDE_PRODUCTION_FEEDBACK=1  # Activer feedback production
OPTUNA_TRIALS=10  # Nombre d'essais Optuna
```

### Seuils de qualité

Dans `src/config.py` :

```python
MIN_RECALL = 0.85  # Minimum 85% de rappel
MIN_PR_AUC = 0.75  # Minimum 75% PR-AUC
```

Si un modèle ne passe pas ces seuils, le retraining échoue et le champion actuel reste en place.

---

## 🚨 Alertes et notifications

### Alertes Grafana configurées

1. **Drift élevé** : `drift_share > 0.20` (20% des features dérivent)
2. **PSI critique** : `drift_psi{feature} > 0.25` pour plusieurs features
3. **Latence élevée** : `prediction_latency > 2s`
4. **Erreurs télémétrie** : `telemetry_errors_total > 10/min`

### Configurer les notifications

Dans Grafana → Alerting → Contact points :
- Email
- Slack
- PagerDuty
- Webhook custom

---

## 📚 Commandes utiles

### Vérifier l'état de l'API

```bash
curl "${API_URL}/ready"
```

### Voir les métriques Prometheus

```bash
curl "${API_URL}/metrics"
```

### Télécharger le champion actuel

```bash
gcloud storage cp "gs://${MODEL_ARTIFACT_BUCKET}/models/champion.json" .
cat champion.json
```

### Lister les prédictions stockées

```bash
gcloud storage ls "gs://${PREDICTION_BUCKET}/predictions/" | head -20
```

### Lister les feedbacks stockés

```bash
gcloud storage ls "gs://${PREDICTION_BUCKET}/feedback/" | head -20
```

### Voir les logs de l'API

```bash
gcloud run services logs read predictmaint-api \
  --region europe-west1 \
  --limit 50
```

### Déclencher un retraining manuel

```bash
gcloud run jobs execute predictmaint-retrain \
  --region europe-west1 \
  --wait
```

---

## 🎓 Bonnes pratiques

### 1. Stratégie de collecte de feedback

- Automatiser la collecte 30 jours après chaque prédiction
- Stocker les maintenances réelles dans une base de données
- Scripter l'envoi batch du feedback

### 2. Fréquence de retraining

- **Hebdomadaire** : Si flux de données modéré (< 1000 prédictions/semaine)
- **Mensuel** : Si flux faible mais feedback complet disponible
- **Dérive détectée** : Si drift_share > 30%, retrainer immédiatement

### 3. Validation avant déploiement

Le quality gate automatique vérifie :
- Recall ≥ 85%
- PR-AUC ≥ 75%
- Meilleur que champion actuel

Si échec → champion actuel reste en place (pas de régression)

### 4. Versioning des modèles

Chaque modèle est versionné avec :
- SHA Git court (ex: `optimized-6114941abc`)
- Métadonnées complètes stockées sur GCS
- Rollback possible vers versions précédentes

---

## 🔧 Troubleshooting

### Le retraining échoue

```bash
# Vérifier les logs du job
gcloud run jobs executions logs read \
  --job predictmaint-retrain \
  --region europe-west1
```

**Causes fréquentes** :
- Pas assez de feedback (< 20 exemples)
- Quality gate non passé (metrics < seuils)
- Déséquilibre classe (trop de 0 ou trop de 1)

### Drift très élevé mais performances OK

C'est normal si :
- Vos moteurs fonctionnent dans de nouvelles conditions opérationnelles
- Les performances réelles (feedback) restent bonnes

**Action** : Retrainer pour adapter le modèle aux nouvelles distributions

### Métriques non visibles dans Cloud Monitoring

Vérifier :
```bash
# L'API a-t-elle les permissions ?
gcloud projects get-iam-policy ${GCP_PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/monitoring.metricWriter"
```

---

**Prêt à démarrer !** 🚀

Suivez ce guide pour mettre en place le cycle complet de MLOps en production.
