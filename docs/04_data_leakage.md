# Prévention du Data Leakage

## Risque principal

Le jeu de données contient plusieurs lignes successives pour un même moteur. Un split aléatoire par ligne peut placer les premiers cycles d'un moteur dans le train et ses cycles ultérieurs dans la validation. Le modèle bénéficie alors indirectement de la trajectoire du même équipement.

## Stratégie appliquée

Le projet fait d'abord un split **par moteur** :

- 70 moteurs TRAIN ;
- 15 moteurs CALIBRATION ;
- 15 moteurs VALIDATION ;
- 100 moteurs du `test_FD001` conservés comme holdout externe.

Les trois partitions de développement sont construites **avant** le feature engineering.

## Rôle de chaque partition

- TRAIN : fit feature selection, imputation/scaling et modèles.
- CALIBRATION : choix du seuil de classification selon coût métier et recall minimal.
- VALIDATION : comparaison et promotion des modèles.
- TEST EXTERNE : preuve finale ; jamais dans le retraining automatique.

Cette séparation évite de choisir les hyperparamètres, le seuil et le champion sur la même information.

## Causalité temporelle

Les features utilisent uniquement `t` et le passé du même moteur :

- `lag_1`, `lag_3` ;
- `diff_1` ;
- rolling mean/std/min/max/range sur fenêtres trailing ;
- EWM causale.

Sont interdits : `shift(-1)`, rolling centré, agrégation utilisant des cycles futurs.

## Variables interdites

`RUL`, la cible, `engine_id` et toute colonne servant à reconstruire la vérité terrain sont exclues de `X`.

## Contrôles automatiques

- assertions d'absence d'overlap de moteurs ;
- test de mutation du futur : modifier un cycle futur ne doit pas modifier les features d'un cycle passé ;
- test d'isolation entre moteurs ;
- contrôle que les colonnes interdites ne sont jamais sélectionnées ;
- holdout externe absent du pipeline `retrain.py`.

## Fuite par analyse humaine / EDA

La fuite ne vient pas uniquement du code. Regarder les corrélations avec la cible sur VALIDATION ou TEST puis choisir manuellement les capteurs contaminerait aussi l'évaluation. Dans cette version, les analyses utilisant `RUL` ou la cible sont limitées à TRAIN. Le holdout externe n'est ouvert qu'au notebook 05 / à `src.models.evaluate`.

## Holdout réellement fermé

Le pipeline standard `src.data.prepare` ne charge pas `RUL_FD001.txt` et ne génère pas de `test_features.csv`. Le couple `test_FD001.txt + RUL_FD001.txt` est ouvert uniquement par `src.models.evaluate`, après finalisation du modèle. Cette règle réduit le risque d'utiliser involontairement le holdout comme jeu de validation secondaire.
