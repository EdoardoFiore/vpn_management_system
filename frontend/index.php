<?php
// index.php

// Non più necessario require_once 'api_client.php'; direttamente qui per logica POST
// Verrà usato solo per configurazione iniziale se necessario, ma ora le chiamate sono via JS a ajax_handler.php

?>

<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pannello di Gestione VPN</title>
    <!-- Tabler Core CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css" />
    <!-- Tabler Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css" />
    <style>
        body { min-width: 320px; }
    </style>
</head>
<body>
    <div class="page">
        <header class="navbar navbar-expand-md d-print-none">
            <div class="container-xl">
                <h1 class="navbar-brand navbar-brand-autodark d-none-navbar-horizontal pe-0 pe-md-3">
                    <a href=".">Pannello di Gestione VPN</a>
                </h1>
            </div>
        </header>

        <div class="page-wrapper">
            <div class="page-body">
                <div class="container-xl">

                    <div id="notification-container"></div>

                    <div class="card mb-4">
                        <div class="card-header">
                            <h3 class="card-title">Aggiungi Nuovo Client</h3>
                        </div>
                        <div class="card-body">
                            <form id="addClientForm" onsubmit="event.preventDefault(); createClient();">
                                <div class="row g-2">
                                    <div class="col">
                                        <input type="text" id="clientNameInput" class="form-control" placeholder="Es: laptop-mario-rossi" required>
                                    </div>
                                    <div class="col-auto">
                                        <button type="submit" class="btn btn-primary">
                                            <i class="ti ti-plus icon"></i> Crea Client
                                        </button>
                                    </div>
                                </div>
                                <div class="form-text">
                                    Usare solo lettere, numeri, trattini (-) e underscore (_).
                                </div>
                            </form>
                        </div>
                    </div>

                    <div class="card mb-4">
                        <div class="card-header">
                            <h3 class="card-title">Client Disponibili per Download</h3>
                            <div class="card-actions">
                                <button class="btn" onclick="fetchAndRenderClients()">
                                    <i class="ti ti-refresh icon"></i>
                                    Aggiorna
                                </button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-vcenter card-table table-striped">
                                <thead>
                                    <tr>
                                        <th>Client</th>
                                        <th class="w-1"></th>
                                    </tr>
                                </thead>
                                <tbody id="availableClientsTableBody">
                                    <!-- I client disponibili verranno iniettati qui da JavaScript -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Client Connessi</h3>
                            <div class="card-actions">
                                <button class="btn" onclick="fetchAndRenderClients()">
                                    <i class="ti ti-refresh icon"></i>
                                    Aggiorna
                                </button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-vcenter card-table table-striped">
                                <thead>
                                    <tr>
                                        <th>Client</th>
                                        <th>IP Virtuale</th>
                                        <th>IP Reale</th>
                                        <th>Connesso Dal</th>
                                        <th class="w-1"></th>
                                    </tr>
                                </thead>
                                <tbody id="connectedClientsTableBody">
                                    <!-- I client connessi verranno iniettati qui da JavaScript -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    </div>
    <!-- Tabler Core JS for features like alert dismissal -->
    <script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js"></script>
    <script>
        const API_AJAX_HANDLER = 'ajax_handler.php';

        function showNotification(type, message) {
            const container = document.getElementById('notification-container');
            const alertHtml = `
                <div class="alert alert-${type} alert-dismissible" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            container.innerHTML = alertHtml;
        }

        function formatDateTime(isoString) {
            if (!isoString) return 'N/D';
            try {
                const date = new Date(isoString);
                return date.toLocaleString('it-IT', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit', second: '2-digit'
                });
            } catch (e) {
                return 'N/D';
            }
        }

        async function fetchAndRenderClients() {
            showNotification('info', 'Caricamento client...');
            try {
                const response = await fetch(`${API_AJAX_HANDLER}?action=get_clients`);
                const result = await response.json();

                if (result.success) {
                    const clients = result.body;
                    const availableClientsTableBody = document.getElementById('availableClientsTableBody');
                    const connectedClientsTableBody = document.getElementById('connectedClientsTableBody');

                    availableClientsTableBody.innerHTML = '';
                    connectedClientsTableBody.innerHTML = '';

                    const connected = clients.filter(c => c.status === 'connected');
                    const disconnected = clients.filter(c => c.status !== 'connected'); // Tutti i non connessi sono disponibili (o revocabili)

                    if (disconnected.length === 0) {
                        availableClientsTableBody.innerHTML = `
                            <tr>
                                <td colspan="2" class="text-center text-muted">
                                    <i class="ti ti-server-off icon-lg my-3"></i>
                                    <p>Nessun client VPN disponibile per il download.</p>
                                </td>
                            </tr>
                        `;
                    } else {
                        disconnected.forEach(client => {
                            const row = `
                                <tr>
                                    <td>
                                        <span class="badge bg-secondary me-1"></span>
                                        ${client.name}
                                    </td>
                                    <td>
                                        <button class="btn btn-primary btn-sm me-1" onclick="downloadClient('${client.name}')" title="Scarica Configurazione">
                                            <i class="ti ti-download"></i>
                                        </button>
                                        <button class="btn btn-danger btn-sm" onclick="revokeClient('${client.name}')" title="Revoca Client">
                                            <i class="ti ti-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            `;
                            availableClientsTableBody.innerHTML += row;
                        });
                    }

                    if (connected.length === 0) {
                        connectedClientsTableBody.innerHTML = `
                            <tr>
                                <td colspan="5" class="text-center text-muted">
                                    <i class="ti ti-server-off icon-lg my-3"></i>
                                    <p>Nessun client VPN connesso.</p>
                                </td>
                            </tr>
                        `;
                    } else {
                        connected.forEach(client => {
                            const row = `
                                <tr>
                                    <td>
                                        <span class="badge bg-success me-1"></span>
                                        ${client.name}
                                    </td>
                                    <td class="text-muted">${client.virtual_ip || 'N/D'}</td>
                                    <td class="text-muted">${client.real_ip || 'N/D'}</td>
                                    <td class="text-muted">${formatDateTime(client.connected_since)}</td>
                                    <td>
                                        <button class="btn btn-danger btn-sm" onclick="revokeClient('${client.name}')" title="Revoca Client">
                                            <i class="ti ti-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            `;
                            connectedClientsTableBody.innerHTML += row;
                        });
                    }
                    showNotification('success', 'Client caricati con successo.');

                } else {
                    const errorMessage = result.body.detail || 'Errore sconosciuto durante il caricamento dei client.';
                    showNotification('danger', `Errore: ${errorMessage}`);
                }
            } catch (error) {
                console.error('Errore fetching clients:', error);
                showNotification('danger', `Errore di rete o API non raggiungibile: ${error.message}`);
            }
        }

        async function createClient() {
            const clientNameInput = document.getElementById('clientNameInput');
            const clientName = clientNameInput.value.trim();

            if (!clientName) {
                showNotification('danger', 'Il nome del client non può essere vuoto.');
                return;
            }
            // Basic client name validation (alphanumeric, underscore, hyphen, period)
            if (!/^[a-zA-Z0-9_.-]+$/.test(clientName)) {
                showNotification('danger', 'Nome client non valido. Usare solo lettere, numeri, trattini e underscore.');
                return;
            }

            showNotification('info', `Creazione client '${clientName}'...`);
            try {
                const formData = new FormData();
                formData.append('action', 'create_client');
                formData.append('client_name', clientName);

                const response = await fetch(API_AJAX_HANDLER, {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', result.body.message || `Client '${clientName}' creato con successo.`);
                    clientNameInput.value = ''; // Clear input
                    fetchAndRenderClients(); // Refresh lists
                } else {
                    const errorMessage = result.body.detail || 'Errore sconosciuto durante la creazione del client.';
                    showNotification('danger', `Errore: ${errorMessage}`);
                }
            } catch (error) {
                console.error('Errore creating client:', error);
                showNotification('danger', `Errore di rete o API non raggiungibile: ${error.message}`);
            }
        }

        async function downloadClient(clientName) {
            showNotification('info', `Preparazione download per '${clientName}'...`);
            try {
                // Fetch the .ovpn content directly. ajax_handler is set up to return the raw file.
                const response = await fetch(`${API_AJAX_HANDLER}?action=download_client&client_name=${clientName}`);
                
                // Check if the response is JSON (meaning an error occurred)
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    const errorResult = await response.json();
                    const errorMessage = errorResult.body.detail || 'Errore sconosciuto durante il download.';
                    showNotification('danger', `Errore download: ${errorMessage}`);
                    return;
                }

                // If not JSON, it's the .ovpn file content
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `${clientName}.ovpn`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                showNotification('success', `Download di '${clientName}.ovpn' avviato.`);

            } catch (error) {
                console.error('Errore downloading client config:', error);
                showNotification('danger', `Errore di rete o API non raggiungibile: ${error.message}`);
            }
        }

        async function revokeClient(clientName) {
            if (!confirm(`Sei sicuro di voler revocare il client '${clientName}'? Questa operazione è IRREVERSIBILE!`)) {
                return;
            }

            showNotification('info', `Revoca client '${clientName}'...`);
            try {
                const formData = new FormData();
                formData.append('action', 'revoke_client');
                formData.append('client_name', clientName);

                const response = await fetch(API_AJAX_HANDLER, {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', result.body.message || `Client '${clientName}' revocato con successo.`);
                    fetchAndRenderClients(); // Refresh lists
                } else {
                    const errorMessage = result.body.detail || 'Errore sconosciuto durante la revoca.';
                    showNotification('danger', `Errore: ${errorMessage}`);
                }
            } catch (error) {
                console.error('Errore revoking client:', error);
                showNotification('danger', `Errore di rete o API non raggiungibile: ${error.message}`);
            }
        }

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', fetchAndRenderClients);
    </script>
</body>
</html>