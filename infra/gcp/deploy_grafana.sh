#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-europe-west1}"
PROMETHEUS_SERVICE="${PROMETHEUS_SERVICE:-predictmaint-prometheus}"
SERVICE="${SERVICE:-predictmaint-grafana}"
REPOSITORY="${REPOSITORY:-predictmaint}"
RUNTIME_SA="${RUNTIME_SA:-predictmaint-runtime@$PROJECT_ID.iam.gserviceaccount.com}"
SECRET_NAME="${SECRET_NAME:-predictmaint-grafana-admin}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$TAG"

PROMETHEUS_URL="$(gcloud run services describe "$PROMETHEUS_SERVICE" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
if [ -z "$PROMETHEUS_URL" ]; then
  echo "Service Prometheus '$PROMETHEUS_SERVICE' introuvable dans la région '$REGION'. Déployer d'abord avec infra/gcp/deploy_prometheus.sh." >&2
  exit 1
fi

# Mot de passe admin généré une seule fois (versions suivantes du secret ignorées si
# déjà présent), stocké dans Secret Manager plutôt qu'en variable d'environnement en clair.
if gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Secret '$SECRET_NAME' déjà existant, mot de passe conservé."
else
  ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
  printf '%s' "$ADMIN_PASSWORD" | gcloud secrets create "$SECRET_NAME" --project "$PROJECT_ID" --replication-policy=automatic --data-file=-
fi

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/secretmanager.secretAccessor" --quiet

gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker build --pull -f Dockerfile.grafana -t "$IMAGE" .
docker push "$IMAGE"

# Public, mais protégé par le mot de passe admin ci-dessus (contrairement à MLflow et
# Prometheus, sans authentification native). Voir docs/06_deploiement_gcp.md.
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "PROMETHEUS_URL=$PROMETHEUS_URL,GF_SECURITY_ADMIN_USER=admin" \
  --set-secrets "GF_SECURITY_ADMIN_PASSWORD=$SECRET_NAME:latest" \
  --port 3000 \
  --cpu 1 --memory 512Mi --concurrency 20 --timeout 60 --min 0 --max 2 \
  --allow-unauthenticated

GRAFANA_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "Grafana public URL: $GRAFANA_URL"
echo "Utilisateur : admin"
echo "Mot de passe : $(gcloud secrets versions access latest --secret="$SECRET_NAME" --project "$PROJECT_ID")"
