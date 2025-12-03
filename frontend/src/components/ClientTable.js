import React from 'react';
import { Table, Button, Badge, Alert, Card } from 'react-bootstrap';

function ClientTable({ clients, onRevokeClient }) {
  if (!clients || clients.length === 0) {
    return (
      <Alert variant="info" className="text-center">
        Nessun client VPN trovato. Creane uno per iniziare!
      </Alert>
    );
  }

  const formatConnectedSince = (isoString) => {
    if (!isoString) return 'N/D';
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <Card>
      <Card.Body>
        <Card.Title>Client VPN</Card.Title>
        <Table striped bordered hover responsive className="mt-3">
          <thead>
            <tr>
              <th>Nome Client</th>
              <th>Stato</th>
              <th>IP Virtuale</th>
              <th>IP Reale</th>
              <th>Connesso Dal</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.name}>
                <td>{client.name}</td>
                <td>
                  <Badge bg={client.status === 'connected' ? 'success' : 'secondary'}>
                    {client.status === 'connected' ? 'Connesso' : 'Disconnesso'}
                  </Badge>
                </td>
                <td>{client.virtual_ip || 'N/D'}</td>
                <td>{client.real_ip || 'N/D'}</td>
                <td>{formatConnectedSince(client.connected_since)}</td>
                <td>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => onRevokeClient(client.name)}
                    disabled={client.name === 'test-client'} // Prevent revoking the initial test client
                  >
                    Revoca
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card.Body>
    </Card>
  );
}

export default ClientTable;
