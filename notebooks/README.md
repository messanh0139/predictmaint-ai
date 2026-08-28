# Parcours des notebooks

Les notebooks sont volontairement pédagogiques : ils montrent les opérations importantes de manière explicite, puis pointent vers le code industrialisé dans `src/`.

1. `01_eda.ipynb` — chargement manuel avec `pd.read_csv`, qualité, cible, split et EDA TRAIN-only.
2. `02_feature_engineering.ipynb` — split avant transformation, features causales et test de causalité.
3. `03_feature_selection.ipynb` — cinq méthodes de sélection, fit sur TRAIN uniquement.
4. `04_model_training.ipynb` — baseline explicite, calibration du seuil et comparaison des modèles.
5. `05_model_evaluation.ipynb` — optimisation/promotion puis ouverture contrôlée du holdout NASA.
6. `06_monitoring.ipynb` — PSI, drift, performance différée et boucle MLOps.

## Contrat méthodologique commun

- La séparation TRAIN/CALIBRATION/VALIDATION est faite par moteur avant toute transformation supervisée.
- Les features sont causales et calculées séparément dans chaque partition.
- La sélection des variables, l'imputation, la standardisation et le modèle sont ajustés sur TRAIN uniquement.
- CALIBRATION sert exclusivement à choisir le seuil de décision.
- VALIDATION sert à comparer et promouvoir les candidats ; le holdout NASA n'est ouvert qu'ensuite dans le notebook 05.

Construire un objet `Pipeline` avant de charger les partitions n'est pas une fuite : aucun paramètre n'est appris avant `fit(X_train, y_train)`. Les transformations appliquées ensuite à CALIBRATION, VALIDATION et au holdout réutilisent les paramètres appris sur TRAIN.

## Hypothèses de coût du notebook 04

Le choix du seuil utilise un scénario pédagogique configurable : faux négatif = 10 000 unités, faux positif = 500 unités et rappel minimal = 85 % par défaut. Ces nombres ne sont ni des prix observés ni une devise. Ils doivent être validés par le commanditaire et remplacés via `FALSE_NEGATIVE_COST`, `FALSE_POSITIVE_COST` et `MIN_RECALL`.

Dans la démonstration, les erreurs et le coût sont comptés par ligne/cycle moteur. Un déploiement réel doit définir comment regrouper les alertes successives et valoriser un événement par moteur avant d'interpréter ce score comme un coût financier.

## Pourquoi garder `src/` si les notebooks montrent le code ?

Le notebook sert à **comprendre, justifier et présenter**. Le dossier `src/` sert à **réutiliser, tester, automatiser et déployer** exactement les mêmes règles sans duplication. C'est la séparation attendue dans un projet Data Science/MLOps professionnel.
