import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const PerformanceTab = ({ testMetrics }) => {
  const formatPercent = (value) => {
    return (typeof value === 'number' && !isNaN(value))
      ? `${(value * 100).toFixed(1)}%`
      : '—';
  };

  const formatNumber = (value) => {
    return (typeof value === 'number' && !isNaN(value))
      ? value.toFixed(3)
      : '—';
  };

  const confusionData = [
    { name: 'Vrais négatifs', value: testMetrics?.tn || 0, fill: '#35b88b' },
    { name: 'Faux positifs', value: testMetrics?.fp || 0, fill: '#f4a261' },
    { name: 'Faux négatifs', value: testMetrics?.fn || 0, fill: '#e35d6a' },
    { name: 'Vrais positifs', value: testMetrics?.tp || 0, fill: '#5ba3d0' }
  ];

  return (
    <div>
      <h2 style={{ marginBottom: '1.5rem', color: '#f4fbff' }}>Résultats sur le holdout externe verrouillé</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="metric-card">
          <div className="metric-label">Recall</div>
          <div className="metric-value">{formatPercent(testMetrics?.recall)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Précision</div>
          <div className="metric-value">{formatPercent(testMetrics?.precision)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">ROC-AUC</div>
          <div className="metric-value">{formatNumber(testMetrics?.roc_auc)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">F1</div>
          <div className="metric-value">{formatNumber(testMetrics?.f1)}</div>
        </div>
      </div>

      <div className="chart-container">
        <h3 style={{ marginBottom: '1rem', color: '#a9c8d8' }}>Matrice de confusion</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={confusionData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#1e526c" />
            <XAxis type="number" stroke="#a9c8d8" />
            <YAxis dataKey="name" type="category" stroke="#a9c8d8" width={150} />
            <Tooltip
              contentStyle={{ background: '#081521', border: '1px solid #1e526c', borderRadius: '8px' }}
              labelStyle={{ color: '#f4fbff' }}
            />
            <Bar dataKey="value">
              {confusionData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="alert alert-info" style={{ marginTop: '2rem' }}>
        Le seuil a été appris sur un ensemble de calibration dédié. Le holdout externe verrouillé
        est réservé à l'évaluation finale et n'est pas utilisé pour ajuster le modèle.
      </div>
    </div>
  );
};

export default PerformanceTab;
