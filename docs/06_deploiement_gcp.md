# Déploiement Google Cloud Platform

## Architecture cible

```text
GitHub
  |
  | Workload Identity Federation
  v
Deployer Service Account
  |
  +--> Artifact Registry
  |
  +--> Cloud Run deploy
          |
          v
   Runtime Service Account
          |
          +--> Cloud Storage telemetry
          +--> Cloud Logging / Monitoring

Cloud Scheduler --> Cloud Run Job (drift / retraining)
```

## Principes de sécurité

- aucun fichier de clé de compte de service dans GitHub ;
- Workload Identity Federation pour des jetons courts ;
- compte de service de déploiement séparé du compte runtime ;
- Cloud Run privé par défaut (`--no-allow-unauthenticated`) ;
- secrets futurs dans Secret Manager ;
- permissions runtime limitées au strict nécessaire.

## Réentraînement automatique déclenché depuis l'API (`/retrain/upload`)

Deux contraintes Cloud Run à connaître, déjà prises en compte dans `Dockerfile` et `infra/gcp/deploy.sh` :

- **Le CPU n'est alloué que pendant le traitement d'une requête, par défaut.** Le réentraînement s'exécute dans un thread en arrière-plan après que la requête `POST /retrain/upload` a déjà répondu : sans `--no-cpu-throttling`, ce thread reste quasiment gelé entre deux requêtes entrantes. Le service API est donc déployé avec `--no-cpu-throttling` (CPU alloué en continu).
- **L'image API embarque `data/raw/`** (comme `Dockerfile.train`), car `src.data.prepare` en a besoin pour reconstruire TRAIN/CALIBRATION/VALIDATION à chaque réentraînement, et Cloud Run n'a pas d'équivalent au volume `./data` de docker-compose.
- **Le modèle réentraîné n'est pas persisté au-delà de l'instance courante** : `MODEL_ARTIFACT_BUCKET` n'est pas configuré sur le service API (le compte runtime n'a volontairement pas les droits d'écriture sur ce bucket, réservés à `trainer`/`deployer`). Un réentraînement déclenché en production met à jour l'instance en cours, mais une nouvelle instance ou un redéploiement reviendra au champion de l'image. Pour une mise à jour durable du champion en production, utiliser le job planifié (`infra/gcp/create_retrain_job.sh`), qui tourne avec le compte `trainer` et publie dans le bucket modèle.

## Bootstrap

Dans Google Cloud Shell :

```bash
export PROJECT_ID="votre-projet"
export REGION="europe-west1"
./infra/gcp/bootstrap.sh
```

Le script active les APIs nécessaires, crée Artifact Registry, les deux service accounts et le bucket de télémétrie.

## Déploiement manuel

Avant le build, générer un artefact modèle validé :

```bash
python -m src.data.prepare
python -m src.features.select_features
python -m src.models.train
python -m src.models.quality_gate
```

Puis, déployer l'API (privée) :

```bash
export PROJECT_ID="votre-projet"
./infra/gcp/deploy.sh
```

Puis, déployer le dashboard (public, pour la démonstration) — nécessite que l'API ait déjà été déployée à l'étape précédente :

```bash
export PROJECT_ID="votre-projet"
./infra/gcp/deploy_dashboard.sh
```

Le script résout automatiquement l'URL de l'API déployée, autorise le compte de service runtime à l'invoquer, puis déploie le dashboard avec `--allow-unauthenticated` et affiche son URL publique.

## GitHub Actions

Secrets :

- `GCP_PROJECT_ID` ;
- `GCP_WORKLOAD_IDENTITY_PROVIDER` ;
- `GCP_DEPLOYER_SERVICE_ACCOUNT` ;
- `GCP_RUNTIME_SERVICE_ACCOUNT`.
- `GCP_TRAINER_SERVICE_ACCOUNT`.

Variables :

- `GCP_REGION` ;
- `PREDICTION_BUCKET` ;
- `MODEL_ARTIFACT_BUCKET`.
- `MLOPS_OPTUNA_TRIALS` (par exemple `3` pour une démonstration, `10` par défaut) ;
- `MLFLOW_TRACKING_URI` (optionnelle, mais nécessaire pour un tracking MLflow persistant).

Le workflow déclenché par chaque push sur `main` construit le trainer, exécute le Cloud Run
Job avec les nouvelles données labellisées du bucket de télémétrie, applique le quality gate,
puis déploie des images API et Streamlit immuables taguées par SHA. Le dashboard est public
pour la présentation ; l'API reste privée et reçoit un jeton d'identité du dashboard.

Configuration minimale recommandée dans GitHub :

```text
Secrets
  GCP_PROJECT_ID
  GCP_WORKLOAD_IDENTITY_PROVIDER
  GCP_DEPLOYER_SERVICE_ACCOUNT
  GCP_RUNTIME_SERVICE_ACCOUNT
  GCP_TRAINER_SERVICE_ACCOUNT

Variables
  GCP_REGION=europe-west1
  PREDICTION_BUCKET=<projet>-predictmaint-telemetry
  MODEL_ARTIFACT_BUCKET=<projet>-predictmaint-models
  MLOPS_OPTUNA_TRIALS=3
  MLFLOW_TRACKING_URI=https://<serveur-mlflow-distant>   # optionnel
```

## Test externe et CI/CD

Le holdout externe n'est **pas** utilisé comme quality gate de déploiement. Le workflow manuel `certification-evaluate.yml` est séparé afin d'éviter de tuner indirectement sur le test.

## Monitoring et jobs

Cloud Run fournit métriques et logs natifs. Pour les tâches planifiées de drift/réentraînement, créer un Cloud Run Job et le déclencher avec Cloud Scheduler. La promotion du modèle reste soumise au quality gate et au mécanisme champion/challenger.

## Configuration GitHub WIF

Après le bootstrap :

```bash
export PROJECT_ID="votre-projet"
export GITHUB_REPOSITORY="organisation/repository"
./infra/gcp/setup_github_wif.sh
```

Le script affiche la valeur à enregistrer dans `GCP_WORKLOAD_IDENTITY_PROVIDER`. Il limite le provider au repository GitHub déclaré.

## Appeler un service Cloud Run privé

Pour une démonstration manuelle avec votre identité autorisée :

```bash
SERVICE_URL="$(gcloud run services describe predictmaint-api --region "$REGION" --format='value(status.url)')"
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$SERVICE_URL/ready"
```

Pour un front ou un autre service, utiliser une identité de service autorisée à invoquer Cloud Run plutôt que d'ouvrir l'API publiquement.

## Secrets futurs

Le projet actuel n'a pas besoin de mot de passe métier. Si une future intégration en introduit, utiliser Secret Manager et donner à l'identité runtime uniquement l'accès aux secrets requis. Ne jamais stocker de secret dans `.env` commité, GitHub Actions ou l'image Docker.


## Job de réentraînement planifié

Après le bootstrap, il est possible de créer un job Cloud Run de retraining et une planification hebdomadaire :

```bash
export PROJECT_ID="votre-projet"
./infra/gcp/create_retrain_job.sh
```

Le job :

1. lit les objets `predictions/` et `feedback/` du bucket télémétrie ;
2. reconstruit des observations de production labellisées ;
3. les ajoute uniquement au TRAIN ;
4. réentraîne et optimise ;
5. applique champion/challenger et quality gate ;
6. enregistre la nouvelle version et la persiste dans le bucket modèle.

La VALIDATION et le holdout externe restent inchangés.
