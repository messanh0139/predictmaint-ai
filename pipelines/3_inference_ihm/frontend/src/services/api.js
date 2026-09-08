import axios from 'axios';
import { API_URL, API_AUDIENCE } from '../config';

// Configuration axios avec timeout
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercepteur pour ajouter le token d'authentification si nécessaire
apiClient.interceptors.request.use(
  async (config) => {
    if (API_AUDIENCE) {
      // TODO: Implémenter récupération token Google Cloud Run si nécessaire
      // const token = await fetchIdToken(API_AUDIENCE);
      // config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// API Health Check
export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/ready');
    return { data: response.data, error: null };
  } catch (error) {
    return { data: null, error: error.message };
  }
};

// API Prediction
export const predictFailure = async (payload) => {
  try {
    const response = await apiClient.post('/predict', payload);
    return { data: response.data, error: null };
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message;
    return { data: null, error: errorMsg };
  }
};

// API Feedback
export const submitFeedback = async (payload) => {
  try {
    const response = await apiClient.post('/feedback', payload);
    return { data: response.data, error: null };
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message;
    return { data: null, error: errorMsg };
  }
};

// API Upload pour réentraînement
export const uploadRetrainData = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/retrain/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000,
    });
    return { data: response.data, error: null };
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message;
    return { data: null, error: errorMsg };
  }
};

// API Statut réentraînement
export const getRetrainStatus = async () => {
  try {
    const response = await apiClient.get('/retrain/status');
    return { data: response.data, error: null };
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message;
    return { data: null, error: errorMsg };
  }
};

// API État des conteneurs (up/down)
export const getServicesStatus = async () => {
  try {
    const response = await apiClient.get('/services/status');
    return { data: response.data, error: null };
  } catch (error) {
    const errorMsg = error.response?.data?.detail || error.message;
    return { data: null, error: errorMsg };
  }
};

export default apiClient;
