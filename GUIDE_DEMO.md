# Guide de démonstration

Ce guide montre comment faire la démo du projet avec les fonctionnalités automatiques.

## Préparation

### 1. Démarrer tous les services

```bash
cd /home/jes/Bureau/predictmaint-ai

# Lancer tous les services
docker compose -f infrastructure/deployment/docker-compose.yml up -d

# Attendre 30 secondes que tout démarre
sleep 30

# Vérifier que tout fonctionne
docker compose -f infrastructure/deployment/docker-compose.yml ps
```

Tous les services doivent être "Up".

### 2. Vérifier que le modèle est chargé

```bash
# Vérifier l'API
curl http://localhost:8001/health
```

Tu dois voir:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "xgboost_optimized",
  ...
}
```

## Démo 1: DAG Airflow (Pipeline automatique)

### Étape 1: Accéder à Airflow

1. Ouvrir dans le navigateur: http://localhost:8081
2. Login: **admin**
3. Mot de passe: **admin**

### Étape 2: Activer le DAG Pipeline 1 (ETL)

1. Dans la liste des DAGs, chercher **pipeline_1_etl_ingestion**
2. Cliquer sur le bouton à gauche pour activer le DAG (il devient bleu)
3. Cliquer sur le nom du DAG pour voir les détails
4. Cliquer sur le bouton "Trigger DAG" (icône play en haut à droite)
5. Confirmer en cliquant "Trigger"

Le DAG va automatiquement:
- Charger les données dans MongoDB
- Transformer les données
- Sauvegarder dans PostgreSQL
- Créer les fichiers CSV

### Étape 3: Suivre l'exécution

1. Tu verras les tâches s'exécuter une par une (couleur verte = succès)
2. Cliquer sur une tâche puis "Log" pour voir les détails
3. L'exécution complète prend environ 1-2 minutes

### Étape 4: Vérifier les résultats

```bash
# Vérifier MongoDB
docker exec -it predictmaint-mongodb mongosh -u admin -p admin123
```

Dans MongoDB:
```javascript
use predictmaint
db.train_raw.countDocuments()  // Doit afficher ~20631
exit
```

```bash
# Vérifier PostgreSQL
docker exec -it predictmaint-postgresql psql -U postgres -d predictmaint
```

Dans PostgreSQL:
```sql
SELECT COUNT(*) FROM train_features;  -- Doit afficher ~14000
\q
```

### Étape 5: Activer le DAG Pipeline 2 (MLOps)

1. Revenir à la page d'accueil Airflow
2. Chercher **pipeline_2_training_mlops**
3. Activer le DAG
4. Cliquer sur "Trigger DAG"

Le DAG va automatiquement:
- Lire les données depuis PostgreSQL
- Entraîner 3 modèles (Logistic Regression, Random Forest, XGBoost)
- Optimiser avec Optuna (30 trials)
- Sélectionner le champion
- Valider avec quality gates
- Enregistrer dans MLflow
- Sauvegarder le modèle

L'exécution complète prend environ 15-20 minutes.

### Étape 6: Voir les résultats dans MLflow

1. Ouvrir dans le navigateur: http://localhost:5001
2. Tu verras toutes les expérimentations
3. Cliquer sur une run pour voir les détails (métriques, paramètres, artefacts)

## Démo 2: Réentraînement automatique via API

### Étape 1: Préparer les données de démo

```bash
# Générer des nouvelles données avec drift
python scripts/generate_demo_data_with_drift.py
```

Le fichier **demo_data_with_drift.csv** est créé avec:
- 50 moteurs
- Drift progressif de 0% à 40%
- IDs moteurs > 5000000 pour éviter les overlaps

### Étape 2: Uploader via l'API

```bash
# Uploader les données et déclencher le réentraînement
curl -X POST http://localhost:8001/retrain/upload \
  -F "file=@demo_data_with_drift.csv"
```

Réponse:
```json
{
  "message": "Réentraînement démarré",
  "rows_added": 5432,
  "optimize": true,
  "trials": 30
}
```

Le système va automatiquement:
1. Valider le fichier CSV
2. Vérifier que les IDs moteurs n'overlappent pas avec validation
3. Ajouter les données au training set
4. Lancer le réentraînement complet
5. Optimiser avec Optuna (30 trials)
6. Valider avec quality gates
7. Promouvoir si meilleur que le champion actuel

### Étape 3: Suivre le statut

```bash
# Voir le statut en temps réel
curl http://localhost:8001/retrain/status
```

Réponse pendant l'exécution:
```json
{
  "state": "running",
  "started_at": "2026-09-05T14:30:00Z",
  "rows_added": 5432,
  "optimize": true,
  "trials": 30,
  "current_step": "Optimisation Optuna (trial 15/30)"
}
```

Réponse quand c'est terminé:
```json
{
  "state": "completed",
  "started_at": "2026-09-05T14:30:00Z",
  "completed_at": "2026-09-05T14:50:00Z",
  "rows_added": 5432,
  "optimize": true,
  "trials": 30,
  "champion_model": "xgboost_optimized",
  "champion_metrics": {
    "recall": 1.0,
    "pr_auc": 0.952
  }
}
```

Le réentraînement prend environ 15-20 minutes.

### Étape 4: Vérifier le nouveau modèle

```bash
# Vérifier que l'API a chargé le nouveau modèle
curl http://localhost:8001/health
```

Tu verras le nouveau modèle dans la réponse.

## Démo 3: Réentraînement via Dashboard

C'est la méthode la plus visuelle pour une démo.

### Étape 1: Ouvrir le Dashboard

Navigateur: http://localhost:3002

### Étape 2: Aller dans l'onglet Réentraînement

1. Cliquer sur "Réentraînement automatique" dans le menu
2. Tu verras le statut actuel du modèle

### Étape 3: Télécharger le fichier exemple

1. Cliquer sur "Télécharger fichier exemple CSV"
2. Un fichier **example_retraining_data.csv** sera téléchargé

### Étape 4: Uploader les données

1. Cliquer sur "Choisir un fichier"
2. Sélectionner le fichier (exemple ou **demo_data_with_drift.csv**)
3. Cliquer sur "Lancer le réentraînement"

### Étape 5: Suivre la progression

Le dashboard affiche en temps réel:
- État: "En cours"
- Étape actuelle
- Nombre de lignes ajoutées
- Temps écoulé

Rafraîchissement automatique toutes les 10 secondes.

### Étape 6: Voir les résultats

Quand c'est terminé, le dashboard affiche:
- Nouveau modèle champion
- Métriques (recall, PR-AUC)
- Temps total d'exécution
- Logs détaillés

## Démo 4: Monitoring avec Grafana

### Étape 1: Générer des métriques

```bash
# Générer 50 prédictions pour alimenter Grafana
python scripts/generate_predictions_for_grafana.py \
  --api-url http://localhost:8001 \
  --num 50
```

Le script fait 50 prédictions avec des données aléatoires.

### Étape 2: Ouvrir Grafana

1. Navigateur: http://localhost:3001
2. Login: **admin**
3. Mot de passe: **admin**

### Étape 3: Voir le dashboard

1. Menu "Dashboards"
2. Sélectionner "PredictMaint AI"
3. Tu verras:
   - Nombre de prédictions
   - Distribution des risques (LOW, MEDIUM, HIGH)
   - Drift global
   - Latence des prédictions
   - Graphiques temporels

## Démo 5: Prédiction simple

### Via l'API

```bash
# Faire une prédiction
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": 999999,
    "cycle": 100,
    "sensor_1": 518.67,
    "sensor_2": 641.82,
    "sensor_3": 1589.70
  }'
```

Réponse:
```json
{
  "prediction_id": "abc123...",
  "failure_probability": 0.15,
  "risk": "LOW",
  "threshold": 0.5,
  "model_name": "xgboost_optimized",
  "model_version": "...",
  "drift": 0.03
}
```

### Via le Dashboard

1. Aller sur http://localhost:3002
2. Onglet "Démonstration prédictive"
3. Sélectionner un moteur dans la liste
4. Cliquer sur "Prédire"
5. Le résultat s'affiche avec:
   - Probabilité de panne
   - Niveau de risque (couleur)
   - Seuil utilisé
   - Modèle utilisé
   - Drift détecté

## Scénario de démo complet (15 minutes)

### Minute 0-2: Montrer l'architecture
1. Expliquer les 3 pipelines
2. Montrer docker-compose.yml
3. Montrer les services qui tournent

### Minute 2-5: Dashboard et prédictions
1. Ouvrir le dashboard
2. Montrer le modèle actuel (xgboost_optimized, 100% recall)
3. Faire 3-4 prédictions
4. Montrer les graphiques de performance

### Minute 5-8: Airflow DAG
1. Ouvrir Airflow
2. Montrer les deux DAGs
3. Déclencher le Pipeline 1 (ETL)
4. Montrer l'exécution en temps réel
5. Expliquer MongoDB puis PostgreSQL

### Minute 8-12: Réentraînement automatique
1. Revenir au dashboard
2. Uploader le fichier de démo
3. Montrer le statut qui change
4. Expliquer: validation, entraînement, optimisation, quality gates
5. Pendant que ça tourne, passer à Grafana

### Minute 12-15: Monitoring
1. Ouvrir Grafana
2. Montrer les métriques en temps réel
3. Ouvrir MLflow
4. Montrer les expérimentations trackées
5. Montrer les artefacts (modèles sauvegardés)

## Conseils pour la démo

### Avant de commencer
- Lance tous les services 5 minutes avant
- Vérifie que tout est "Up"
- Prépare le fichier demo_data_with_drift.csv
- Ouvre tous les onglets du navigateur à l'avance

### Pendant la démo
- Commence par le dashboard (plus visuel)
- Fais des prédictions pour montrer que ça marche
- Montre Airflow pour l'orchestration
- Lance un réentraînement (ça prend 15-20 min)
- Pendant le réentraînement, montre Grafana et MLflow

### Points à souligner
- Tout est automatique (aucune intervention manuelle)
- MongoDB et PostgreSQL fonctionnent
- Quality gates empêchent les mauvais modèles
- Drift détecté automatiquement
- Production feedback loop
- Architecture MLOps complète

## Arrêter la démo

```bash
# Arrêter tous les services
docker compose -f infrastructure/deployment/docker-compose.yml down
```

Pour tout supprimer (bases de données incluses):
```bash
docker compose -f infrastructure/deployment/docker-compose.yml down -v
```
