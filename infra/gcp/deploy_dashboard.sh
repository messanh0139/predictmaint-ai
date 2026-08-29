#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_SERVICE="${API_SERVICE:-predictmaint-api}"
DASHBOARD_SERVICE="${DASHBOARD_SERVICE:-predictmaint-dashboard}"
MLFLOW_SERVICE="${MLFLOW_SERVICE:-predictmaint-mlflow}"
PROMETHEUS_SERVICE="${PROMETHEUS_SERVICE:-predictmaint-prometheus}"
GRAFANA_SERVICE="${GRAFANA_SERVICE:-predictmaint-grafana}"
REPOSITORY="${REPOSITORY:-predictmaint}"
RUNTIME_SA="${RUNTIME_SA:-predictmaint-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$DASHBOARD_SERVICE:$TAG"

API_URL="$(gcloud run services describe "$API_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
if [ -z "$API_URL" ]; then
  echo "API service '$API_SERVICE' introuvable dans la région '$REGION'. Déployer d'abord l'API avec infra/gcp/deploy.sh." >&2
  exit 1
fi

# Optionnel : si MLflow/Prometheus/Grafana sont déployés (infra/gcp/deploy_mlflow.sh,
# deploy_prometheus.sh, deploy_grafana.sh), les liens de la barre latérale du dashboard
# pointent vers leurs URLs publiques plutôt que localhost.
MLFLOW_URL="$(gcloud run services describe "$MLFLOW_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
PROMETHEUS_URL="$(gcloud run services describe "$PROMETHEUS_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
GRAFANA_URL="$(gcloud run services describe "$GRAFANA_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"

# Autorise le compte de service runtime (utilisé par le dashboard) à invoquer l'API privée.
gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --region "$REGION" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/run.invoker" --quiet

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --pull -f Dockerfile.dashboard -t "$IMAGE" .
docker push "$IMAGE"

ENV_VARS="API_URL=$API_URL,API_AUDIENCE=$API_URL"
if [ -n "$MLFLOW_URL" ]; then
  ENV_VARS="$ENV_VARS,MLFLOW_URL=$MLFLOW_URL"
fi
if [ -n "$PROMETHEUS_URL" ]; then
  ENV_VARS="$ENV_VARS,PROMETHEUS_URL=$PROMETHEUS_URL"
fi
if [ -n "$GRAFANA_URL" ]; then
  ENV_VARS="$ENV_VARS,GRAFANA_URL=$GRAFANA_URL"
fi

gcloud run deploy "$DASHBOARD_SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "$ENV_VARS" \
  --port 8501 \
  --cpu 1 --memory 1Gi --concurrency 20 --timeout 60 --min 0 --max 3 \
  --allow-unauthenticated

DASHBOARD_URL="$(gcloud run services describe "$DASHBOARD_SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Dashboard public URL: $DASHBOARD_URL"
