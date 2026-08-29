# Cahier de tests

## Tests data

- dimensions et nombre de moteurs attendus ;
- schéma complet ;
- aucune clé `(engine_id, cycle)` dupliquée ;
- aucune valeur manquante/non finie brute ;
- reconstruction/alignement du RUL testés sur données synthétiques sans ouvrir la vérité terrain réelle pendant la CI ;
- partitions train/calibration/validation sans moteur commun.

## Tests features

- isolation par moteur ;
- rolling causal ;
- mutation du futur sans effet sur le passé ;
- colonnes de vérité terrain interdites au modèle.

## Tests modèle

- coût métier pénalise correctement les faux négatifs ;
- seuil respecte le recall minimal lorsqu'un seuil faisable existe ;
- quality gate refuse un modèle sous les seuils attendus.

## Tests API

- liveness disponible sans modèle ;
- readiness retourne 503 sans artefacts ;
- validation des cycles croissants ;
- prédiction avec modèle mocké ;
- métriques Prometheus exposées.

## Tests monitoring

- application du seuil versionné propre à chaque prédiction ;
- diagnostic par version lorsque plusieurs modèles coexistent dans un même lot ;
- absence de remplacement des seuils historiques par une médiane globale ;
- statut `insufficient_data` lorsque le volume de monitoring drift est trop faible.

## CI

La CI exécute lint, tests, préparation des données, sélection de variables, entraînement et quality gate validation. Le holdout externe n'est pas utilisé dans la CI courante.
