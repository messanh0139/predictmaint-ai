#!/bin/bash
# Script de test du retraining automatique
# Usage: ./test_retraining.sh

set -e

echo "Test de retraining automatique"
echo ""

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' 

# Variables
API_URL="http://localhost:8000"
DEMO_FILE="demo_nouvelles_donnees.csv"

echo -e "${BLUE}1. Vérification du fichier de démonstration${NC}"
if [ ! -f "$DEMO_FILE" ]; then
    echo -e "${RED}Erreur: $DEMO_FILE introuvable${NC}"
    echo "Générez-le d'abord avec le script Python fourni."
    exit 1
fi
echo -e "${GREEN}OK - Fichier trouvé ($(wc -l < $DEMO_FILE) lignes)${NC}"
echo ""

echo -e "${BLUE}2. Vérification de l'API${NC}"
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}Erreur: L'API n'est pas accessible à $API_URL${NC}"
    echo "Lancez l'API d'abord : cd pipelines/3_inference_ihm/api && uvicorn main:app --reload"
    exit 1
fi
echo -e "${GREEN}OK - API en ligne${NC}"
echo ""

echo -e "${BLUE}3. État actuel du modèle${NC}"
CURRENT_VERSION=$(curl -s "$API_URL/ready" | python3 -c "import sys, json; print(json.load(sys.stdin).get('model_version', 'N/A'))")
echo "Version actuelle : $CURRENT_VERSION"
echo ""

echo -e "${BLUE}4. Upload des nouvelles données pour retraining${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/retrain/upload" -F "file=@$DEMO_FILE")
echo "$RESPONSE" | python3 -m json.tool
echo ""

STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))")
if [ "$STATUS" != "retrain_triggered" ]; then
    echo -e "${RED}Erreur lors du déclenchement du retraining${NC}"
    exit 1
fi

ROWS_ADDED=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('rows_added', 0))")
echo -e "${GREEN}Retraining déclenché avec $ROWS_ADDED lignes ajoutées${NC}"
echo ""

echo -e "${BLUE}5. Suivi de l'avancement (peut prendre 15-20 minutes)${NC}"
echo "Appuyez sur Ctrl+C pour arrêter le suivi (le retraining continue en arrière-plan)"
echo ""

while true; do
    STATUS_RESPONSE=$(curl -s "$API_URL/retrain/status")
    STATE=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('state', 'unknown'))")

    if [ "$STATE" = "completed" ]; then
        echo -e "${GREEN}Retraining terminé avec succès !${NC}"
        echo "$STATUS_RESPONSE" | python3 -m json.tool

        NEW_VERSION=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('model_version', 'N/A'))")
        echo ""
        echo "Ancien modèle : $CURRENT_VERSION"
        echo "Nouveau modèle : $NEW_VERSION"
        break
    elif [ "$STATE" = "failed" ]; then
        echo -e "${RED}Le retraining a échoué${NC}"
        echo "$STATUS_RESPONSE" | python3 -m json.tool
        exit 1
    elif [ "$STATE" = "running" ]; then
        STARTED=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('started_at', 'N/A'))" | cut -d'T' -f2 | cut -d'.' -f1)
        echo "[$(date +%H:%M:%S)] État: $STATE (démarré à $STARTED)"
    else
        echo "[$(date +%H:%M:%S)] État: $STATE"
    fi

    sleep 30
done

echo ""
echo -e "${BLUE}6. Vérification du nouveau modèle${NC}"
NEW_MODEL_INFO=$(curl -s "$API_URL/ready")
echo "$NEW_MODEL_INFO" | python3 -m json.tool
echo ""

echo -e "${GREEN}Test terminé avec succès${NC}"
echo ""
echo "Prochaines étapes :"
echo "- Vérifier les métriques : cat storage/models/model_metadata.json"
echo "- Voir le leaderboard : cat storage/models/leaderboard.csv"
echo "- Tester une prédiction avec le nouveau modèle"
