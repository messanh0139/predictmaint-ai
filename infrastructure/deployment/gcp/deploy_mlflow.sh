#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-predictmaint-mlflow}"
REPOSITORY="${REPOSITORY:-predictmaint}"
RUNTIME_SA="${RUNTIME_SA:-predictmaint-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$TAG"

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --pull -f Dockerfile.mlflow -t "$IMAGE" .
docker push "$IMAGE"

# Public en lecture pour la démonstration : MLflow n'a pas d'authentification native
# et son backend est un sqlite local au conteneur (perdu à chaque redéploiement/nouvelle
# instance). Ne pas y stocker de runs de production réels. Voir docs/06_deploiement_gcp.md.
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --port 5000 \
  --cpu 1 --memory 1Gi --concurrency 20 --timeout 120 --min 0 --max 2 \
  --allow-unauthenticated

MLFLOW_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "MLflow public URL: $MLFLOW_URL"
echo "Set GitHub variable MLFLOW_TRACKING_URI=$MLFLOW_URL and dashboard env var MLFLOW_URL=$MLFLOW_URL"
