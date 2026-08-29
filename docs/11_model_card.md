# Model Card — PredictMaint AI

## Usage prévu

Priorisation de maintenance à partir de séquences de capteurs du jeu de données FD001. Sortie : probabilité d'une défaillance dans les 30 prochains cycles.

## Usage non prévu

Le modèle ne doit pas être utilisé tel quel pour prendre automatiquement une décision de sécurité industrielle réelle sans validation terrain, calibration métier, analyse de risques et procédure humaine.

## Données

Jeu de données FD001, données simulées run-to-failure. Empreintes SHA256 stockées dans `data/processed/split_manifest.json` et `models/model_metadata.json`.

## Métriques

Métriques principales : recall, PR-AUC, F1 et coût métier. ROC-AUC et Brier sont conservés comme diagnostics complémentaires.

## Seuil

Le seuil est ajusté uniquement sur la partition CALIBRATION, indépendante du TRAIN et de la VALIDATION.

## Validation

La sélection du champion se fait sur une partition VALIDATION par moteurs distincts. Le test externe constitue un holdout explicitement séparé.

## Limites

FD001 ne couvre qu'une condition opérationnelle et un mode de panne. Les coûts FN/FP sont des hypothèses fictives. La performance sur données réelles reste à démontrer.
