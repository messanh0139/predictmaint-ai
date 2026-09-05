# Guide d'utilisation - PredictMaint AI

Ce guide explique comment utiliser le projet en production et en local.

## En production (Cloud Run)

### URLs du projet
- Dashboard : https://predictmaint-dashboard-6iao6qpasa-ew.a.run.app
- API : https://predictmaint-api-6iao6qpasa-ew.a.run.app
- Grafana : https://predictmaint-grafana-6iao6qpasa-ew.a.run.app
- MLflow : (à déployer si nécessaire)

### Utilisation du dashboard

1. **Voir l'état du système**
   - En haut de la page : statut de l'API et du modèle
   - Métriques du modèle champion : nom, recall, PR-AUC

2. **Faire une prédiction**
   - Onglet "Démonstration prédictive"
   - Choisir un moteur dans la liste
   - Cliquer sur "Prédire"
   - Le système affiche le risque de panne

3. **Voir les performances**
   - Onglet "Performance"
   - Graphiques de métriques du modèle
   - Matrice de confusion

4. **Réentraîner le modèle**
   - Onglet "Réentraînement automatique"
   - Télécharger l'exemple de fichier CSV
   - Uploader vos nouvelles données
   - Le système réentraîne automatiquement (15-20 minutes)

### Utilisation de Grafana

1. **Se connecter**
   - Aller sur l'URL Grafana
   - Login : admin
   - Mot de passe : (défini dans les variables d'environnement)

2. **Voir les métriques**
   - Menu Dashboards
   - Sélectionner "PredictMaint AI - Cloud Monitoring"
   - Attendre que des prédictions soient faites (voir GUIDE_GRAFANA.md)

## En local (docker-compose)

### Démarrer tous les services

```bash
cd /home/jes/Bureau/predictmaint-ai

# Lancer tous les services
docker compose -f infrastructure/deployment/docker-compose.yml up --build -d

# Vérifier que tout tourne
docker compose -f infrastructure/deployment/docker-compose.yml ps

# Vérifier que les connexions fonctionnent (optionnel)
./scripts/verify_connections.sh
```

### Mode standard vs mode complet

Le projet supporte deux modes:

**Mode standard (par défaut):**
- Données en CSV dans storage/
- MongoDB et PostgreSQL démarrés
- Rapide et simple

**Mode complet (MongoDB + PostgreSQL):**
```bash
# 1. Initialiser les bases de données
python scripts/init_databases.py

# 2. Lancer la transformation
USE_DATABASES=1 python -m src.data.prepare

# 3. Ou utiliser Airflow (active automatiquement le mode complet)
# http://localhost:8080 - DAG pipeline_1_etl_ingestion
```

Voir GUIDE_DATABASES.md pour plus de détails sur le mode complet.

### Services disponibles

Une fois démarré, vous pouvez accéder à :

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Interface utilisateur |
| API | http://localhost:8000 | API de prédiction |
| API Docs | http://localhost:8000/docs | Documentation interactive |
| Grafana | http://localhost:3001 | Monitoring (login: admin/admin) |
| MLflow | http://localhost:5000 | Tracking expérimentations |
| Airflow | http://localhost:8080 | Orchestration (login: admin/admin) |
| Prometheus | http://localhost:9090 | Base de métriques |

### Arrêter les services

```bash
docker compose -f infrastructure/deployment/docker-compose.yml down
```

### Voir les logs

```bash
# Tous les services
docker compose -f infrastructure/deployment/docker-compose.yml logs -f

# Un service spécifique
docker compose -f infrastructure/deployment/docker-compose.yml logs -f api
```

## Tester le retraining

### En production

```bash
# 1. Télécharger le fichier exemple depuis le dashboard
# 2. L'uploader via l'interface
# 3. Attendre 15-20 minutes
# 4. Vérifier les logs dans l'onglet de statut
```

### En local

```bash
# 1. Créer des données de test
python examples/generer_dataset_demo.py --moteurs 5 --output test_data.csv

# 2. Lancer le script de test
./examples/test_retraining.sh
```

## Générer des prédictions pour Grafana

Pour que Grafana affiche des données, il faut d'abord générer des prédictions :

```bash
# En production
python scripts/generate_predictions_for_grafana.py \
  --api-url https://predictmaint-api-6iao6qpasa-ew.a.run.app \
  --num 50

# En local
python scripts/generate_predictions_for_grafana.py \
  --api-url http://localhost:8000 \
  --num 50
```

## Développement

### Lancer uniquement l'API en local

```bash
cd pipelines/3_inference_ihm/api
uvicorn main:app --reload --port 8000
```

### Lancer uniquement le frontend

```bash
cd pipelines/3_inference_ihm/frontend
npm install
npm start
```

### Lancer les tests

```bash
# Tous les tests
pytest infrastructure/tests/ -v

# Un test spécifique
pytest infrastructure/tests/test_api.py -v
```

## Résolution de problèmes

### Le retraining échoue
1. Vérifier les logs dans l'onglet "Réentraînement automatique"
2. Vérifier que le CSV contient toutes les colonnes requises
3. Vérifier que les IDs moteurs sont > 5000000 pour éviter les overlaps

### Grafana affiche "No data"
1. Vérifier qu'on utilise le bon dashboard (Cloud Monitoring pour production)
2. Générer des prédictions pour créer des métriques
3. Attendre 2-3 minutes que les métriques soient envoyées
4. Voir GUIDE_GRAFANA.md pour plus de détails

### L'API ne répond pas
1. Vérifier que le modèle est bien présent dans storage/models/
2. Vérifier les logs de l'API
3. Tester l'endpoint /health pour voir l'erreur exacte

## Support

Pour toute question, consulter :
- ETAT_IMPLEMENTATION.md : état réel de l'implémentation (MongoDB, PostgreSQL, etc.)
- GUIDE_GRAFANA.md : problèmes Grafana
- CORRECTIONS_REALISEES.md : liste des corrections apportées
- examples/README_DEMO.md : guide de démonstration
- GUIDE_DEMONSTRATION_GCP.md : déploiement GCP complet
