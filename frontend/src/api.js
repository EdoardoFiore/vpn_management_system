import axios from 'axios';

// L'URL di base della tua API. Durante il deploy, Nginx reindirizzerà /api al backend.
const API_BASE_URL = '/api'; 

// Leggi la chiave API dalle variabili d'ambiente di React
const API_KEY = process.env.REACT_APP_API_KEY;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  }
});

// Funzione per scaricare file di testo (come i .ovpn)
export const downloadFile = (blob, fileName) => {
  const url = window.URL.createObjectURL(new Blob([blob]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
};

export default apiClient;
