#!/usr/bin/env bash
set -euo pipefail

: "${API_HOST:?Set API_HOST}"
TOKEN_FILE=/prometheus/token
CONFIG_FILE=/etc/prometheus/prometheus.yml

# L'API cible est un service Cloud Run privé : Prometheus doit présenter un jeton
# d'identité à chaque scrape. Les jetons GCP expirent après ~1h, donc on les
# renouvelle en continu dans un fichier que Prometheus relit à chaque requête
# (authorization.credentials_file), sans jamais avoir besoin de recharger sa config.
refresh_token() {
  while true; do
    if curl -sf -H "Metadata-Flavor: Google" \
      "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=https://${API_HOST}&format=full" \
      -o "$TOKEN_FILE.tmp"; then
      mv "$TOKEN_FILE.tmp" "$TOKEN_FILE"
      echo "[entrypoint] identity token refreshed ($(wc -c < "$TOKEN_FILE") bytes)" >&2
    else
      echo "[entrypoint] identity token fetch failed (curl exit $?)" >&2
    fi
    sleep 3000
  done
}
refresh_token &

for i in $(seq 1 30); do
  [ -s "$TOKEN_FILE" ] && break
  echo "[entrypoint] waiting for identity token ($i/30)..." >&2
  sleep 1
done

sed "s/__API_HOST__/${API_HOST}/g" /etc/prometheus/prometheus.yml.template > "$CONFIG_FILE"

exec /usr/local/bin/prometheus \
  --config.file="$CONFIG_FILE" \
  --storage.tsdb.path=/prometheus \
  --web.listen-address=":${PORT:-9090}"
