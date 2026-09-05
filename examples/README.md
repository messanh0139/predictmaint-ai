# Exemples de test de l'API

Ce dossier contient des exemples pour tester l'API de production.

## 1. Vérifier les URLs de déploiement

Après le déploiement GitHub Actions, utilisez ce script pour récupérer toutes les URLs :

```bash
./scripts/check_production_urls.sh
```

Ce script affiche :
- URL de l'API
- URL du Dashboard React
- URL de Grafana (avec login/password)
- Commandes pour tester l'API

## 2. Tester une prédiction

### Prérequis

```bash
# Récupérer l'URL de l'API
API_URL=$(gcloud run services describe predictmaint-api \
    --region europe-west1 \
    --format='value(status.url)')

# Obtenir un token d'authentification
ID_TOKEN=$(gcloud auth print-identity-token --audiences="${API_URL}")

echo "API_URL: ${API_URL}"
```

### Envoyer une prédiction de test

```bash
curl -X POST "${API_URL}/predict" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @examples/test_prediction.json
```

**Réponse attendue** :

```json
{
  "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-09-04T16:30:00.123456Z",
  "engine_id": 999,
  "last_cycle": 2,
  "failure_probability": 0.23,
  "risk": "LOW",
  "threshold": 0.48,
  "model_name": "XGBoost",
  "model_version": "optimized-04be8ad..."
}
```

Sauvegarde le `prediction_id` pour soumettre le feedback plus tard.

## 3. Soumettre un feedback

30 jours après la prédiction, vous soumettez la vérité terrain :

```bash
# Éditer le fichier examples/test_feedback.json
# Remplacer REMPLACER_PAR_PREDICTION_ID_RECU par le prediction_id reçu

curl -X POST "${API_URL}/feedback" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @examples/test_feedback.json
```

**Réponse attendue** :

```json
{
  "status": "recorded",
  "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-10-04T16:30:00.123456Z",
  "actual_failure_within_30_cycles": 0,
  "actual_rul": 150
}
```

## 4. Vérifier les métriques

### Prometheus (raw)

```bash
curl "${API_URL}/metrics"
```

Retourne les métriques au format Prometheus :
```
predictmaint_predictions_total{risk="LOW"} 1
predictmaint_drift_share 0.0
predictmaint_model_ready 1
...
```

### Dashboard React (interface graphique)

Ouvrir dans un navigateur :
```bash
echo "Dashboard: $(gcloud run services describe predictmaint-dashboard \
    --region europe-west1 \
    --format='value(status.url)')"
```

### Grafana (monitoring avancé)

```bash
# URL
GRAFANA_URL=$(gcloud run services describe predictmaint-grafana \
    --region europe-west1 \
    --format='value(status.url)')

echo "Grafana: ${GRAFANA_URL}"
echo "Login: admin"

# Récupérer le mot de passe
echo "Password: $(gcloud secrets versions access latest \
    --secret=predictmaint-grafana-admin)"
```

## 5. Déclencher un retraining

### Option A : Upload CSV

Créer un fichier CSV avec vos données (voir format dans `GUIDE_MONITORING_RETRAINING.md`) :

```bash
curl -X POST "${API_URL}/retrain/upload" \
  -H "Authorization: Bearer ${ID_TOKEN}" \
  -F "file=@mes_nouvelles_donnees.csv"
```

### Option B : Cloud Run Job

```bash
gcloud run jobs execute predictmaint-retrain \
  --region europe-west1 \
  --wait
```

### Vérifier le statut du retraining

```bash
curl -H "Authorization: Bearer ${ID_TOKEN}" \
  "${API_URL}/retrain/status" | python3 -m json.tool
```

## 6. Exemples Python

### Script complet de test

```python
import requests
import subprocess
import json

# Configuration
REGION = "europe-west1"
SERVICE = "predictmaint-api"

# Récupérer l'URL de l'API
api_url = subprocess.check_output([
    "gcloud", "run", "services", "describe", SERVICE,
    "--region", REGION,
    "--format=value(status.url)"
]).decode().strip()

# Obtenir un token d'auth
id_token = subprocess.check_output([
    "gcloud", "auth", "print-identity-token",
    f"--audiences={api_url}"
]).decode().strip()

headers = {
    "Authorization": f"Bearer {id_token}",
    "Content-Type": "application/json"
}

print(f"API URL: {api_url}")
print()

# Test de santé (public)
print("1. Test /live (public)...")
response = requests.get(f"{api_url}/live")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
print()

# Test de disponibilité (authentifié)
print("2. Test /ready (authentifié)...")
response = requests.get(f"{api_url}/ready", headers=headers)
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")
print()

# Prédiction de test
print("3. Envoi d'une prédiction de test...")
with open("examples/test_prediction.json") as f:
    prediction_payload = json.load(f)

response = requests.post(
    f"{api_url}/predict",
    headers=headers,
    json=prediction_payload
)

if response.status_code == 200:
    prediction = response.json()
    print(f"   Prédiction réussie")
    print(f"   Prediction ID: {prediction['prediction_id']}")
    print(f"   Engine ID: {prediction['engine_id']}")
    print(f"   Probabilité de panne: {prediction['failure_probability']:.2%}")
    print(f"   Risque: {prediction['risk']}")
    print(f"   Seuil: {prediction['threshold']}")
    print(f"   Modèle: {prediction['model_name']} ({prediction['model_version']})")

    # Sauvegarder l'ID pour feedback ultérieur
    prediction_id = prediction['prediction_id']
else:
    print(f"   Erreur: {response.status_code}")
    print(f"   {response.text}")
    prediction_id = None

print()

# Feedback (si prédiction réussie)
if prediction_id:
    print("4. Envoi du feedback...")
    feedback_payload = {
        "prediction_id": prediction_id,
        "actual_failure_within_30_cycles": 0,
        "actual_rul": 150
    }

    response = requests.post(
        f"{api_url}/feedback",
        headers=headers,
        json=feedback_payload
    )

    if response.status_code == 200:
        print(f"   Feedback enregistré")
        print(f"   {response.json()}")
    else:
        print(f"   Erreur: {response.status_code}")

print()
print("Tests terminés !")
```

Sauvegarder ce script dans `test_api.py` et lancer :

```bash
python3 test_api.py
```

## 7. Monitoring continu

### Script de monitoring quotidien

```python
import time
import requests
import subprocess
from datetime import datetime

# Configuration
API_URL = "..."  # Récupérer avec gcloud
ID_TOKEN = "..."  # Récupérer avec gcloud

headers = {"Authorization": f"Bearer {ID_TOKEN}"}

# Boucle de monitoring (toutes les 5 minutes)
while True:
    print(f"\n[{datetime.now()}] Vérification...")

    # Métriques Prometheus
    metrics = requests.get(f"{API_URL}/metrics", headers=headers).text

    # Extraire drift_share
    for line in metrics.split('\n'):
        if line.startswith('predictmaint_drift_share'):
            drift = float(line.split()[-1])
            print(f"  Drift global: {drift:.1%}")

            if drift > 0.30:
                print("  Le drift est élevé (> 30%)")
                print("  Il faut réentraîner le modèle")

    # Attendre 5 minutes
    time.sleep(300)
```

---

**Pour plus de détails, consultez** : `GUIDE_MONITORING_RETRAINING.md`
