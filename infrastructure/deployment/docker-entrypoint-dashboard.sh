#!/bin/sh
set -e

# Port par défaut si Cloud Run ne l'injecte pas
PORT="${PORT:-8080}"

echo "=== PredictMaint Dashboard Startup ==="
echo "Port: ${PORT}"
echo "API URL: ${REACT_APP_API_URL:-not set}"
echo "MLflow URL: ${REACT_APP_MLFLOW_URL:-not set}"
echo "Grafana URL: ${REACT_APP_GRAFANA_URL:-not set}"

# Générer la configuration nginx avec le port dynamique
cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen ${PORT};
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Support de React Router - rediriger toutes les routes vers index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache pour les assets statiques
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Pas de cache pour index.html
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
EOF

# Créer le fichier de configuration runtime pour React
cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.RUNTIME_CONFIG = {
  REACT_APP_API_URL: "${REACT_APP_API_URL:-}",
  REACT_APP_MLFLOW_URL: "${REACT_APP_MLFLOW_URL:-}",
  REACT_APP_GRAFANA_URL: "${REACT_APP_GRAFANA_URL:-}",
  REACT_APP_PROMETHEUS_URL: "${REACT_APP_PROMETHEUS_URL:-}",
  REACT_APP_API_DOCS_URL: "${REACT_APP_API_DOCS_URL:-${REACT_APP_API_URL:-}/docs}",
  REACT_APP_DATA_PATH: "/data/raw/test_FD001.txt",
  REACT_APP_METADATA_PATH: "/models/model_metadata.json",
  REACT_APP_METRICS_PATH: "/models/test_metrics.json"
};
EOF
# sans ça, nginx (utilisateur non-root) ne peut pas lire le fichier
chmod 644 /usr/share/nginx/html/runtime-config.js

echo "=== Configuration nginx générée ==="
cat /etc/nginx/conf.d/default.conf

echo "=== Configuration runtime générée ==="
cat /usr/share/nginx/html/runtime-config.js

echo "=== Démarrage de nginx sur le port ${PORT} ==="
exec nginx -g "daemon off;"
