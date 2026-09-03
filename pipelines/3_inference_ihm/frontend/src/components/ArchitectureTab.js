import React from 'react';

const ArchitectureTab = () => {
  return (
    <div>
      <h2 style={{ marginBottom: '1.5rem', color: '#f4fbff' }}>Scénario conseillé pour la soutenance</h2>

      <div style={{ background: 'rgba(8, 21, 33, 0.6)', padding: '2rem', borderRadius: '12px', marginBottom: '2rem' }}>
        <ol style={{ color: '#a9c8d8', lineHeight: '2', paddingLeft: '1.5rem' }}>
          <li>
            <strong style={{ color: '#f4fbff' }}>React Dashboard</strong> — sélectionner un moteur, faire varier le cycle et produire une alerte.
          </li>
          <li>
            <strong style={{ color: '#f4fbff' }}>FastAPI</strong> — montrer le contrat <code>/predict</code> et la réponse traçable.
          </li>
          <li>
            <strong style={{ color: '#f4fbff' }}>Grafana</strong> — vérifier le volume, la latence et l'état du modèle.
          </li>
          <li>
            <strong style={{ color: '#f4fbff' }}>MLflow</strong> — comparer les expériences et retrouver les artefacts versionnés.
          </li>
          <li>
            <strong style={{ color: '#f4fbff' }}>Boucle de feedback</strong> — rattacher la vérité terrain puis déclencher le réentraînement.
          </li>
        </ol>
      </div>

      <h3 style={{ marginBottom: '1rem', color: '#f4fbff' }}>Schéma d'architecture</h3>
      <div style={{ background: 'rgba(8, 21, 33, 0.8)', padding: '2rem', borderRadius: '12px', fontFamily: 'monospace' }}>
        <pre style={{ color: '#a9c8d8', margin: 0, fontSize: '0.95rem', lineHeight: '1.8' }}>
{`Capteurs → React Dashboard → FastAPI → Modèle
                                  ├→ Prometheus → Grafana
Feedback → Monitoring → Réentraînement → MLflow`}
        </pre>
      </div>

      <div className="alert alert-info" style={{ marginTop: '2rem' }}>
        <strong>Architecture MLOps complète :</strong>
        <ul style={{ marginTop: '1rem', paddingLeft: '1.5rem', lineHeight: '1.8' }}>
          <li>Pipeline 1 (ETL) : Extraction → MongoDB → Transformation → PostgreSQL</li>
          <li>Pipeline 2 (MLOps) : Training → Experimentation (3+ modèles) → Optimisation → MLflow → GCP</li>
          <li>Pipeline 3 (Inférence) : FastAPI + React + Monitoring</li>
          <li>Orchestration : Apache Airflow (DAGs automatisés)</li>
          <li>Monitoring : cAdvisor + Prometheus + Grafana</li>
        </ul>
      </div>
    </div>
  );
};

export default ArchitectureTab;
