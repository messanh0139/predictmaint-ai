# Choix technologiques et algorithmiques

| Besoin | Choix | Avantages | Limites / alternative |
|---|---|---|---|
| Langage | Python 3.12 | standard DS/MLOps, écosystème large | R/Julia possibles mais moins alignés avec stack API |
| Data | pandas / NumPy | simple et suffisant pour ~20k lignes | Spark inutile à ce volume |
| ML | scikit-learn | pipelines, métriques, modèles baseline | pas un framework deep learning |
| Boosting | XGBoost | performant tabulaire, class imbalance | coût tuning supérieur |
| Optimisation | Optuna | TPE, reproductibilité, historique essais | RandomizedSearch plus simple |
| Tracking | MLflow | paramètres, métriques, artefacts | nécessite stockage persistant en équipe |
| API | FastAPI / Pydantic | contrat typé, faible friction | Flask plus minimal |
| Sérialisation | joblib + JSON metadata | simple, réutilisable | format Python dépend des versions librairies |
| Conteneur | Docker | reproductibilité | image à maintenir/scanner |
| CI/CD | GitHub Actions / Cloud Build | automatisation et audit | dépend de la gouvernance choisie |
| Registry image | Artifact Registry | natif GCP | vendor lock-in GCP |
| Runtime | Cloud Run | serverless, scale-to-zero, service container | moins de contrôle qu'un cluster Kubernetes |
| Drift | PSI + Evidently optionnel | métrique machine-readable + rapport visuel | seuils à calibrer métier |
| Service monitoring | Prometheus/Grafana local | démo portable | en GCP, Cloud Monitoring est plus naturel |
| Télémétrie | JSONL local + Cloud Storage | auditabilité simple | BigQuery préférable à grand volume |

