import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { predictFailure, submitFeedback } from '../services/api';

const PredictionTab = ({ demoData, healthError }) => {
  const [selectedEngine, setSelectedEngine] = useState(null);
  const [selectedCycle, setSelectedCycle] = useState(1);
  const [engines, setEngines] = useState([]);
  const [engineData, setEngineData] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackData, setFeedbackData] = useState({
    actualFailure: 0,
    actualRul: 30
  });

  useEffect(() => {
    if (demoData && demoData.length > 0) {
      const uniqueEngines = [...new Set(demoData.map(row => row.engine_id))].sort((a, b) => a - b);
      setEngines(uniqueEngines);
      if (uniqueEngines.length > 0 && !selectedEngine) {
        setSelectedEngine(uniqueEngines[0]);
      }
    }
  }, [demoData, selectedEngine]);

  useEffect(() => {
    if (selectedEngine && demoData) {
      const data = demoData.filter(row => row.engine_id === selectedEngine);
      setEngineData(data);
      if (data.length > 0) {
        setSelectedCycle(Math.max(...data.map(row => row.cycle)));
      }
    }
  }, [selectedEngine, demoData]);

  const handlePredict = async () => {
    if (!selectedEngine) return;

    setLoading(true);
    setError(null);

    const history = engineData
      .filter(row => row.cycle <= selectedCycle)
      .map(row => {
        const { engine_id, ...rest } = row;
        return rest;
      });

    const payload = {
      engine_id: selectedEngine,
      history: history
    };

    const { data, error: apiError } = await predictFailure(payload);

    if (apiError) {
      setError(apiError);
    } else {
      setPrediction(data);
    }

    setLoading(false);
  };

  const handleFeedback = async () => {
    if (!prediction) return;

    const payload = {
      prediction_id: prediction.prediction_id,
      actual_failure_within_30_cycles: feedbackData.actualFailure,
      actual_rul: feedbackData.actualRul
    };

    const { data, error: apiError } = await submitFeedback(payload);

    if (apiError) {
      setError(apiError);
    } else {
      alert('Feedback enregistré pour le monitoring continu.');
      setShowFeedback(false);
    }
  };

  if (healthError) {
    return (
      <div className="alert alert-error">
        Impossible de joindre l'API : {healthError}
      </div>
    );
  }

  if (!demoData || demoData.length === 0) {
    return <div className="alert alert-error">Jeu de démonstration absent</div>;
  }

  const historyData = engineData
    .filter(row => row.cycle <= selectedCycle)
    .map(row => ({
      cycle: row.cycle,
      sensor_2: row.sensor_2,
      sensor_4: row.sensor_4,
      sensor_7: row.sensor_7,
      sensor_11: row.sensor_11,
      sensor_15: row.sensor_15
    }));

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="form-group">
          <label className="form-label">Moteur</label>
          <select
            className="form-select"
            value={selectedEngine || ''}
            onChange={(e) => setSelectedEngine(Number(e.target.value))}
          >
            {engines.map(engine => (
              <option key={engine} value={engine}>
                Moteur {engine}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">
            Dernier cycle observé (max: {engineData.length > 0 ? Math.max(...engineData.map(r => r.cycle)) : 0})
          </label>
          <input
            type="range"
            className="form-input"
            min="1"
            max={engineData.length > 0 ? Math.max(...engineData.map(r => r.cycle)) : 1}
            value={selectedCycle}
            onChange={(e) => setSelectedCycle(Number(e.target.value))}
            style={{ cursor: 'pointer' }}
          />
          <div style={{ color: '#a9c8d8', marginTop: '0.5rem' }}>Cycle: {selectedCycle}</div>
        </div>
      </div>

      {historyData.length > 0 && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={historyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e526c" />
              <XAxis dataKey="cycle" stroke="#a9c8d8" />
              <YAxis stroke="#a9c8d8" />
              <Tooltip
                contentStyle={{ background: '#081521', border: '1px solid #1e526c', borderRadius: '8px' }}
                labelStyle={{ color: '#f4fbff' }}
              />
              <Legend />
              <Line type="monotone" dataKey="sensor_2" stroke="#35b88b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="sensor_4" stroke="#5ba3d0" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="sensor_7" stroke="#e35d6a" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="sensor_11" stroke="#f4a261" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="sensor_15" stroke="#a78bfa" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={handlePredict}
        disabled={loading || !selectedEngine}
        style={{ width: '100%', marginTop: '1rem' }}
      >
        {loading ? 'Analyse en cours...' : 'Analyser le risque'}
      </button>

      {error && (
        <div className="alert alert-error" style={{ marginTop: '1rem' }}>
          {error}
        </div>
      )}

      {prediction && (
        <div style={{ marginTop: '2rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '1.5rem' }}>
            <div className={`risk-badge ${prediction.risk === 'HIGH' ? 'high' : 'low'}`}>
              {prediction.risk === 'HIGH' ? 'INTERVENTION À PRIORISER' : 'SURVEILLANCE NORMALE'}
            </div>
            <div className="metric-card">
              <div className="metric-label">Probabilité</div>
              <div className="metric-value">{(prediction.failure_probability * 100).toFixed(2)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Seuil décisionnel</div>
              <div className="metric-value">{(prediction.threshold * 100).toFixed(1)}%</div>
            </div>
          </div>

          <div className="progress-bar" style={{ marginTop: '1rem' }}>
            <div
              className="progress-fill"
              style={{ width: `${Math.min(Math.max(prediction.failure_probability * 100, 0), 100)}%` }}
            />
          </div>

          <div style={{ color: '#a9c8d8', fontSize: '0.9rem', marginTop: '1rem' }}>
            Prédiction <code>{prediction.prediction_id}</code> · moteur {prediction.engine_id} ·
            cycle {prediction.last_cycle} · modèle {prediction.model_version || 'n/a'}
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button
              className="btn btn-secondary"
              onClick={() => setShowFeedback(!showFeedback)}
              style={{ marginBottom: '1rem' }}
            >
              {showFeedback ? 'Masquer' : 'Enregistrer le résultat terrain ultérieur'}
            </button>

            {showFeedback && (
              <div style={{ background: 'rgba(8, 21, 33, 0.6)', padding: '1.5rem', borderRadius: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Défaillance observée dans les 30 cycles ?</label>
                  <div style={{ display: 'flex', gap: '1rem' }}>
                    <button
                      className={`btn ${feedbackData.actualFailure === 0 ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setFeedbackData({ ...feedbackData, actualFailure: 0 })}
                    >
                      Non
                    </button>
                    <button
                      className={`btn ${feedbackData.actualFailure === 1 ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => setFeedbackData({ ...feedbackData, actualFailure: 1 })}
                    >
                      Oui
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">RUL réel (optionnel)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={feedbackData.actualRul}
                    onChange={(e) => setFeedbackData({ ...feedbackData, actualRul: Number(e.target.value) })}
                    min="0"
                  />
                </div>

                <button className="btn btn-primary" onClick={handleFeedback}>
                  Envoyer le feedback
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PredictionTab;
