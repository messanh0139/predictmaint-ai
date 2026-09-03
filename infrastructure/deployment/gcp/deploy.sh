#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-predictmaint-api}"
REPOSITORY="${REPOSITORY:-predictmaint}"
RUNTIME_SA="${RUNTIME_SA:-predictmaint-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
PREDICTION_BUCKET="${PREDICTION_BUCKET:-${PROJECT_ID}-predictmaint-telemetry}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$TAG"

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --pull -t "$IMAGE" .
docker push "$IMAGE"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "PREDICTION_BUCKET=$PREDICTION_BUCKET,LOG_LEVEL=INFO" \
  --cpu 1 --memory 1Gi --concurrency 10 --timeout 60 --min 0 --max 5 \
  --no-cpu-throttling \
  --no-allow-unauthenticated
