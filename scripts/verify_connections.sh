#!/bin/bash

# Script de vérification des connexions automatiques
# Ce script vérifie que tous les services docker-compose peuvent se connecter entre eux

echo "=== Vérification des connexions automatiques ==="
echo ""

# Fonction pour vérifier une URL
check_url() {
    local service=$1
    local url=$2
    local expected=$3

    echo -n "Vérification $service ($url)... "

    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)

    if [ "$response" = "$expected" ]; then
        echo "OK (HTTP $response)"
        return 0
    else
        echo "ERREUR (HTTP $response, attendu $expected)"
        return 1
    fi
}

# Vérifier que docker-compose est lancé
if ! docker compose -f infrastructure/deployment/docker-compose.yml ps | grep -q "Up"; then
    echo "Erreur: Les services docker-compose ne sont pas démarrés"
    echo "Lancez d'abord: docker compose -f infrastructure/deployment/docker-compose.yml up -d"
    exit 1
fi

echo "Services docker-compose actifs:"
docker compose -f infrastructure/deployment/docker-compose.yml ps --format "table {{.Name}}\t{{.Status}}" | grep -v "NAME"
echo ""

# Attendre que les services soient prêts
echo "Attente du démarrage des services (15 secondes)..."
sleep 15
echo ""

# Vérification des services de base
echo "--- Services de base ---"
check_url "API Health" "http://localhost:8001/health" "200"
check_url "API Docs" "http://localhost:8001/docs" "200"
check_url "Dashboard" "http://localhost:3002" "200"
check_url "MLflow" "http://localhost:5001" "200"
check_url "Airflow" "http://localhost:8081" "200"
check_url "Prometheus" "http://localhost:9090" "200"
check_url "Grafana" "http://localhost:3001" "302"
echo ""

# Vérification des métriques Prometheus
echo "--- Métriques Prometheus ---"
echo -n "Vérification que Prometheus scrape l'API... "
metrics=$(curl -s "http://localhost:9090/api/v1/targets" | grep -c "api:8080")
if [ "$metrics" -gt 0 ]; then
    echo "OK (target configuré)"
else
    echo "ERREUR (target api:8080 non trouvé)"
fi
echo ""

# Vérification que l'API expose des métriques
echo -n "Vérification que l'API expose des métriques... "
api_metrics=$(curl -s "http://localhost:8001/metrics" | grep -c "predictmaint_")
if [ "$api_metrics" -gt 0 ]; then
    echo "OK ($api_metrics métriques trouvées)"
else
    echo "ERREUR (aucune métrique predictmaint_ trouvée)"
fi
echo ""

# Résumé
echo "=== Résumé ==="
echo "Services fonctionnels:"
echo "  - API: http://localhost:8001"
echo "  - Dashboard: http://localhost:3002"
echo "  - Grafana: http://localhost:3001 (login: admin/admin)"
echo "  - MLflow: http://localhost:5001"
echo "  - Airflow: http://localhost:8081 (login: admin/admin)"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "Pour générer des métriques dans Grafana:"
echo "  python scripts/generate_predictions_for_grafana.py --api-url http://localhost:8001 --num 50"
echo ""
