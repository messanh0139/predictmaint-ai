#!/bin/bash

# Récupère les URLs des services déployés en production.
# Usage : ./scripts/check_production_urls.sh

set -e

REGION="${GCP_REGION:-europe-west1}"

echo "Récupération des URLs de production (région ${REGION})"
echo ""

if ! command -v gcloud &> /dev/null; then
    echo "gcloud CLI n'est pas installé"
    exit 1
fi

# API
echo "Recherche de l'API..."
API_URL=$(gcloud run services describe predictmaint-api \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${API_URL}" ]; then
    echo "API : ${API_URL}"

    HEALTH=$(curl -s "${API_URL}/live" 2>/dev/null || echo "")
    if [ -n "${HEALTH}" ]; then
        echo "  API répond (endpoint public /live)"
    else
        echo "  API ne répond pas (peut nécessiter une authentification)"
    fi
else
    echo "API non trouvée (pas encore déployée)"
fi
echo ""

# Dashboard
echo "Recherche du dashboard React..."
DASHBOARD_URL=$(gcloud run services describe predictmaint-dashboard \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${DASHBOARD_URL}" ]; then
    echo "Dashboard : ${DASHBOARD_URL}"
    echo "  (accessible publiquement dans le navigateur)"
else
    echo "Dashboard non trouvé (pas encore déployé)"
fi
echo ""

# Grafana
echo "Recherche de Grafana..."
GRAFANA_URL=$(gcloud run services describe predictmaint-grafana \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${GRAFANA_URL}" ]; then
    echo "Grafana : ${GRAFANA_URL}"
    echo "  Identifiant : admin"
    echo "  Mot de passe : voir Secret Manager (predictmaint-grafana-admin)"
    echo ""
    echo "  Pour récupérer le mot de passe :"
    echo "  gcloud secrets versions access latest --secret=predictmaint-grafana-admin"
else
    echo "Grafana non trouvé (déploiement optionnel)"
fi
echo ""

# MLflow
echo "Recherche de MLflow..."
MLFLOW_URL=$(gcloud run services describe predictmaint-mlflow \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${MLFLOW_URL}" ]; then
    echo "MLflow : ${MLFLOW_URL}"
else
    echo "MLflow non trouvé (déploiement optionnel)"
fi
echo ""

echo "Commandes pour tester l'API"
echo ""

if [ -n "${API_URL}" ]; then
    echo "# Obtenir un token d'authentification GCP"
    echo "ID_TOKEN=\$(gcloud auth print-identity-token --audiences=\"${API_URL}\")"
    echo ""
    echo "# Test de santé (public)"
    echo "curl ${API_URL}/live"
    echo ""
    echo "# Test de disponibilité (nécessite une authentification)"
    echo "curl -H \"Authorization: Bearer \${ID_TOKEN}\" ${API_URL}/ready"
    echo ""
    echo "# Faire une prédiction de test"
    echo "curl -X POST ${API_URL}/predict \\"
    echo "  -H \"Authorization: Bearer \${ID_TOKEN}\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d @test_prediction.json"
    echo ""
fi

echo "Monitoring"
echo ""
echo "Cloud Monitoring (console GCP) :"
echo "  https://console.cloud.google.com/monitoring/metrics-explorer"
echo "  Métriques : custom.googleapis.com/predictmaint/*"
echo ""

if [ -n "${GRAFANA_URL}" ]; then
    echo "Grafana (dashboards) :"
    echo "  ${GRAFANA_URL}"
fi
echo ""

echo "Résumé"
echo ""

if [ -n "${API_URL}" ] && [ -n "${DASHBOARD_URL}" ]; then
    echo "Déploiement réussi."
    echo ""
    echo "Prochaines étapes :"
    echo "  1. Ouvrir le dashboard : ${DASHBOARD_URL}"
    echo "  2. Tester une prédiction (voir commandes ci-dessus)"
    echo "  3. Consulter GUIDE_UTILISATION.md pour la suite"
else
    echo "Déploiement en cours..."
    echo ""
    echo "Vérifiez l'avancement sur :"
    echo "https://github.com/messanh0139/predictmaint-ai/actions"
    echo ""
    echo "Relancez ce script dans quelques minutes."
fi
echo ""
