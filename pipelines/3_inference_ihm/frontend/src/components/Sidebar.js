import React from 'react';

const Sidebar = ({ healthStatus, healthError }) => {
  const PROMETHEUS_URL = process.env.REACT_APP_PROMETHEUS_URL || 'http://localhost:9090';
  const GRAFANA_URL = process.env.REACT_APP_GRAFANA_URL || 'http://localhost:3000';
  const MLFLOW_URL = process.env.REACT_APP_MLFLOW_URL || 'http://localhost:5000';
  const API_DOCS_URL = process.env.REACT_APP_API_DOCS_URL || 'http://localhost:8000/docs';

  return (
    <div className="sidebar">
      <h1>PredictMaint</h1>

      <div className={`sidebar-status ${healthError ? 'error' : 'success'}`}>
        {healthError ? 'API indisponible' : 'API et modèle opérationnels'}
      </div>

      <div className="sidebar-divider" />

      <h3>Écosystème MLOps</h3>
      <div className="service-links">
        <a className="service-link" href={PROMETHEUS_URL} target="_blank" rel="noopener noreferrer">
          Prometheus ↗
        </a>
        <a className="service-link" href={GRAFANA_URL} target="_blank" rel="noopener noreferrer">
          Grafana ↗
        </a>
        <a className="service-link" href={MLFLOW_URL} target="_blank" rel="noopener noreferrer">
          MLflow ↗
        </a>
        <a className="service-link" href={API_DOCS_URL} target="_blank" rel="noopener noreferrer">
          Documentation API ↗
        </a>
      </div>
    </div>
  );
};

export default Sidebar;
