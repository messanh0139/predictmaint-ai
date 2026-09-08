#!/usr/bin/env bash
set -euo pipefail

if [ -n "${GCP_PROJECT_ID:-}" ]; then
  sed "s#__PROJECT_ID__#${GCP_PROJECT_ID}#g" \
    /etc/grafana/provisioning/datasources/cloud-monitoring.yml.template \
    > /etc/grafana/provisioning/datasources/cloud-monitoring.yml
fi

/run.sh &
GRAFANA_PID=$!
trap 'kill -TERM "${GRAFANA_PID}" 2>/dev/null' TERM INT

# Attendre que Grafana réponde avant d'importer le dashboard par API : le
# provisioning par fichier de ce dashboard ne déclenche jamais les requêtes
# des panneaux (bug Grafana 12 non identifié), alors que l'import par API
# fonctionne de façon fiable (même chemin de code qu'un "Save dashboard"
# depuis l'interface).
for _ in $(seq 1 60); do
  if curl -sf http://localhost:3000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

ADMIN_USER="${GF_SECURITY_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${GF_SECURITY_ADMIN_PASSWORD:-admin}"

# Le dossier "PredictMaint AI" est créé par le provisioning de fichier
# (predictmaint.yml), qui peut finir après que /api/health réponde déjà.
FOLDER_UID=""
for _ in $(seq 1 15); do
  FOLDER_UID="$(curl -sf -u "${ADMIN_USER}:${ADMIN_PASSWORD}" http://localhost:3000/api/folders \
    | jq -r '.[] | select(.title == "PredictMaint AI") | .uid' | head -n1)"
  [ -n "${FOLDER_UID}" ] && break
  sleep 1
done

for dashboard_file in /var/lib/grafana/dashboards-source/*.json; do
  [ -f "${dashboard_file}" ] || continue
  jq -n --slurpfile dashboard "${dashboard_file}" --arg folderUid "${FOLDER_UID:-}" \
    '{dashboard: ($dashboard[0] | del(.id)), overwrite: true, folderUid: $folderUid}' \
    > /tmp/dashboard-import.json
  if curl -sf -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
      -H "Content-Type: application/json" \
      -X POST http://localhost:3000/api/dashboards/db \
      -d @/tmp/dashboard-import.json > /tmp/dashboard-import-result.json; then
    echo "dashboard importé : ${dashboard_file}"
  else
    echo "échec import dashboard : ${dashboard_file}" >&2
    cat /tmp/dashboard-import-result.json >&2 || true
  fi
done

wait "${GRAFANA_PID}"
