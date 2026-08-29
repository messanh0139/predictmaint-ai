#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
REPOSITORY="${REPOSITORY:-predictmaint}"
JOB="${JOB:-predictmaint-retrain}"
TRAINER_SA="${TRAINER_SA:-predictmaint-trainer@$PROJECT_ID.iam.gserviceaccount.com}"
SCHEDULER_SA="${SCHEDULER_SA:-predictmaint-scheduler@$PROJECT_ID.iam.gserviceaccount.com}"
PREDICTION_BUCKET="${PREDICTION_BUCKET:-${PROJECT_ID}-predictmaint-telemetry}"
MODEL_ARTIFACT_BUCKET="${MODEL_ARTIFACT_BUCKET:-${PROJECT_ID}-predictmaint-models}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/predictmaint-trainer:$TAG"

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build -f Dockerfile.train -t "$IMAGE" .
docker push "$IMAGE"

gcloud run jobs deploy "$JOB" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$TRAINER_SA" \
  --set-env-vars "PREDICTION_BUCKET=$PREDICTION_BUCKET,MODEL_ARTIFACT_BUCKET=$MODEL_ARTIFACT_BUCKET,INCLUDE_PRODUCTION_FEEDBACK=1,MLFLOW_TRACKING_URI=sqlite:////tmp/mlflow.db" \
  --tasks 1 \
  --max-retries 1 \
  --task-timeout 3600

gcloud run jobs add-iam-policy-binding "$JOB" \
  --region "$REGION" \
  --member="serviceAccount:$SCHEDULER_SA" \
  --role="roles/run.invoker" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
SCHEDULE="${SCHEDULE:-0 3 * * 0}"

gcloud scheduler jobs describe "$JOB-weekly" --location "$REGION" >/dev/null 2>&1 && \
  gcloud scheduler jobs delete "$JOB-weekly" --location "$REGION" --quiet || true

gcloud scheduler jobs create http "$JOB-weekly" \
  --location "$REGION" \
  --schedule "$SCHEDULE" \
  --uri "$URI" \
  --http-method POST \
  --oauth-service-account-email "$SCHEDULER_SA" \
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"

echo "Retraining job deployed: $JOB"
echo "Schedule: $SCHEDULE"
