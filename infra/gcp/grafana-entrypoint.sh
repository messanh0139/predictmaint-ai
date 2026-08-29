#!/usr/bin/env bash
set -euo pipefail

: "${PROMETHEUS_URL:?Set PROMETHEUS_URL}"

sed "s#__PROMETHEUS_URL__#${PROMETHEUS_URL}#g" \
  /etc/grafana/provisioning/datasources/prometheus.yml.template \
  > /etc/grafana/provisioning/datasources/prometheus.yml

exec /run.sh
