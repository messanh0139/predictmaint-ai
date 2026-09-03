import React, { useState, useEffect } from 'react';
import { uploadRetrainData, getRetrainStatus } from '../services/api';

const RetrainTab = ({ demoData }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [retrainTriggered, setRetrainTriggered] = useState(false);
  const [retrainStatus, setRetrainStatus] = useState(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    let interval;
    if (retrainTriggered && polling) {
      interval = setInterval(async () => {
        const { data, error } = await getRetrainStatus();
        if (error) {
          setUploadError(error);
          setPolling(false);
        } else if (data) {
          setRetrainStatus(data);
          if (data.state !== 'running') {
            setPolling(false);
            setRetrainTriggered(false);
          }
        }
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [retrainTriggered, polling]);

  const generateSampleCSV = () => {
    if (!demoData || demoData.length === 0) return null;

    const engines = [...new Set(demoData.map(row => row.engine_id))].slice(0, 3);
    const sampleRows = demoData.filter(row => engines.includes(row.engine_id));

    const labels = {};
    engines.forEach((engine, idx) => {
      labels[engine] = idx % 2 === 0 ? 1 : 0;
    });

    const csvRows = sampleRows.map(row => {
      return {
        ...row,
        actual_failure_within_30_cycles: labels[row.engine_id]
      };
    });

    const headers = Object.keys(csvRows[0]);
    const csvContent = [
      headers.join(','),
      ...csvRows.map(row => headers.map(header => row[header]).join(','))
    ].join('\n');

    return csvContent;
  };

  const handleDownloadSample = () => {
    const csv = generateSampleCSV();
    if (!csv) return;

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'nouvelles_donnees_exemple.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const { data, error } = await uploadRetrainData(file);

    if (error) {
      setUploadError(error);
    } else {
      setUploadSuccess(`${data.rows_added || 0} moteur(s) intégré(s). Réentraînement déclenché automatiquement.`);
      setRetrainTriggered(true);
      setPolling(true);
    }

    setUploading(false);
    event.target.value = '';
  };

  return (
    <div>
      <h2 style={{ marginBottom: '1.5rem', color: '#f4fbff' }}>Déclenchement automatique du réentraînement</h2>

      <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
        Téléverser un fichier CSV de nouvelles données de production <strong>déclenche
        immédiatement et automatiquement</strong> le pipeline complet
        (préparation → sélection de variables → entraînement → quality gate →
        enregistrement), sans action supplémentaire.
      </div>

      <div style={{ color: '#a9c8d8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
        Colonnes attendues : <code>engine_id</code>, <code>cycle</code>, <code>setting_1..3</code>, <code>sensor_1..21</code>,
        <code>actual_failure_within_30_cycles</code> (0 ou 1, un label par moteur).
      </div>

      {demoData && demoData.length > 0 && (
        <button
          className="btn btn-secondary"
          onClick={handleDownloadSample}
          style={{ marginBottom: '1.5rem' }}
        >
          Télécharger un exemple de fichier
        </button>
      )}

      <div className="form-group">
        <label className="form-label">Nouvelles données de production (CSV)</label>
        <input
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          disabled={uploading}
          className="form-input"
          style={{ padding: '0.8rem', cursor: 'pointer' }}
        />
      </div>

      {uploading && (
        <div className="alert alert-info">
          Envoi du fichier et déclenchement automatique du pipeline...
        </div>
      )}

      {uploadError && (
        <div className="alert alert-error">
          Échec du déclenchement : {uploadError}
        </div>
      )}

      {uploadSuccess && (
        <div className="alert alert-success">
          {uploadSuccess}
        </div>
      )}

      {retrainStatus && (
        <div style={{ marginTop: '2rem' }}>
          {retrainStatus.state === 'running' && (
            <div className="alert alert-info">
              <div className="spinner" />
              Réentraînement en cours (démarré à {retrainStatus.started_at})...
              <br />
              Cette page se met à jour automatiquement.
            </div>
          )}

          {retrainStatus.state === 'completed' && (
            <div className="alert alert-success">
              Réentraînement terminé. Nouveau modèle champion : <code>{retrainStatus.model_version}</code>.
            </div>
          )}

          {retrainStatus.state === 'failed' && (
            <div className="alert alert-error">
              Échec du réentraînement : {retrainStatus.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RetrainTab;
