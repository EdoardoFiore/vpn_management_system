import React, { useState } from 'react';
import { Form, Button, Row, Col, Card } from 'react-bootstrap';

function AddClientForm({ onAddClient }) {
  const [clientName, setClientName] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!clientName.trim()) {
      alert('Il nome del client non può essere vuoto.');
      return;
    }
    if (!/^[a-zA-Z0-9]+$/.test(clientName)) {
        alert('Il nome del client può contenere solo lettere e numeri.');
        return;
    }

    setIsLoading(true);
    await onAddClient(clientName);
    setIsLoading(false);
    setClientName(''); // Reset input field
  };

  return (
    <Card>
      <Card.Body>
        <Card.Title>Crea Nuovo Client</Card.Title>
        <Form onSubmit={handleSubmit}>
          <Row className="align-items-end">
            <Col xs={12} md={8} lg={9}>
              <Form.Group controlId="formClientName">
                <Form.Label>Nome del nuovo client (solo lettere e numeri)</Form.Label>
                <Form.Control
                  type="text"
                  placeholder="Es: laptop_mario_rossi"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </Form.Group>
            </Col>
            <Col xs={12} md={4} lg={3} className="mt-3 mt-md-0">
              <Button variant="primary" type="submit" className="w-100" disabled={isLoading}>
                {isLoading ? 'Creazione...' : 'Crea e Scarica'}
              </Button>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );
}

export default AddClientForm;
