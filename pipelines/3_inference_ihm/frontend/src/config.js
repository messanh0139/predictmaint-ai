// Fonction utilitaire pour lire les variables d'environnement
// au runtime depuis window.RUNTIME_CONFIG ou depuis process.env en fallback
const getConfig = (key, defaultValue = '') => {
  // En production, les variables sont dans window.RUNTIME_CONFIG (injectées au démarrage du conteneur)
  if (window.RUNTIME_CONFIG && window.RUNTIME_CONFIG[key]) {
    return window.RUNTIME_CONFIG[key];
  }
  // En développement, les variables sont dans process.env (compilées au build)
  return process.env[key] || defaultValue;
};

export const API_URL = getConfig('REACT_APP_API_URL', 'http://localhost:8000');
export const API_AUDIENCE = getConfig('REACT_APP_API_AUDIENCE', '');
export const PROMETHEUS_URL = getConfig('REACT_APP_PROMETHEUS_URL', '');
export const GRAFANA_URL = getConfig('REACT_APP_GRAFANA_URL', 'http://localhost:3000');
export const MLFLOW_URL = getConfig('REACT_APP_MLFLOW_URL', 'http://localhost:5000');
export const API_DOCS_URL = getConfig('REACT_APP_API_DOCS_URL', 'http://localhost:8000/docs');
export const DATA_PATH = getConfig('REACT_APP_DATA_PATH', '/data/raw/test_FD001.txt');
export const METADATA_PATH = getConfig('REACT_APP_METADATA_PATH', '/models/model_metadata.json');
export const METRICS_PATH = getConfig('REACT_APP_METRICS_PATH', '/models/test_metrics.json');
