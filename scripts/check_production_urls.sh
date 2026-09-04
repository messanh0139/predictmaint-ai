#!/bin/bash

# Script pour récupérer les URLs de production après déploiement
# Usage: ./scripts/check_production_urls.sh

set -e

REGION="${GCP_REGION:-europe-west1}"

echo "========================================="
echo "🌐 RÉCUPÉRATION DES URLs DE PRODUCTION"
echo "========================================="
echo ""

# Vérifier si gcloud est configuré
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI n'est pas installé"
    exit 1
fi

echo "📍 Région: ${REGION}"
echo ""

# API
echo "🔍 Recherche de l'API..."
API_URL=$(gcloud run services describe predictmaint-api \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${API_URL}" ]; then
    echo "✅ API: ${API_URL}"

    # Test de santé
    echo "   Testing /ready endpoint..."
    HEALTH=$(curl -s "${API_URL}/live" 2>/dev/null || echo "")
    if [ -n "${HEALTH}" ]; then
        echo "   ✅ API répond (endpoint public /live)"
    else
        echo "   ⚠️  API ne répond pas (peut nécessiter auth)"
    fi
else
    echo "❌ API non trouvée (pas encore déployée)"
fi
echo ""

# Dashboard
echo "🔍 Recherche du Dashboard React..."
DASHBOARD_URL=$(gcloud run services describe predictmaint-dashboard \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${DASHBOARD_URL}" ]; then
    echo "✅ Dashboard: ${DASHBOARD_URL}"
    echo "   (Accessible publiquement dans votre navigateur)"
else
    echo "❌ Dashboard non trouvé (pas encore déployé)"
fi
echo ""

# Grafana
echo "🔍 Recherche de Grafana..."
GRAFANA_URL=$(gcloud run services describe predictmaint-grafana \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${GRAFANA_URL}" ]; then
    echo "✅ Grafana: ${GRAFANA_URL}"
    echo "   Login: admin"
    echo "   Password: voir Secret Manager (predictmaint-grafana-admin)"

    # Commande pour récupérer le mot de passe
    echo ""
    echo "   Pour récupérer le mot de passe:"
    echo "   gcloud secrets versions access latest --secret=predictmaint-grafana-admin"
else
    echo "⚠️  Grafana non trouvé (déploiement optionnel)"
fi
echo ""

# MLflow
echo "🔍 Recherche de MLflow..."
MLFLOW_URL=$(gcloud run services describe predictmaint-mlflow \
    --region "${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [ -n "${MLFLOW_URL}" ]; then
    echo "✅ MLflow: ${MLFLOW_URL}"
else
    echo "⚠️  MLflow non trouvé (déploiement optionnel)"
fi
echo ""

echo "========================================="
echo "🧪 COMMANDES POUR TESTER L'API"
echo "========================================="
echo ""

if [ -n "${API_URL}" ]; then
    echo "# Obtenir un token d'auth GCP"
    echo "ID_TOKEN=\$(gcloud auth print-identity-token --audiences=\"${API_URL}\")"
    echo ""
    echo "# Test de santé (public)"
    echo "curl ${API_URL}/live"
    echo ""
    echo "# Test de disponibilité (nécessite auth)"
    echo "curl -H \"Authorization: Bearer \${ID_TOKEN}\" ${API_URL}/ready"
    echo ""
    echo "# Faire une prédiction de test"
    echo "curl -X POST ${API_URL}/predict \\"
    echo "  -H \"Authorization: Bearer \${ID_TOKEN}\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d @test_prediction.json"
    echo ""
fi

echo "========================================="
echo "📊 MONITORING"
echo "========================================="
echo ""
echo "✅ Cloud Monitoring (Console GCP):"
echo "   https://console.cloud.google.com/monitoring/metrics-explorer"
echo "   Métriques: custom.googleapis.com/predictmaint/*"
echo ""

if [ -n "${GRAFANA_URL}" ]; then
    echo "✅ Grafana (Dashboards):"
    echo "   ${GRAFANA_URL}"
fi
echo ""

echo "========================================="
echo "📝 RÉSUMÉ"
echo "========================================="
echo ""

if [ -n "${API_URL}" ] && [ -n "${DASHBOARD_URL}" ]; then
    echo "✅ Déploiement réussi !"
    echo ""
    echo "🎯 Prochaines étapes:"
    echo "   1. Ouvrir le Dashboard: ${DASHBOARD_URL}"
    echo "   2. Tester une prédiction (voir commandes ci-dessus)"
    echo "   3. Configurer votre pipeline de données (voir GUIDE_MONITORING_RETRAINING.md)"
else
    echo "⏳ Déploiement en cours..."
    echo ""
    echo "Vérifiez l'avancement sur:"
    echo "https://github.com/messanh0139/predictmaint-ai/actions"
    echo ""
    echo "Relancez ce script dans quelques minutes."
fi
echo ""
