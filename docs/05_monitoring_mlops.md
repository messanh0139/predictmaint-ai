# C5.3.3 / C5.3.4 — Monitoring et cycle MLOps

## Trois niveaux de monitoring

### Service

L'API expose `/metrics` : volume de prédictions, risque HIGH/LOW, latence, état du modèle et erreurs de persistance télémétrie. Prometheus/Grafana sont fournis pour la démonstration locale.

### Données

`src/monitoring/drift.py` calcule un **PSI** par feature avec des bornes apprises sur la référence TRAIN. Un rapport Evidently HTML peut être généré si la dépendance est installée.

Une alerte est déclenchée si une proportion significative de variables dépasse le seuil PSI. Si le volume courant est insuffisant, le système retourne explicitement `insufficient_data` au lieu d'interpréter artificiellement un PSI nul comme une absence de dérive.

### Performance

Les prédictions sont reliées à la vérité terrain reçue plus tard via `/feedback`. `src/monitoring/performance.py` recalcule recall, PR-AUC, F1 et coût métier et signale les guardrails non respectés. Pour un lot contenant plusieurs versions du modèle, **chaque prédiction est réévaluée avec le seuil versionné qui a réellement servi à produire sa décision** ; aucun seuil médian ou seuil du champion courant ne remplace l'historique. Le rapport inclut aussi un diagnostic par `model_version`.

## Historisation

Chaque prédiction contient en télémétrie :

- identifiant ;
- timestamp ;
- version modèle ;
- probabilité et décision ;
- snapshot brut courant ;
- snapshot des features sélectionnées ;
- empreinte du manifeste dataset.

En Cloud Run, le système de fichiers local est éphémère : `PREDICTION_BUCKET` active la persistance Cloud Storage.

## Réentraînement

`src/pipelines/retrain.py` exécute préparation, sélection, entraînement, optimisation optionnelle, promotion et quality gate.

Le holdout NASA est volontairement absent de ce pipeline.

## Politique de promotion

Le challenger est promu uniquement si :

1. les guardrails recall/PR-AUC passent ;
2. il est meilleur sur la VALIDATION verrouillée selon coût métier ;
3. PR-AUC/Brier servent de départage.

Ce mécanisme évite de déployer un modèle plus complexe mais moins utile.
