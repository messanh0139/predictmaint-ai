# Matrice de traçabilité — Bloc 5

Cette matrice relie chaque compétence du Bloc 5 aux preuves réellement présentes dans le dépôt.

| Compétence | Ce qui est démontré | Preuves techniques | Preuve soutenance |
|---|---|---|---|
| C5.1.1 | besoin, contexte, contraintes, faisabilité | `docs/01_besoin_metier.md` | slide besoin + KPI métier |
| C5.1.2 | traduction du besoin en classification, fonction de coût | `docs/02_strategie_ml.md`, `src/models/common.py` | schéma problème métier -> problème ML |
| C5.1.3 | comparaison outils/algorithmes/coût/maintenabilité | `docs/03_choix_technologiques.md` | tableau de choix technologiques |
| C5.2.1 | features brutes + temporelles causales | `src/features/build_features.py`, notebook 02 | exemples lag/rolling/EWM et preuve de causalité |
| C5.2.2 | variance, corrélation, MI, RF embedded, L1 | `src/features/select_features.py`, `models/feature_selection_report.csv` | tableau de ranking + variables retirées |
| C5.2.3 | entraînement Logistic/RF/XGB, inférence | `src/models/train.py`, `models/leaderboard.csv` | comparaison candidats |
| C5.2.4 | Optuna + group CV + comparaison avant/après | `src/models/optimize.py`, `models/optimization_report.json` | gain PR-AUC + décision champion/challenger |
| C5.3.1 | sérialisation, métadonnées, versioning, MLflow | `models/model.joblib`, `model_metadata.json`, `mlruns/` | rechargement modèle + contrat |
| C5.3.2 | API, Docker, CI/CD, Cloud Run | `api/main.py`, `Dockerfile`, `.github/workflows/`, `cloudbuild.yaml` | démo endpoint + pipeline CI/CD |
| C5.3.3 | monitoring service, performance et drift | `src/monitoring/`, Prometheus/Grafana provisionné, Evidently optionnel, seuils versionnés | dashboard + rapport drift + alertes + suivi par version |
| C5.3.4 | collecte prédictions/feedback et retraining | `/feedback`, `src/pipelines/retrain.py` | boucle de vie complète |

## Compétences critiques

Les quatre compétences de développement de modèle doivent être montrées avec des preuves exécutées, pas seulement décrites :

- **C5.2.1** : démontrer que les variables temporelles ne regardent jamais le futur.
- **C5.2.2** : montrer plusieurs méthodes de sélection et expliquer le compromis.
- **C5.2.3** : présenter l'entraînement, les métriques et une inférence réelle.
- **C5.2.4** : montrer Optuna, les hyperparamètres, le gain et la règle de non-promotion si le candidat reste moins bon métier.

## Lisibilité et industrialisation

La séparation entre démonstration explicite dans les notebooks et code réutilisable dans `src/` est documentée dans `docs/14_notebooks_et_code_production.md`.
