import React, { useEffect, useState } from 'react';
import { PROMETHEUS_URL, MLFLOW_URL, API_DOCS_URL } from '../config';
import { getServicesStatus } from '../services/api';

const STATUS_POLL_INTERVAL_MS = 15000;

const Sidebar = ({ healthStatus, healthError }) => {
  const [services, setServices] = useState([]);

  useEffect(() => {
    const fetchStatus = async () => {
      const { data } = await getServicesStatus();
      if (data?.services) {
        setServices(data.services);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, STATUS_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="sidebar">
      <h1>PredictMaint</h1>

      <div className={`sidebar-status ${healthError ? 'error' : 'success'}`}>
        {healthError ? 'API indisponible' : 'API et modèle opérationnels'}
      </div>

      <div className="sidebar-divider" />

      <h3>Écosystème MLOps</h3>
      <div className="service-links">
        {PROMETHEUS_URL && (
          <a className="service-link" href={PROMETHEUS_URL} target="_blank" rel="noopener noreferrer">
            Prometheus ↗
          </a>
        )}
        <a className="service-link" href={MLFLOW_URL} target="_blank" rel="noopener noreferrer">
          Tracking ↗
        </a>
        <a className="service-link" href={API_DOCS_URL} target="_blank" rel="noopener noreferrer">
          Documentation API ↗
        </a>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-divider" />
        <h3>État des conteneurs</h3>
        <div className="container-status">
          {services.length === 0 && (
            <div className="container-status-item">
              <span className="status-dot" />
              <span>Vérification…</span>
            </div>
          )}
          {services.map((service) => (
            <div className="container-status-item" key={service.name}>
              <span className={`status-dot ${service.up ? 'up' : 'down'}`} />
              <span>{service.name}</span>
              <span className="status-label">{service.up ? 'UP' : 'DOWN'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
