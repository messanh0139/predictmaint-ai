#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
REPOSITORY="${REPOSITORY:-predictmaint}"
TELEMETRY_BUCKET="${PREDICTION_BUCKET:-${PROJECT_ID}-predictmaint-telemetry}"
MODEL_BUCKET="${MODEL_ARTIFACT_BUCKET:-${PROJECT_ID}-predictmaint-models}"
RUNTIME_SA="predictmaint-runtime"
DEPLOYER_SA="predictmaint-deployer"
TRAINER_SA="predictmaint-trainer"
SCHEDULER_SA="predictmaint-scheduler"
RUNTIME_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"
DEPLOYER_EMAIL="$DEPLOYER_SA@$PROJECT_ID.iam.gserviceaccount.com"
TRAINER_EMAIL="$TRAINER_SA@$PROJECT_ID.iam.gserviceaccount.com"
SCHEDULER_EMAIL="$SCHEDULER_SA@$PROJECT_ID.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com

gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location="$REGION"

for sa in "$RUNTIME_SA" "$DEPLOYER_SA" "$TRAINER_SA" "$SCHEDULER_SA"; do
  gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 || \
    gcloud iam service-accounts create "$sa" --display-name="PredictMaint $sa"
done

for bucket in "$TELEMETRY_BUCKET" "$MODEL_BUCKET"; do
  gcloud storage buckets describe "gs://$bucket" >/dev/null 2>&1 || \
    gcloud storage buckets create "gs://$bucket" --location="$REGION" --uniform-bucket-level-access
done

# Runtime API : écriture de télémétrie uniquement.
gcloud storage buckets add-iam-policy-binding "gs://$TELEMETRY_BUCKET" \
  --member="serviceAccount:$RUNTIME_EMAIL" \
  --role="roles/storage.objectCreator" >/dev/null

# Runtime : l'API pousse ses métriques custom (drift, prédictions, état du modèle) vers
# Cloud Monitoring, et Grafana (même compte) les lit — voir api/cloud_monitoring.py.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_EMAIL" \
  --role="roles/monitoring.metricWriter" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_EMAIL" \
  --role="roles/monitoring.viewer" >/dev/null

# Trainer : lecture télémétrie labellisée et écriture des artefacts modèles versionnés.
gcloud storage buckets add-iam-policy-binding "gs://$TELEMETRY_BUCKET" \
  --member="serviceAccount:$TRAINER_EMAIL" \
  --role="roles/storage.objectViewer" >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$MODEL_BUCKET" \
  --member="serviceAccount:$TRAINER_EMAIL" \
  --role="roles/storage.objectAdmin" >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$MODEL_BUCKET" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/storage.objectAdmin" >/dev/null

# Déployeur : Cloud Run + Artifact Registry, puis impersonation ciblée du runtime.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/run.admin" >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
  --location="$REGION" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/artifactregistry.writer" >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/iam.serviceAccountUser" >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$TRAINER_EMAIL" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/iam.serviceAccountUser" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/run.invoker" >/dev/null
# Requis pour créer/gérer le secret du mot de passe admin Grafana lors du déploiement
# CI/CD (voir .github/workflows/deploy.yml, étape "Deploy Grafana").
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$DEPLOYER_EMAIL" \
  --role="roles/secretmanager.admin" >/dev/null

# Le Scheduler sera autorisé à invoquer le job après création du job.

echo "GCP bootstrap complete"
echo "Runtime SA:  $RUNTIME_EMAIL"
echo "Deployer SA: $DEPLOYER_EMAIL"
echo "Trainer SA:  $TRAINER_EMAIL"
echo "Scheduler SA:$SCHEDULER_EMAIL"
echo "Telemetry:   gs://$TELEMETRY_BUCKET"
echo "Models:      gs://$MODEL_BUCKET"
echo "Next: configure GitHub WIF with infra/gcp/setup_github_wif.sh"
