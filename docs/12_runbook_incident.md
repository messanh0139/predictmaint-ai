# Runbook — incident modèle / API

## API indisponible

1. Vérifier `/live` puis `/ready`.
2. Consulter Cloud Run logs et la dernière révision.
3. Vérifier présence/compatibilité `model.joblib` + `model_metadata.json`.
4. Si régression liée à une nouvelle révision, rollback vers la révision précédente.
5. Documenter cause, durée, impact et action corrective.

## Drift détecté

1. Vérifier volume de données courant et qualité du lot.
2. Identifier les features avec PSI élevé.
3. Comparer conditions opérationnelles aux données de référence.
4. Ne pas réentraîner automatiquement si la vérité terrain est insuffisante.
5. Si ground truth suffisant, lancer retraining puis quality gate et champion/challenger.

## Performance dégradée

1. Vérifier nombre de prédictions labellisées.
2. Contrôler recall / PR-AUC / coût métier.
3. Rechercher changement de distribution ou problème de collecte.
4. Réentraîner seulement sur données validées et versionnées.
5. Promotion uniquement si validation verrouillée et guardrails passent.
