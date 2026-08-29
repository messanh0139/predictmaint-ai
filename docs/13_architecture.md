# Architecture technique

```mermaid
flowchart TD
    A[Jeu de données FD001] --> B[Validation schéma + SHA256]
    B --> C{Split par moteur avant features}
    C --> D[TRAIN]
    C --> E[CALIBRATION]
    C --> F[VALIDATION]
    A --> G[TEST EXTERNE]

    D --> H[Feature Engineering causal]
    E --> I[Feature Engineering causal]
    F --> J[Feature Engineering causal]
    G --> K[Feature Engineering causal]

    H --> L[Feature Selection TRAIN only]
    L --> M[Logistic / RF / XGBoost]
    M --> N[Seuil sur CALIBRATION]
    N --> O[Comparaison sur VALIDATION]
    O --> P[Champion]
    M --> Q[Optuna + Group CV TRAIN]
    Q --> R[Challenger]
    R --> O

    P --> S[Quality Gate]
    S --> T[Local Registry + MLflow]
    T --> U[FastAPI + Docker]
    U --> V[Artifact Registry]
    V --> W[Cloud Run]

    W --> X[Cloud Storage telemetry]
    X --> Y[Predictions + Feedback]
    Y --> Z[Drift + Performance Monitoring]
    Z --> AA[Cloud Run Retraining Job]
    AA --> AB[New labelled production features]
    AB --> D
    AA --> AC[GCS Model Artifact Store]

    P --> G
    G --> AD[Évaluation externe finale seulement]
```

## Séparation des responsabilités

- **Data pipeline** : validation, labellisation, split, features.
- **ML pipeline** : sélection, entraînement, tuning, calibration, promotion.
- **Serving** : API stateless, modèle versionné, contrat Pydantic.
- **Observabilité** : métriques service, drift, performance différée.
- **Lifecycle** : feedback -> dataset additionnel -> retraining -> registry.
- **Cloud** : identité deployer/runtime/trainer/scheduler séparée.
