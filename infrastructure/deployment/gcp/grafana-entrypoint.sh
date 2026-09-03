#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

sed "s#__PROJECT_ID__#${GCP_PROJECT_ID}#g" \
  /etc/grafana/provisioning/datasources/cloud-monitoring.yml.template \
  > /etc/grafana/provisioning/datasources/cloud-monitoring.yml

exec /run.sh
