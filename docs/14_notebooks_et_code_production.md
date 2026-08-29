# Notebooks pédagogiques et code de production

## Principe

Le projet utilise deux niveaux complémentaires :

- **Notebooks** : transparence méthodologique, exploration, visualisation, démonstration au jury. Les opérations structurantes sont écrites explicitement (`pd.read_csv`, calcul RUL, split par moteur, construction de features, sélection, métriques).
- **`src/`** : version refactorisée, testable et réutilisable dans la CI/CD, l'API, le retraining et le monitoring.

Cette séparation évite deux écueils : un projet opaque où les notebooks ne montrent rien, et un projet non industrialisable où toute la logique reste copiée dans des notebooks.

## Règle anti-fuite renforcée

L'EDA supervisée elle-même peut devenir une source de fuite si l'on regarde VALIDATION/TEST avant de choisir les variables. Par conséquent :

1. contrôle structurel des données brutes ;
2. création de la vérité terrain train ;
3. split par `engine_id` ;
4. analyses utilisant RUL/cible sur TRAIN uniquement ;
5. feature engineering séparé par partition ;
6. sélection fit sur TRAIN ;
7. modèle fit sur TRAIN ;
8. seuil choisi sur CALIBRATION ;
9. champion choisi sur VALIDATION ;
10. holdout externe et sa vérité terrain ouverts seulement pour l'évaluation externe finale ; aucun `test_features.csv` n'est matérialisé dans le pipeline de développement.

## Traçabilité

Chaque notebook indique à quel moment il passe de la démonstration explicite au module `src/` correspondant. Cela permet au jury de voir à la fois la compréhension Data Science et l'industrialisation MLOps.
