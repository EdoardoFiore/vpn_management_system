import React, { useState, useEffect, useCallback } from 'react';
import { Container, Navbar, Spinner, Alert } from 'react-bootstrap';
import apiClient, { downloadFile } from './api';
import ClientTable from './components/ClientTable';
import AddClientForm from './components/AddClientForm';

function App() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const fetchClients = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/clients');
      setClients(response.data);
      setError(null);
    } catch (err) {
      setError('Impossibile caricare i client. Il backend è in esecuzione?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const handleAddClient = async (clientName) => {
    try {
      setError(null);
      setSuccess(null);
      const response = await apiClient.post('/clients', { client_name: clientName });
      downloadFile(response.data, `${clientName}.ovpn`);
      setSuccess(`Client '${clientName}' creato con successo e file di configurazione scaricato.`);
      fetchClients(); // Refresh the list
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Errore nella creazione del client.';
      setError(errorMessage);
      console.error(err);
    }
  };

  const handleRevokeClient = async (clientName) => {
    if (window.confirm(`Sei sicuro di voler revocare il client '${clientName}'? L'azione è irreversibile.`)) {
      try {
        setError(null);
        setSuccess(null);
        await apiClient.delete(`/clients/${clientName}`);
        setSuccess(`Client '${clientName}' revocato con successo.`);
        fetchClients(); // Refresh the list
      } catch (err) {
        const errorMessage = err.response?.data?.detail || 'Errore nella revoca del client.';
        setError(errorMessage);
        console.error(err);
      }
    }
  };

  return (
    <>
      <Navbar bg="dark" variant="dark">
        <Container>
          <Navbar.Brand href="#home">VPN Management Dashboard</Navbar.Brand>
        </Container>
      </Navbar>
      <Container className="mt-4">
        {error && <Alert variant="danger" onClose={() => setError(null)} dismissible>{error}</Alert>}
        {success && <Alert variant="success" onClose={() => setSuccess(null)} dismissible>{success}</Alert>}
        
        <AddClientForm onAddClient={handleAddClient} />
        
        <hr className="my-4" />

        {loading ? (
          <div className="text-center">
            <Spinner animation="border" role="status">
              <span className="visually-hidden">Caricamento...</span>
            </Spinner>
          </div>
        ) : (
          <ClientTable clients={clients} onRevokeClient={handleRevokeClient} />
        )}
      </Container>
    </>
  );
}

export default App;
