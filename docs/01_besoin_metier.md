# C5.1.1 — Analyse du besoin et faisabilité

## Commanditaire fictif

**INDUSTRIA SAS** exploite une flotte d'équipements tournants. Les arrêts non planifiés entraînent indisponibilité, interventions d'urgence et perturbation de production.

## Problématique

Le commanditaire souhaite passer d'une maintenance principalement corrective à une maintenance mieux priorisée. Le système doit répondre à la question :

> À partir des informations disponibles au cycle courant, quelle est la probabilité qu'un moteur atteigne sa défaillance dans les 30 prochains cycles ?

## Utilisateurs

- responsable maintenance : priorisation des inspections ;
- technicien : compréhension du niveau de risque ;
- responsable Data/ML : surveillance du modèle ;
- exploitant IT : disponibilité de l'API.

## Objectifs mesurables

- recall minimal cible : 0,85 sur la validation ;
- PR-AUC minimale cible : 0,70 ;
- priorité aux faux négatifs, supposés beaucoup plus coûteux ;
- API reproductible et conteneurisée ;
- traçabilité du dataset, des features, du modèle et du seuil ;
- monitoring des dérives et collecte de vérité terrain différée.

## Contraintes

### Données

- séries de capteurs par moteur ;
- durée de vie variable ;
- cible déséquilibrée (~15 % de positifs sur le train complet) ;
- risque majeur de fuite si les cycles d'un même moteur sont répartis entre train et validation.

### Modélisation

- éviter le futur dans les features ;
- ne jamais fournir RUL/cible/identifiant au modèle ;
- distinguer fit modèle, calibration du seuil, sélection du champion et test externe.

### Production

- coût maîtrisé ;
- image Docker ;
- service HTTP ;
- CI/CD ;
- observabilité et rollback ;
- identité GCP de moindre privilège.

## Faisabilité

FD001 est adapté à une preuve de concept : 100 trajectoires run-to-failure d'entraînement et 100 trajectoires de test. Le volume est compatible avec pandas/scikit-learn et une infrastructure légère. La principale réserve est que les données sont simulées et représentent un contexte plus simple que la plupart des environnements industriels réels.

## Décision

Projet **faisable** comme mise en situation Data Science/MLOps. Toute généralisation industrielle réelle exigerait une validation sur données terrain et une redéfinition des coûts métier et du seuil de 30 cycles.
