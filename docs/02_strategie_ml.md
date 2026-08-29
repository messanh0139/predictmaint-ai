# Stratégie de résolution du problème

## Formulation

Le besoin est traduit en classification binaire :

`P(RUL <= 30 | informations disponibles jusqu'au cycle t)`.

La cible vaut 1 lorsqu'il reste au plus 30 cycles avant la fin de la trajectoire.

## Fonction d'objectif métier

Une erreur n'a pas le même coût selon sa nature :

- faux négatif : coût fictif 10 000 ;
- faux positif : coût fictif 500.

Le seuil de décision est donc choisi pour minimiser le coût sous contrainte de recall minimal, et non fixé automatiquement à 0,5.

## Protocole expérimental

1. calcul de la cible ;
2. split par moteur en TRAIN / CALIBRATION / VALIDATION ;
3. feature engineering causal séparé ;
4. sélection de variables sur TRAIN seulement ;
5. entraînement de Logistic Regression, Random Forest et XGBoost ;
6. choix du seuil sur CALIBRATION ;
7. comparaison des modèles sur VALIDATION ;
8. optimisation XGBoost avec Optuna et validation croisée groupée uniquement sur TRAIN ;
9. champion/challenger : promotion seulement si les guardrails et le score métier sont meilleurs ;
10. test externe après verrouillage.

## Pourquoi plusieurs modèles

- Logistic Regression : baseline interprétable et peu coûteuse ;
- Random Forest : interactions non linéaires, robuste sur features tabulaires ;
- XGBoost : candidat performant et optimisable.

Le projet ne suppose pas qu'un modèle plus complexe est automatiquement meilleur.

## Métriques

Principales : recall, PR-AUC, F1, coût métier.

Complémentaires : precision, specificity, balanced accuracy, MCC, ROC-AUC, Brier score.

## Gestion du déséquilibre

- `class_weight="balanced"` / `balanced_subsample` ;
- `scale_pos_weight` pour XGBoost ;
- métriques adaptées ;
- seuil calibré métier.
