# Risques, limites et mesures de maîtrise

| Risque | Impact | Mesure |
|---|---|---|
| Data leakage par moteur | scores artificiels | split par `engine_id` avant features |
| Fuite temporelle | modèle irréaliste | features causales + tests de mutation futur |
| Sur-optimisation du seuil | généralisation réduite | partition CALIBRATION dédiée |
| Sur-optimisation modèle | validation contaminée | Group CV sur TRAIN + validation verrouillée |
| Test externe réutilisé | test transformé en validation | absent de retraining/quality gate |
| Déséquilibre classes | accuracy trompeuse | recall, PR-AUC, coût métier |
| Dataset simulé | transfert terrain incertain | déclarer la limite + valider sur données réelles |
| Drift | baisse performance | PSI/Evidently + feedback + alertes |
| Modèle plus complexe mais moins utile | dette technique | champion/challenger + règle de promotion |
| Secret exposé en CI | incident sécurité | WIF + Secret Manager, pas de clé JSON |
| Privilèges GCP excessifs | surface d'attaque | comptes deployer/runtime séparés |
