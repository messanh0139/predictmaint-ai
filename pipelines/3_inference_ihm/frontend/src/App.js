import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import MetricsBar from './components/MetricsBar';
import PredictionTab from './components/PredictionTab';
import PerformanceTab from './components/PerformanceTab';
import RetrainTab from './components/RetrainTab';
import { checkHealth } from './services/api';
import { DATA_PATH, METADATA_PATH, METRICS_PATH } from './config';
import './styles/App.css';

const App = () => {
  const [activeTab, setActiveTab] = useState('prediction');
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [metadata, setMetadata] = useState({});
  const [testMetrics, setTestMetrics] = useState({});
  const [demoData, setDemoData] = useState([]);

  // Colonnes du dataset
  const BASE_COLUMNS = [
    'engine_id', 'cycle', 'setting_1', 'setting_2', 'setting_3',
    ...Array.from({ length: 21 }, (_, i) => `sensor_${i + 1}`)
  ];

  useEffect(() => {
    // Vérifier la santé de l'API
    const fetchHealth = async () => {
      const { data, error } = await checkHealth();
      if (error) {
        setHealthError(error);
      } else {
        setHealthStatus(data);
      }
    };

    // Charger les métadonnées du modèle
    const fetchMetadata = async () => {
      try {
        const response = await axios.get(METADATA_PATH);
        console.log('Métadonnées chargées:', response.data);
        setMetadata(response.data || {});
      } catch (error) {
        console.error('Erreur chargement métadonnées:', error.message);
      }
    };

    // Charger les métriques de test
    const fetchTestMetrics = async () => {
      try {
        const response = await axios.get(METRICS_PATH);
        console.log('Métriques de test chargées:', response.data);
        setTestMetrics(response.data || {});
      } catch (error) {
        console.error('Erreur chargement métriques de test:', error.message);
      }
    };

    // Charger les données de démonstration
    const fetchDemoData = async () => {
      try {
        const response = await axios.get(DATA_PATH);
        const lines = response.data.trim().split('\n');
        const parsedData = lines.map(line => {
          const values = line.trim().split(/\s+/).map(Number);
          const row = {};
          BASE_COLUMNS.forEach((col, idx) => {
            row[col] = values[idx];
          });
          return row;
        });
        console.log(`Données de démo chargées: ${parsedData.length} lignes`);
        setDemoData(parsedData);
      } catch (error) {
        console.error('Erreur chargement données de démo:', error.message);
      }
    };

    fetchHealth();
    fetchMetadata();
    fetchTestMetrics();
    fetchDemoData();
  }, []);

  const tabs = [
    { id: 'prediction', label: 'Démonstration prédictive' },
    { id: 'performance', label: 'Performance' },
    { id: 'retrain', label: 'Réentraînement automatique' }
  ];

  return (
    <div className="app">
      <Sidebar healthStatus={healthStatus} healthError={healthError} />

      <div className="main-content">
        <Header />

        <MetricsBar metadata={metadata} testMetrics={testMetrics} />

        <div className="tabs">
          <div className="tab-buttons">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="tab-content">
            {activeTab === 'prediction' && (
              <PredictionTab demoData={demoData} healthError={healthError} />
            )}
            {activeTab === 'performance' && (
              <PerformanceTab testMetrics={testMetrics} />
            )}
            {activeTab === 'retrain' && (
              <RetrainTab demoData={demoData} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
