# Plan de soutenance (30 min)

## 1. Besoin et faisabilité — 3 min

- contexte INDUSTRIA SAS ;
- coût des pannes ;
- question métier ;
- contraintes et limites du dataset.

## 2. Traduction en problème ML — 2 min

- classification `RUL <= 30` ;
- coût faux négatif / faux positif ;
- métriques retenues.

## 3. Données et EDA — 4 min

- 20 631 lignes / 100 moteurs train ;
- trajectoires 128 à 362 cycles ;
- ~15 % de classe positive ;
- capteurs constants ;
- capteurs liés à la dégradation.

## 4. Data leakage — 3 min

Présenter le schéma TRAIN / CALIBRATION / VALIDATION / TEST EXTERNE et démontrer que les moteurs sont disjoints. Montrer le test de causalité des features.

## 5. Feature engineering et sélection — 4 min

- lag, diff, rolling, EWM ;
- variance, corrélation, MI, RF, L1 ;
- tableau `feature_selection_report.csv`.

## 6. Entraînement et comparaison — 4 min

- Logistic, Random Forest, XGBoost ;
- calibration du seuil sur partition dédiée ;
- leaderboard validation.

## 7. Optimisation — 3 min

- Optuna + StratifiedGroupKFold sur TRAIN ;
- 10 essais de démonstration dans le dépôt ;
- gain métier du challenger et décision de promotion.

## 8. Industrialisation — 4 min

- joblib + métadonnées + MLflow ;
- FastAPI ;
- Docker ;
- CI/CD ;
- Cloud Run / Artifact Registry / WIF.

## 9. Monitoring et lifecycle — 2 min

- Prometheus/Grafana ;
- PSI/Evidently ;
- feedback ;
- retraining ;
- champion/challenger.

## 10. Conclusion — 1 min

- résultat ;
- limites ;
- extension FD004 / données réelles.

## Questions jury à anticiper

- Pourquoi ne pas faire un split aléatoire par ligne ?
- Pourquoi le seuil n'est-il pas 0,5 ?
- Pourquoi utiliser une partition calibration séparée ?
- Pourquoi PR-AUC plutôt qu'accuracy ?
- Pourquoi XGBoost optimisé a-t-il été promu alors que certains scores changent peu ?
- Comment détecter un drift en production ?
- Que se passe-t-il si un nouveau modèle échoue au quality gate ?
- Pourquoi Cloud Run plutôt que Kubernetes ?
- Comment garantir que le test externe n'a pas influencé le développement ?
