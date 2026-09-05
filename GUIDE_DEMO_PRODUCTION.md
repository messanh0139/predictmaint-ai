# Guide de démonstration — Production (GCP Cloud Run)

Ce guide vérifie et démontre le système réellement déployé en production sur
GCP, par opposition à `GUIDE_DEMO.md` qui décrit la stack locale
(docker-compose). Rien ici ne nécessite de lancer quoi que ce soit en local :
tout tourne déjà sur Cloud Run.

Le réentraînement se déclenche automatiquement de deux façons indépendantes,
sans aucune action manuelle nécessaire au quotidien :
- **À chaque push sur `main`** (`.github/workflows/deploy.yml`) : build, retrain,
  garde-fous qualité, déploiement des services.
- **Tous les jours à 3h du matin (heure de Paris)**, via une tâche **Cloud
  Scheduler** (`predictmaint-retrain-daily`) qui exécute directement le job
  Cloud Run `predictmaint-retrain` : le système reprend alors tout le
  feedback de production accumulé depuis la dernière fois et ne remplace le
  champion que s'il est réellement meilleur. Aucun `git push`, aucun script,
  aucune intervention humaine requise pour ce chemin — c'est la boucle
  fermée complète : les utilisateurs appellent `/predict` puis `/feedback`,
  et le système se réentraîne tout seul chaque nuit avec ces nouvelles
  données.

## URLs de production

| Service | URL |
|---|---|
| API | https://predictmaint-api-6iao6qpasa-ew.a.run.app |
| Dashboard | https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app |
| Grafana | https://predictmaint-grafana-6iao6qpasa-ew.a.run.app |
| MLflow | https://predictmaint-mlflow-6iao6qpasa-ew.a.run.app |

## 0. Prérequis (une fois)

```bash
gcloud config set project predictmaint-ai-4821
gcloud auth list   # vérifier que le bon compte est actif
```

## 1. Vérifier que tout est en ligne (30 secondes, à faire juste avant la démo)

```bash
curl -s https://predictmaint-api-6iao6qpasa-ew.a.run.app/ready
curl -s -o /dev/null -w "dashboard: %{http_code}\n" https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app/
curl -s -o /dev/null -w "grafana:   %{http_code}\n" https://predictmaint-grafana-6iao6qpasa-ew.a.run.app/
curl -s -o /dev/null -w "mlflow:    %{http_code}\n" https://predictmaint-mlflow-6iao6qpasa-ew.a.run.app/
```

Attendu : `/ready` renvoie `{"status":"ready","model":"xgboost_optimized",...}`,
les 3 autres `200` (ou `302` pour Grafana si pas encore connecté — normal).

Si un service renvoie une erreur au premier essai : c'est probablement un
cold start (`--min 0` sur tous les services). Relancer une fois.

## 2. Démo visuelle : le dashboard (le plus parlant pour un public non technique)

1. Ouvrir https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app/
2. Onglet **"Démonstration prédictive"** : sélectionner un moteur, ajuster le
   cycle avec le slider, cliquer "Analyser le risque" → la prédiction
   (probabilité, niveau LOW/HIGH, seuil, modèle utilisé) s'affiche en direct,
   servie par l'API de production.
3. Faire 2-3 prédictions sur des moteurs différents pour montrer la variation
   du risque.

## 3. Démo API brute (pour un public technique)

```bash
curl -s https://predictmaint-api-6iao6qpasa-ew.a.run.app/health
```

```bash
curl -s -X POST https://predictmaint-api-6iao6qpasa-ew.a.run.app/predict \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 1,
    "history": [
      {"cycle": 1, "setting_1": 0.0023, "setting_2": 0.0003, "setting_3": 100.0,
       "sensor_1": 518.67, "sensor_2": 641.82, "sensor_3": 1589.70, "sensor_4": 1400.60,
       "sensor_5": 14.62, "sensor_6": 21.61, "sensor_7": 554.36, "sensor_8": 2388.06,
       "sensor_9": 9046.19, "sensor_10": 1.30, "sensor_11": 47.47, "sensor_12": 521.66,
       "sensor_13": 2388.02, "sensor_14": 8138.62, "sensor_15": 8.4195, "sensor_16": 0.03,
       "sensor_17": 392, "sensor_18": 2388, "sensor_19": 100.0, "sensor_20": 39.06,
       "sensor_21": 23.4190}
    ]
  }'
```

Réponse attendue : un JSON avec `failure_probability`, `risk`, `threshold`,
`model_name`, `model_version`. Chaque appel est aussi journalisé (bucket
`predictmaint-ai-4821-predictmaint-telemetry`) et incrémente les métriques
Prometheus visibles ensuite dans Grafana.

## 4. Monitoring — Grafana

```bash
# Récupérer le mot de passe admin (à exécuter soi-même, ne pas le partager à l'écran)
gcloud secrets versions access latest --secret=predictmaint-grafana-admin
```

1. Ouvrir https://predictmaint-grafana-6iao6qpasa-ew.a.run.app/, login `admin`
   + mot de passe ci-dessus.
2. Dashboards préconfigurés à montrer :
   - **PredictMaint AI - API Monitoring** : prédictions/minute, latence, part
     de dérive (drift), erreurs de télémétrie.
   - **PredictMaint AI - Cloud Monitoring** : métriques Cloud Run natives.
3. Faire quelques prédictions (étape 2 ou 3) juste avant d'ouvrir Grafana pour
   que les graphes bougent en direct.

## 5. Tracking des expérimentations — MLflow

1. Ouvrir https://predictmaint-mlflow-6iao6qpasa-ew.a.run.app/
2. Expérience `predictmaint-fd001` : montrer les runs (un par modèle candidat
   + un run d'optimisation Optuna), leurs métriques (`pr_auc`, `recall`,
   `business_cost`) et les artefacts de modèle attachés.

## 5bis. Injecter de nouvelles données pour démontrer le réentraînement automatique

Pour démontrer que le pipeline s'adapte à de nouvelles données, la façon
fidèle à la vraie production est de passer par la vraie boucle de feedback
(pas par un raccourci) : `POST /predict` puis `POST /feedback` sur l'API
publique, exactement comme le ferait un client réel. Ces deux appels
persistent sur le bucket `predictmaint-ai-4821-predictmaint-telemetry`, sous
`predictions/<id>.json` et `feedback/<id>.json` — c'est exactement ce que lit
automatiquement `collect_feedback.py --bucket` au sein du job Cloud Run de
retrain (`INCLUDE_PRODUCTION_FEEDBACK=1` est déjà activé dans le pipeline
CI/CD, pas besoin de le configurer).

```bash
python scripts/generate_production_feedback.py \
  --api-url https://predictmaint-api-6iao6qpasa-ew.a.run.app \
  --num 20
```

Le script génère des trajectoires de moteurs synthétiques (certaines saines,
certaines en dégradation progressive selon `--failure-ratio`, 30% par
défaut), envoie chacune à `/predict`, puis renvoie la vérité terrain associée
à `/feedback`. Vérifié : les objets apparaissent bien sur GCS avec le schéma
attendu (`raw_history` dans `predictions/`, `actual_failure_within_30_cycles`
dans `feedback/`), et le modèle actuel détecte correctement les trajectoires
dégradées comme `HIGH`.

Une fois les données injectées, il n'y a **rien d'autre à faire** : le job
de retrain tournera automatiquement la nuit suivante (3h, heure de Paris,
section 6 option C) et les intègrera au jeu d'entraînement (moteurs
réindexés à partir de 1 000 000 pour ne jamais chevaucher les moteurs
originaux ni ceux de calibration/validation), sans promouvoir le nouveau
modèle sauf s'il est réellement meilleur. Pour une démo qui ne peut pas
attendre le lendemain, déclencher ce même chemin immédiatement (option C
ci-dessous, "déclencher maintenant").

## 6. Preuve que le pipeline MLOps est réellement automatique

C'est le point le plus fort à démontrer : tout le cycle — retrain,
comparaison au champion, garde-fous qualité, build des images, déploiement,
smoke tests — peut se déclencher de deux façons sans écrire de code ni
toucher au système : à chaque push sur `main`, ou automatiquement chaque
nuit via Cloud Scheduler.

### Option A — montrer l'historique (sans rien déclencher, 0 coût)

```bash
gh run list --workflow=deploy.yml --limit 5
gh run view <run_id>   # détail d'un run
```

Montrer le run le plus récent : toutes les étapes vertes, y compris
`Retrain from production feedback and enforce quality gate` (c'est le job
Cloud Run qui réentraîne réellement le modèle).

### Option B — le redéclencher en direct pendant la démo

```bash
gh workflow run deploy.yml
```

À savoir avant de le faire en live : le run complet prend **~18-20 minutes**
(retrain avec 10 essais Optuna + rebuild/déploiement des 3 services), et
consomme réellement des ressources GCP. Le pipeline ne peut pas dégrader la
prod : `promote.py` ne remplace le champion que s'il est strictement meilleur
sur validation, sinon l'ancien modèle reste actif. Utile si la démo dure
assez longtemps pour lancer ça en tâche de fond au début et revenir dessus à
la fin (comme dans `GUIDE_DEMO.md`, étape "pendant que ça tourne, montrer
Grafana/MLflow").

### Option C — montrer que c'est automatique tous les jours, sans y toucher

C'est la réponse au "je ne veux rien lancer moi-même, le système doit voir
les données et se réentraîner tout seul" : une tâche **Cloud Scheduler**
appelle directement l'API Cloud Run Jobs chaque nuit, indépendamment de tout
push de code.

```bash
# Montrer la configuration (preuve que c'est automatique, sans rien déclencher)
gcloud scheduler jobs describe predictmaint-retrain-daily --location europe-west1

# Déclencher immédiatement ce même chemin automatique, pour la démo
gcloud scheduler jobs run predictmaint-retrain-daily --location europe-west1

# Suivre l'exécution que ça vient de créer
gcloud run jobs executions list --job predictmaint-retrain --region europe-west1 --limit 3
```

## 7. Preuve de la non-fuite de données et du choix du champion (public technique/jury)

Le modèle actuellement en production :

```bash
gcloud storage cat gs://predictmaint-ai-4821-predictmaint-models/models/champion.json
gcloud storage cat gs://predictmaint-ai-4821-predictmaint-models/models/optimized-2979abf273c4/metadata.json
```

Points à montrer dans `metadata.json` :
- `"threshold_source": "dedicated calibration engines"` — le seuil de
  décision n'a jamais vu les moteurs de validation.
- `validation_metrics` : `recall: 1.0`, `pr_auc: 0.946` — mesurés sur des
  moteurs jamais utilisés à l'entraînement.
- `selected_features` : uniquement des variables causales (lags, moyennes
  glissantes), aucune colonne liée à la cible (`RUL`, `failure_within_...`).

Dans le code (`src/`), montrer si besoin :
- `src/data/split.py` : split par moteur avec exception si chevauchement.
- `src/models/promote.py` : le champion n'est remplacé que s'il est
  strictement meilleur, jamais par défaut.
- `src/models/evaluate.py` : le jeu de test externe (certification finale)
  n'est ouvert que par ce script, jamais par le pipeline de retrain
  automatique (`.github/workflows/certification-evaluate.yml`, séparé de
  `deploy.yml`).
- `infrastructure/tests/test_features.py` et `test_data.py` : tests
  automatisés qui vérifient ces garanties (exécutés à chaque push, visibles
  dans l'étape `Static, unit and anti-leakage checks` du run GitHub Actions).

## À éviter pendant une démo en production

- **Ne pas utiliser `/retrain/upload` (ou l'onglet "Réentraînement
  automatique" du dashboard) sur l'API de production** pour déclencher un
  réentraînement "en direct" à partir d'un CSV uploadé. Vérifié dans le
  code : ce chemin (pensé pour la démo locale docker-compose) tourne dans le
  conteneur API de prod (1 vCPU / 1 Gi), *sans* `MODEL_ARTIFACT_BUCKET`
  configuré — donc il ne peut pas écraser le vrai champion sur GCS — mais le
  résultat reste local à cette seule instance et n'est jamais publié. Pire :
  le service tourne avec `--min 0`, donc Cloud Run peut arrêter l'instance en
  cours de réentraînement (aucune requête entrante ne le retient), ce qui
  peut planter la démo en plein milieu sans erreur claire. Pour injecter de
  nouvelles données et montrer le réentraînement automatique, utiliser la
  section 5bis (boucle `/predict` + `/feedback`) puis l'option B de la
  section 6 (le vrai pipeline CI/CD, protégé par les garde-fous de
  `promote.py`).
- Ne pas afficher à l'écran la sortie de la commande `gcloud secrets versions
  access` (mot de passe Grafana) — la lire soi-même avant la démo.

## Arrêter / nettoyer après la démo

Rien à arrêter : ce sont des services Cloud Run avec `--min 0`, ils
redescendent à zéro instance automatiquement en l'absence de trafic. Aucune
action de nettoyage n'est nécessaire.
