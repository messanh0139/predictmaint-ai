import React from 'react';
import { PROMETHEUS_URL, GRAFANA_URL, MLFLOW_URL, API_DOCS_URL } from '../config';

const Sidebar = ({ healthStatus, healthError }) => {

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
