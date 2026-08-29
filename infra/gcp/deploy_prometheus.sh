#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_SERVICE="${API_SERVICE:-predictmaint-api}"
SERVICE="${SERVICE:-predictmaint-prometheus}"
REPOSITORY="${REPOSITORY:-predictmaint}"
RUNTIME_SA="${RUNTIME_SA:-predictmaint-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$TAG"

API_URL="$(gcloud run services describe "$API_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
if [ -z "$API_URL" ]; then
  echo "API service '$API_SERVICE' introuvable dans la région '$REGION'. Déployer d'abord l'API avec infra/gcp/deploy.sh." >&2
  exit 1
fi
API_HOST="${API_URL#https://}"

# Prometheus tourne avec le compte runtime, déjà (ou à autoriser ici) invoker sur
# l'API privée : c'est ce qui lui permet de générer un jeton d'identité pour scraper
# /metrics via le serveur de métadonnées GCP (voir infra/gcp/prometheus-entrypoint.sh).
gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --region "$REGION" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/run.invoker" --quiet

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --pull -f Dockerfile.prometheus -t "$IMAGE" .
docker push "$IMAGE"

# Public sans authentification : ne contient que des métriques techniques (volume,
# latence, drift), pas de données client. Voir docs/06_deploiement_gcp.md.
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "API_HOST=$API_HOST" \
  --port 9090 \
  --cpu 1 --memory 512Mi --concurrency 20 --timeout 60 --min 0 --max 2 \
  --allow-unauthenticated

PROMETHEUS_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Prometheus public URL: $PROMETHEUS_URL"
