<?php
// index.php
?>
<!DOCTYPE html>
<html lang="it">

<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Gestore VPN Multi-Istanza</title>
    <!-- Tabler Core CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css" />
    <!-- Tabler Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css" />
    <style>
        body {
            min-width: 320px;
        }

        .instance-card {
            cursor: pointer;
            transition: transform 0.2s;
        }

        .instance-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>

<body>
    <div class="page">
        <header class="navbar navbar-expand-md d-print-none">
            <div class="container-xl">
                <h1 class="navbar-brand navbar-brand-autodark d-none-navbar-horizontal pe-0 pe-md-3">
                    <a href=".">Gestore VPN</a>
                </h1>
            </div>
        </header>

        <div class="page-wrapper">
            <div class="page-body">
                <div class="container-xl">
                    <div id="notification-container"></div>

                    <!-- DASHBOARD VIEW -->
                    <div id="dashboard-view">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <h2>Istanze OpenVPN</h2>
                            <button class="btn btn-primary" data-bs-toggle="modal"
                                data-bs-target="#modal-create-instance">
                                <i class="ti ti-plus icon"></i> Nuova Istanza
                            </button>
                        </div>
                        <div class="row row-cards" id="instances-container">
                            <!-- Instances will be loaded here -->
                        </div>
                    </div>

                    <!-- INSTANCE DETAILS VIEW -->
                    <div id="instance-view" style="display: none;">
                        <div class="mb-4">
                            <button class="btn btn-ghost-secondary" onclick="showDashboard()">
                                <i class="ti ti-arrow-left icon"></i> Torna alla Dashboard
                            </button>
                        </div>

                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h2 id="current-instance-name">Dettagli Istanza</h2>
                            <div>
                                <span class="badge bg-blue" id="current-instance-port"></span>
                                <span class="badge bg-green" id="current-instance-subnet"></span>
                                <button class="btn btn-danger btn-sm ms-3" onclick="deleteInstancePrompt()">
                                    <i class="ti ti-trash"></i> Elimina Istanza
                                </button>
                            </div>
                        </div>

                        <div class="card mb-4">
                            <div class="card-header">
                                <h3 class="card-title">Aggiungi Nuovo Client</h3>
                            </div>
                            <div class="card-body">
                                <form id="addClientForm" onsubmit="event.preventDefault(); createClient();">
                                    <div class="row g-2">
                                        <div class="col">
                                            <input type="text" id="clientNameInput" class="form-control"
                                                placeholder="Es: laptop-mario-rossi" required>
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

                        <div class="row">
                            <div class="col-md-6">
                                <div class="card mb-4">
                                    <div class="card-header">
                                        <h3 class="card-title">Client Disponibili</h3>
                                        <div class="card-actions">
                                            <button class="btn btn-icon" onclick="fetchAndRenderClients()">
                                                <i class="ti ti-refresh"></i>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                                        <table class="table table-vcenter card-table table-striped">
                                            <thead>
                                                <tr>
                                                    <th>Client</th>
                                                    <th class="w-1"></th>
                                                </tr>
                                            </thead>
                                            <tbody id="availableClientsTableBody"></tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card mb-4">
                                    <div class="card-header">
                                        <h3 class="card-title">Client Connessi</h3>
                                        <div class="card-actions">
                                            <button class="btn btn-icon" onclick="fetchAndRenderClients()">
                                                <i class="ti ti-refresh"></i>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                                        <table class="table table-vcenter card-table table-striped">
                                            <thead>
                                                <tr>
                                                    <th>Client</th>
                                                    <th>IP</th>
                                                    <th>Da</th>
                                                    <th class="w-1"></th>
                                                </tr>
                                            </thead>
                                            <tbody id="connectedClientsTableBody"></tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    </div>

    <!-- Modal Create Instance -->
    <div class="modal modal-blur fade" id="modal-create-instance" tabindex="-1" role="dialog" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Nuova Istanza OpenVPN</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="createInstanceForm">
                        <div class="mb-3">
                            <label class="form-label">Nome Istanza</label>
                            <input type="text" class="form-control" name="name" placeholder="Es: Cliente_A" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Porta (UDP)</label>
                                    <input type="number" class="form-control" name="port" placeholder="1194" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Subnet VPN</label>
                                    <input type="text" class="form-control" name="subnet" placeholder="10.8.0.0/24"
                                        required>
                                    <small class="form-hint">Deve essere una subnet privata unica.</small>
                                </div>
                            </div>
                            <div class="col-md-12">
                                <div class="mb-3">
                                    <label class="form-label">Interfaccia di Rete</label>
                                    <select class="form-select" name="outgoing_interface"
                                        id="outgoing-interface-select">
                                        <option value="">Auto-detect (Consigliato)</option>
                                    </select>
                                    <small class="form-hint">Seleziona l'interfaccia di rete da usare per il routing
                                        VPN.</small>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                    <button type="button" class="btn btn-primary" onclick="createInstance()">Crea Istanza</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal Revoke Client -->
    <div class="modal modal-blur fade" id="modal-revoke-confirm" tabindex="-1" role="dialog" aria-hidden="true">
        <div class="modal-dialog modal-sm modal-dialog-centered" role="document">
            <div class="modal-content">
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                <div class="modal-status bg-danger"></div>
                <div class="modal-body text-center py-4">
                    <i class="ti ti-alert-triangle icon mb-2 text-danger icon-lg"></i>
                    <h3>Conferma Revoca</h3>
                    <div class="text-muted">
                        Sei sicuro di voler revocare il client '<span id="revoke-client-name"></span>'?
                    </div>
                </div>
                <div class="modal-footer">
                    <div class="w-100">
                        <div class="row">
                            <div class="col"><a href="#" class="btn w-100" data-bs-dismiss="modal">Annulla</a></div>
                            <div class="col"><a href="#" class="btn btn-danger w-100" id="confirm-revoke-button"
                                    data-bs-dismiss="modal">Revoca</a></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal Delete Instance -->
    <div class="modal modal-blur fade" id="modal-delete-instance" tabindex="-1" role="dialog" aria-hidden="true">
        <div class="modal-dialog modal-sm modal-dialog-centered" role="document">
            <div class="modal-content">
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                <div class="modal-status bg-danger"></div>
                <div class="modal-body text-center py-4">
                    <i class="ti ti-alert-triangle icon mb-2 text-danger icon-lg"></i>
                    <h3>Elimina Istanza</h3>
                    <div class="text-muted">
                        Sei sicuro di voler eliminare l'istanza corrente? Tutti i dati verranno persi.
                    </div>
                </div>
                <div class="modal-footer">
                    <div class="w-100">
                        <div class="row">
                            <div class="col"><a href="#" class="btn w-100" data-bs-dismiss="modal">Annulla</a></div>
                            <div class="col"><a href="#" class="btn btn-danger w-100" onclick="deleteInstanceAction()"
                                    data-bs-dismiss="modal">Elimina</a></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js"></script>
    <script>
        const API_AJAX_HANDLER = 'ajax_handler.php';
        let currentInstance = null;

        function showNotification(type, message) {
            const container = document.getElementById('notification-container');
            const alertHtml = `
                <div class="alert alert-${type} alert-dismissible" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            container.innerHTML = alertHtml;
            setTimeout(() => {
                const alert = container.querySelector('.alert');
                if (alert) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, 5000);
        }

        function formatDateTime(isoString) {
            if (!isoString) return 'N/D';
            try {
                return new Date(isoString).toLocaleString('it-IT');
            } catch (e) { return 'N/D'; }
        }

        // --- DASHBOARD FUNCTIONS ---

        async function loadInstances() {
            try {
                const response = await fetch(`${API_AJAX_HANDLER}?action=get_instances`);
                const result = await response.json();
                const container = document.getElementById('instances-container');
                container.innerHTML = '';

                if (result.success) {
                    const instances = result.body;
                    if (instances.length === 0) {
                        container.innerHTML = '<div class="col-12 text-center text-muted p-5">Nessuna istanza configurata. Creane una nuova.</div>';
                        return;
                    }

                    instances.forEach(inst => {
                        const statusColor = inst.status === 'running' ? 'bg-success' : 'bg-danger';
                        const html = `
                            <div class="col-md-6 col-lg-4">
                                <div class="card instance-card" onclick='openInstance(${JSON.stringify(inst)})'>
                                    <div class="card-body">
                                        <div class="d-flex align-items-center mb-3">
                                            <span class="status-dot ${statusColor} me-2"></span>
                                            <h3 class="card-title m-0">${inst.name}</h3>
                                        </div>
                                        <div class="text-muted">
                                            <div><strong>Porta:</strong> ${inst.port}</div>
                                            <div><strong>Subnet:</strong> ${inst.subnet}</div>
                                            <div><strong>Protocollo:</strong> ${inst.protocol}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                        container.innerHTML += html;
                    });
                } else {
                    showNotification('danger', 'Errore caricamento istanze: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        async function createInstance() {
            const form = document.getElementById('createInstanceForm');
            const formData = new FormData(form);
            formData.append('action', 'create_instance');

            try {
                const response = await fetch(API_AJAX_HANDLER, { method: 'POST', body: formData });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', 'Istanza creata con successo!');
                    bootstrap.Modal.getInstance(document.getElementById('modal-create-instance')).hide();
                    form.reset();
                    loadInstances();
                } else {
                    showNotification('danger', 'Errore creazione: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        async function loadNetworkInterfaces() {
            try {
                const response = await fetch(`${API_AJAX_HANDLER}?action=get_network_interfaces`);
                const result = await response.json();
                const select = document.getElementById('outgoing-interface-select');
                
                // Clear existing options except the auto-detect
                while (select.options.length > 1) {
                    select.remove(1);
                }

                if (result.success && result.body) {
                    result.body.forEach(iface => {
                        const option = document.createElement('option');
                        option.value = iface.name;
                        option.textContent = `${iface.name} (${iface.ip}/${iface.cidr})`;
                        select.appendChild(option);
                    });
                }
            } catch (e) {
                console.error('Error loading network interfaces:', e);
            }
        }

        function openInstance(instance) {
            currentInstance = instance;
            document.getElementById('dashboard-view').style.display = 'none';
            document.getElementById('instance-view').style.display = 'block';

            document.getElementById('current-instance-name').textContent = instance.name;
            document.getElementById('current-instance-port').textContent = 'Porta: ' + instance.port;
            document.getElementById('current-instance-subnet').textContent = 'Subnet: ' + instance.subnet;

            fetchAndRenderClients();
        }

        function showDashboard() {
            currentInstance = null;
            document.getElementById('instance-view').style.display = 'none';
            document.getElementById('dashboard-view').style.display = 'block';
            loadInstances();
        }

        function deleteInstancePrompt() {
            new bootstrap.Modal(document.getElementById('modal-delete-instance')).show();
        }

        async function deleteInstanceAction() {
            if (!currentInstance) return;
            try {
                const formData = new FormData();
                formData.append('action', 'delete_instance');
                formData.append('instance_id', currentInstance.id);

                const response = await fetch(API_AJAX_HANDLER, { method: 'POST', body: formData });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', 'Istanza eliminata.');
                    showDashboard();
                } else {
                    showNotification('danger', 'Errore eliminazione: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        // --- CLIENT FUNCTIONS ---

        async function fetchAndRenderClients() {
            if (!currentInstance) return;

            try {
                const response = await fetch(`${API_AJAX_HANDLER}?action=get_clients&instance_id=${currentInstance.id}`);
                const result = await response.json();

                const availBody = document.getElementById('availableClientsTableBody');
                const connBody = document.getElementById('connectedClientsTableBody');
                availBody.innerHTML = '';
                connBody.innerHTML = '';

                if (result.success) {
                    const clients = result.body;

                    clients.forEach(client => {
                        if (client.status === 'connected') {
                            connBody.innerHTML += `
                                <tr>
                                    <td>${client.name}</td>
                                    <td>${client.virtual_ip || '-'}</td>
                                    <td>${formatDateTime(client.connected_since)}</td>
                                    <td>
                                        <button class="btn btn-danger btn-sm btn-icon" onclick="revokeClient('${client.name}')">
                                            <i class="ti ti-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            `;
                        } else {
                            availBody.innerHTML += `
                                <tr>
                                    <td>${client.name}</td>
                                    <td>
                                        <button class="btn btn-primary btn-sm btn-icon" onclick="downloadClient('${client.name}')">
                                            <i class="ti ti-download"></i>
                                        </button>
                                        <button class="btn btn-danger btn-sm btn-icon" onclick="revokeClient('${client.name}')">
                                            <i class="ti ti-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            `;
                        }
                    });

                    if (clients.length === 0) {
                        availBody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Nessun client.</td></tr>';
                        connBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Nessun client connesso.</td></tr>';
                    }

                } else {
                    showNotification('danger', 'Errore caricamento client: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        async function createClient() {
            if (!currentInstance) return;
            const input = document.getElementById('clientNameInput');
            const name = input.value.trim();
            if (!name) return;

            try {
                const formData = new FormData();
                formData.append('action', 'create_client');
                formData.append('instance_id', currentInstance.id);
                formData.append('client_name', name);

                const response = await fetch(API_AJAX_HANDLER, { method: 'POST', body: formData });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', 'Client creato.');
                    input.value = '';
                    fetchAndRenderClients();
                } else {
                    showNotification('danger', 'Errore creazione: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        async function downloadClient(clientName) {
            if (!currentInstance) return;
            window.location.href = `${API_AJAX_HANDLER}?action=download_client&instance_id=${currentInstance.id}&client_name=${clientName}`;
        }

        function revokeClient(clientName) {
            document.getElementById('revoke-client-name').textContent = clientName;
            document.getElementById('confirm-revoke-button').onclick = () => performRevoke(clientName);
            new bootstrap.Modal(document.getElementById('modal-revoke-confirm')).show();
        }

        async function performRevoke(clientName) {
            if (!currentInstance) return;
            try {
                const formData = new FormData();
                formData.append('action', 'revoke_client');
                formData.append('instance_id', currentInstance.id);
                formData.append('client_name', clientName);

                const response = await fetch(API_AJAX_HANDLER, { method: 'POST', body: formData });
                const result = await response.json();

                if (result.success) {
                    showNotification('success', 'Client revocato.');
                    fetchAndRenderClients();
                } else {
                    showNotification('danger', 'Errore revoca: ' + (result.body.detail || 'Sconosciuto'));
                }
            } catch (e) {
                showNotification('danger', 'Errore di connessione: ' + e.message);
            }
        }

        // Init
        document.addEventListener('DOMContentLoaded', () => {
            loadInstances();
            
            // Load network interfaces when modal is shown
            const instanceModal = document.getElementById('modal-create-instance');
            instanceModal.addEventListener('show.bs.modal', loadNetworkInterfaces);
        });

    </script>
</body>

</html>