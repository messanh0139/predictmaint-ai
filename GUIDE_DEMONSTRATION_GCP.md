# Guide de Démonstration sur GCP

Ce guide explique comment accéder et utiliser tous les composants déployés sur Google Cloud Platform pour démontrer le système de monitoring MLOps et la détection de drift.

## 1. Récupérer les URLs Publiques

### Via GitHub Actions Summary

1. Allez sur : https://github.com/messanh0139/predictmaint-ai/actions
2. Cliquez sur le dernier workflow "MLOps - Retrain and Deploy"
3. Onglet **Summary**
4. Vous verrez :

```
### Production deployed
- Dashboard React: https://predictmaint-dashboard-xxx.run.app
- API: https://predictmaint-api-xxx.run.app
- Grafana: https://predictmaint-grafana-xxx.run.app (mot de passe admin dans Secret Manager)
- Cloud Monitoring: métriques custom sous custom.googleapis.com/predictmaint/*
- Model image tag: abc123def456
```

### Via gcloud CLI (Alternative)

```bash
# API
gcloud run services describe predictmaint-api \
  --region europe-west1 \
  --format='value(status.url)'

# Dashboard
gcloud run services describe predictmaint-dashboard \
  --region europe-west1 \
  --format='value(status.url)'

# Grafana
gcloud run services describe predictmaint-grafana \
  --region europe-west1 \
  --format='value(status.url)'
```

---

## 2. Accéder à Grafana (Monitoring Drift)

### Récupérer le Mot de Passe Grafana

```bash
gcloud secrets versions access latest --secret="predictmaint-grafana-admin"
```

Copiez le mot de passe affiché.

### Se Connecter à Grafana

1. Ouvrez l'URL Grafana : `https://predictmaint-grafana-xxx.run.app`
2. Login : **admin**
3. Password : (le mot de passe récupéré ci-dessus)

### Ce que Vous Verrez dans Grafana

**Dashboard Principal** :
- **Drift PSI par Feature** : Graphiques temps réel du drift pour chaque capteur
- **Drift Share Global** : Pourcentage de features en dérive
- **Métriques de Prédictions** : Nombre total, latence moyenne
- **Alertes** : Si PSI > 0.25 ou drift_share > 20%

---

## 3. Envoyer des Prédictions pour Générer du Drift

Pour voir le monitoring en action, vous devez générer du trafic de prédictions.

### Prédiction Simple (Sans Drift)

```bash
API_URL="https://predictmaint-api-xxx.run.app"

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

### Prédiction Avec Drift Volontaire

Pour **provoquer un drift** et le voir dans Grafana, modifiez les valeurs des capteurs :

```bash
curl -X POST "${API_URL}/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 1001,
    "history": [
      {
        "cycle": 1,
        "setting_1": 0.0015,
        "setting_2": 0.0003,
        "setting_3": 100.0,
        "sensor_1": 550.0,
        "sensor_2": 700.0,
        "sensor_3": 1700.0,
        "sensor_4": 1500.0,
        "sensor_5": 16.0,
        "sensor_6": 23.0,
        "sensor_7": 600.0,
        "sensor_8": 2500.0,
        "sensor_9": 9500.0,
        "sensor_10": 1.5,
        "sensor_11": 50.0,
        "sensor_12": 550.0,
        "sensor_13": 2500.0,
        "sensor_14": 8500.0,
        "sensor_15": 9.0,
        "sensor_16": 0.05,
        "sensor_17": 400,
        "sensor_18": 2400,
        "sensor_19": 110.0,
        "sensor_20": 42.0,
        "sensor_21": 25.0
      }
    ]
  }'
```

**Répétez cette commande 20-30 fois** pour accumuler assez de données et voir le drift dans Grafana.

### Script Python pour Générer du Trafic

Créez `test_drift_production.py` :

```python
import requests
import random
import time

API_URL = "https://predictmaint-api-xxx.run.app"  # Remplacez par votre URL

# Valeurs normales (référence)
NORMAL_VALUES = {
    "sensor_1": 518.67,
    "sensor_2": 641.82,
    "sensor_3": 1589.7,
    "sensor_4": 1400.6,
    # ... (valeurs moyennes)
}

def generate_prediction_with_drift(drift_factor=0.2):
    """Génère une prédiction avec drift volontaire"""
    history = []

    for cycle in range(1, 6):  # 5 cycles
        data = {
            "cycle": cycle,
            "setting_1": 0.0015 + random.uniform(-0.001, 0.001),
            "setting_2": 0.0003 + random.uniform(-0.0001, 0.0001),
            "setting_3": 100.0,
        }

        # Ajouter les capteurs avec drift
        for i in range(1, 22):
            sensor_key = f"sensor_{i}"
            base_value = NORMAL_VALUES.get(sensor_key, 500)
            # Ajouter du drift proportionnel
            drift_value = base_value * (1 + drift_factor * random.uniform(-1, 1))
            data[sensor_key] = drift_value

        history.append(data)

    return {
        "engine_id": random.randint(1000, 9999),
        "history": history
    }

# Envoyer 50 prédictions avec drift progressif
for i in range(50):
    drift_factor = i * 0.01  # Drift progressif de 0% à 50%

    payload = generate_prediction_with_drift(drift_factor)

    try:
        response = requests.post(
            f"{API_URL}/predict",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"[{i+1}/50] ✓ Prediction {result['prediction_id'][:8]}... | "
                  f"Risk: {result['risk']} | Drift factor: {drift_factor:.0%}")
        else:
            print(f"[{i+1}/50] ✗ Error {response.status_code}")

    except Exception as e:
        print(f"[{i+1}/50] ✗ Exception: {e}")

    time.sleep(1)  # 1 seconde entre chaque requête

print("\nTerminé. Attendez 5 minutes puis vérifiez Grafana.")
```

Exécutez :
```bash
python test_drift_production.py
```

---

## 4. Observer le Drift dans Grafana

### Après avoir généré du trafic (étape 3)

1. Retournez sur Grafana : `https://predictmaint-grafana-xxx.run.app`
2. Dashboard principal

### Métriques à Surveiller

**Drift PSI par Feature** :
- Graphiques pour chaque sensor (sensor_1, sensor_2, etc.)
- Si PSI > 0.1 : drift modéré (jaune)
- Si PSI > 0.25 : drift fort (rouge)

**Drift Share** :
- Pourcentage de features en dérive
- Si > 20% : alerte de retraining nécessaire

**Timeline des Prédictions** :
- Nombre de prédictions par minute
- Latence moyenne
- Répartition HIGH vs LOW risk

### Alertes Grafana

Les alertes se déclenchent automatiquement si :
- `drift_share > 0.20` (20% des features dérivent)
- `drift_psi{feature="sensor_X"} > 0.25` pour plusieurs features
- `prediction_latency > 2s`

---

## 5. Cloud Monitoring (Google Cloud Console)

### Accéder à Cloud Monitoring

1. Allez sur : https://console.cloud.google.com/monitoring
2. Sélectionnez votre projet : `predictmaint-prod`

### Métriques Custom

Dans **Metrics Explorer**, cherchez :

```
custom.googleapis.com/predictmaint/predictions_total
custom.googleapis.com/predictmaint/prediction_latency_seconds_mean
custom.googleapis.com/predictmaint/drift_share
custom.googleapis.com/predictmaint/drift_psi
```

### Créer un Dashboard Cloud Monitoring

1. Aller dans **Monitoring** puis **Dashboards** puis **Create Dashboard**
2. Ajouter des graphiques :
   - **Prédictions Totales** : `custom.googleapis.com/predictmaint/predictions_total`
   - **Drift Global** : `custom.googleapis.com/predictmaint/drift_share`
   - **Latence API** : `custom.googleapis.com/predictmaint/prediction_latency_seconds_mean`

---

## 6. Logs Cloud Run (Débogage)

### Voir les Logs de l'API

```bash
gcloud run services logs read predictmaint-api \
  --region europe-west1 \
  --limit 100
```

**Ou via Console** :
1. https://console.cloud.google.com/run
2. Cliquez sur `predictmaint-api`
3. Onglet **Logs**

### Filtrer les Logs

Pour voir uniquement les calculs de drift :
```
resource.type="cloud_run_revision"
resource.labels.service_name="predictmaint-api"
jsonPayload.message=~"Drift"
```

Pour voir les prédictions :
```
resource.type="cloud_run_revision"
resource.labels.service_name="predictmaint-api"
jsonPayload.message=~"prediction_id"
```

---

## 7. Tester le Workflow Complet pour la Démo

### Scénario de Démonstration Complète

#### 1. Montrer le Dashboard React
```
https://predictmaint-dashboard-xxx.run.app
```
- Onglet "Performance" : Métriques du modèle champion
- Onglet "Démonstration prédictive" : Faire une prédiction en direct

#### 2. Générer des Prédictions
```bash
# Via le dashboard ou via API directement
curl -X POST "https://predictmaint-api-xxx.run.app/predict" -H "Content-Type: application/json" -d @prediction.json
```

#### 3. Attendre 5 Minutes (Drift calculé automatiquement)
L'API calcule le drift **toutes les 5 minutes** en arrière-plan.

#### 4. Montrer Grafana
```
https://predictmaint-grafana-xxx.run.app
```
- Dashboard avec drift PSI par feature
- Drift share global
- Alertes si drift > seuil

#### 5. Montrer Cloud Monitoring
```
https://console.cloud.google.com/monitoring
```
- Métriques custom exportées
- Graphiques temps réel

#### 6. Déclencher un Retraining (Optionnel)
```bash
# Via GitHub Actions
gh workflow run deploy.yml

# Ou via Cloud Run Job
gcloud run jobs execute predictmaint-retrain --region europe-west1 --wait
```

#### 7. Voir le Nouveau Modèle Déployé
- Dans GitHub Actions Summary, vérifier le nouveau model_version
- Dans le Dashboard, vérifier que le modèle champion est mis à jour

---

## 8. Récupérer les Données Stockées sur GCS

### Prédictions Stockées
```bash
gsutil ls gs://PREDICTION_BUCKET/predictions/ | head -20
```

### Feedback Stockés
```bash
gsutil ls gs://PREDICTION_BUCKET/feedback/ | head -20
```

### Télécharger une Prédiction
```bash
gsutil cp gs://PREDICTION_BUCKET/predictions/abc123-def456.json .
cat abc123-def456.json | jq
```

---

## 9. Monitoring des Coûts

### Voir les Coûts Actuels

1. https://console.cloud.google.com/billing
2. **Reports**
3. Filtrer par service :
   - Cloud Run : API, Dashboard, Grafana
   - Cloud Storage : Buckets prédictions/modèles
   - Cloud Run Jobs : Retraining

### Coûts Estimés (Usage Modéré)

| Service | Coût Mensuel |
|---------|--------------|
| Cloud Run API (0-5 instances) | 5-10€ |
| Cloud Run Dashboard | 3-5€ |
| Cloud Run Grafana | 3-5€ |
| Cloud Storage (2 buckets) | 1-2€ |
| Artifact Registry | 1€ |
| Cloud Run Jobs (retraining hebdo) | 2-4€ |
| **Total** | **15-27€/mois** |

**Optimisation** : Avec `--min 0`, les services se mettent en veille quand non utilisés (0€ au repos).

---

## 10. Checklist pour la Soutenance

### Avant la Soutenance

- [ ] Vérifier que tous les services sont déployés (vert sur GitHub Actions)
- [ ] Récupérer toutes les URLs publiques
- [ ] Tester le dashboard en navigation privée
- [ ] Récupérer le mot de passe Grafana
- [ ] Générer du trafic de prédictions (50+ prédictions)
- [ ] Attendre 10 minutes pour que le drift soit calculé
- [ ] Vérifier que Grafana affiche des graphiques de drift

### Pendant la Soutenance

**Slide 1 : Architecture Production**
- Montrer le schéma GitHub Actions vers Cloud Run

**Slide 2 : URLs Publiques** (cliquables)
```
Dashboard : https://predictmaint-dashboard-xxx.run.app
API Docs  : https://predictmaint-api-xxx.run.app/docs
Grafana   : https://predictmaint-grafana-xxx.run.app
```

**Slide 3 : Démonstration Live**
1. Ouvrir Dashboard et faire une prédiction
2. Ouvrir Grafana et montrer drift PSI
3. Ouvrir Cloud Monitoring et montrer métriques custom

**Slide 4 : GitHub Actions**
- Montrer l'historique des déploiements
- Expliquer le workflow automatique

---

## Commandes Récapitulatives

```bash
# Récupérer les URLs
gcloud run services list --region=europe-west1

# Mot de passe Grafana
gcloud secrets versions access latest --secret="predictmaint-grafana-admin"

# Logs API en temps réel
gcloud run services logs tail predictmaint-api --region=europe-west1

# Déclencher retraining
gcloud run jobs execute predictmaint-retrain --region=europe-west1

# Voir les métriques Prometheus (depuis l'API)
curl https://predictmaint-api-xxx.run.app/metrics

# Lister les modèles sur GCS
gsutil ls gs://MODEL_ARTIFACT_BUCKET/models/

# Voir le champion actuel
gsutil cat gs://MODEL_ARTIFACT_BUCKET/models/champion.json | jq
```

---

## Troubleshooting

### Grafana ne charge pas
```bash
# Vérifier que le service est UP
gcloud run services describe predictmaint-grafana --region=europe-west1

# Voir les logs d'erreur
gcloud run services logs read predictmaint-grafana --region=europe-west1 --limit=50
```

### Pas de drift visible
- Assurez-vous d'avoir envoyé 20+ prédictions
- Attendez 5-10 minutes (calcul en background)
- Vérifiez les logs : `gcloud run services logs tail predictmaint-api`

### API timeout
- Le premier appel peut être lent (cold start)
- Refreshez et réessayez

---

**Prêt pour la démonstration !** 🎉

Tous vos composants MLOps sont maintenant accessibles publiquement et le jury pourra tester en direct pendant votre soutenance.
