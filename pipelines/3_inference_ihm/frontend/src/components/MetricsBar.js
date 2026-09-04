import React from 'react';

const MetricsBar = ({ metadata, testMetrics }) => {
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

  return (
    <div className="metrics-bar">
      <div className="metric-card">
        <div className="metric-label">Modèle champion</div>
        <div className="metric-value">{metadata?.model_name || '—'}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Recall test</div>
        <div className="metric-value">{formatPercent(testMetrics?.recall)}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">PR-AUC test</div>
        <div className="metric-value">{formatNumber(testMetrics?.pr_auc)}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Fenêtre d'alerte</div>
        <div className="metric-value">{metadata?.failure_window || 30} cycles</div>
      </div>
    </div>
  );
};

export default MetricsBar;
