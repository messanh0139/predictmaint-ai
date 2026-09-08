# Tableau de Bord React - Maintenance Prédictive

Interface utilisateur interactive développée en React pour la visualisation des prédictions de maintenance prédictive.

## Fonctionnalités

- **Démonstration prédictive** : Sélection de moteurs, visualisation de capteurs, analyse du risque
- **Performance** : Métriques du modèle et matrice de confusion
- **Réentraînement automatique** : Upload de nouvelles données et suivi du pipeline
- **Architecture** : Guide de présentation et schéma du système

## Technologies

- React 18
- Recharts (visualisations)
- Material-UI (composants)
- Axios (appels API)

## Installation

```bash
npm install
```

## Démarrage

### Développement

```bash
npm start
```

L'application sera disponible sur http://localhost:3000

### Production

```bash
npm run build
```

## Variables d'environnement

Créer un fichier **.env** à la racine :

```env
REACT_APP_API_URL=http://localhost:8001
REACT_APP_PROMETHEUS_URL=http://localhost:9090
REACT_APP_GRAFANA_URL=http://localhost:3001
REACT_APP_MLFLOW_URL=http://localhost:5001
REACT_APP_API_DOCS_URL=http://localhost:8001/docs
REACT_APP_DATA_PATH=/data/raw/test_FD001.txt
REACT_APP_METADATA_PATH=/models/model_metadata.json
REACT_APP_METRICS_PATH=/models/test_metrics.json
```

## Structure du projet

```
src/
├── App.js                  # Composant principal
├── index.js                # Point d'entrée
├── components/             # Composants React
│   ├── Sidebar.js
│   ├── Header.js
│   ├── MetricsBar.js
│   ├── PredictionTab.js
│   ├── PerformanceTab.js
│   ├── RetrainTab.js
│   └── ArchitectureTab.js
├── services/               # Services API
│   └── api.js
└── styles/                 # Feuilles de style
    └── App.css
```

## Docker

L'application est containerisée et s'intègre dans l'écosystème MLOps complet via Docker Compose.

Voir **infrastructure/deployment/Dockerfile.dashboard** pour les détails du build.
