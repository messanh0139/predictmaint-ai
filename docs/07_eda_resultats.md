# Résultats EDA — NASA C-MAPSS FD001

## Structure et qualité

- Train : 20 631 observations, 100 moteurs, 26 colonnes brutes.
- Test : 13 096 observations, 100 moteurs, 26 colonnes brutes.
- `RUL_FD001.txt` : 100 lignes attendues ; les valeurs de vérité terrain restent fermées pendant l'EDA et ne sont ouvertes qu'à l'évaluation externe finale.
- Valeurs manquantes : 0.
- Doublons `(engine_id, cycle)` : 0.
- Cycles non monotones par moteur : 0.

## Durée des trajectoires train

- minimum : 128 cycles ;
- Q1 : 177 cycles ;
- médiane : 199 cycles ;
- moyenne : 206,31 cycles ;
- Q3 : 229,25 cycles ;
- maximum : 362 cycles.

## Cible métier

La cible est `failure_within_30_cycles = 1` si `RUL <= 30`.

Après le split par moteur, l'analyse supervisée est menée sur **TRAIN uniquement** (70 moteurs) :

- classe 0 : 12 237 lignes ;
- classe 1 : 2 170 lignes ;
- taux positif : 15,06 %.

L'accuracy seule serait donc trompeuse. Le projet privilégie recall, F1, PR-AUC, ROC-AUC et coût métier.

## Variables quasi constantes

Sur la partition TRAIN de développement, les colonnes suivantes ont une variance nulle :

`setting_3`, `sensor_1`, `sensor_5`, `sensor_10`, `sensor_16`, `sensor_18`, `sensor_19`.

Elles sont retirées automatiquement par la phase de sélection de variables.

## Signaux bruts les plus liés au RUL

Sur TRAIN uniquement, les corrélations absolues brutes les plus élevées avec le RUL concernent notamment `sensor_11`, `sensor_4`, `sensor_12`, `sensor_7`, `sensor_15`, `sensor_21`, `sensor_20`, `sensor_2`, `sensor_17` et `sensor_3`.

Cette observation guide l'exploration mais ne remplace pas la sélection data-driven réalisée uniquement sur le TRAIN.

## Point de vigilance

Les conditions de FD001 sont simples. Une extension FD004 est pertinente pour tester plusieurs conditions opérationnelles et plusieurs modes de défaillance après validation de la V1.
