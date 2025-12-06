const API_AJAX_HANDLER = 'ajax_handler.php';
let currentInstance = null;

// --- UTILS ---

function showNotification(type, message) {
    const container = document.getElementById('notification-container');
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    container.innerHTML = alertHtml;
    // Auto dismiss after 5 seconds
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

function formatDnsList(dnsList) {
    if (!dnsList || dnsList.length === 0) return 'Default (Google)';
    return dnsList.join(', ');
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

// --- INSTANCE CREATION ---

let routeCounter = 0;

function toggleRouteConfig() {
    const tunnelMode = document.getElementById('tunnel-mode-select').value;
    const routesConfig = document.getElementById('routes-config');
    if (tunnelMode === 'split') {
        routesConfig.style.display = 'block';
        // Add first route if none
        if (document.getElementById('routes-container').children.length === 0) {
            addRoute();
        }
    } else {
        routesConfig.style.display = 'none';
    }
}

function addRoute() {
    const container = document.getElementById('routes-container');
    const routeId = routeCounter++;
    const html = `
        <div class="row mb-2" id="route-${routeId}">
            <div class="col-md-5">
                <input type="text" class="form-control" placeholder="192.168.1.0/24" data-route-network="${routeId}" required>
            </div>
            <div class="col-md-5">
                <select class="form-select" data-route-interface="${routeId}" id="route-interface-${routeId}">
                    <option value="">Seleziona Interfaccia</option>
                </select>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-danger btn-sm" onclick="removeRoute(${routeId})">
                    <i class="ti ti-trash"></i>
                </button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    // Populate interface dropdown for this route
    populateRouteInterface(routeId);
}

async function populateRouteInterface(routeId) {
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_network_interfaces`);
        const result = await response.json();
        const select = document.getElementById(`route-interface-${routeId}`);

        if (result.success && result.body) {
            result.body.forEach(iface => {
                const option = document.createElement('option');
                option.value = iface.name;
                option.textContent = `${iface.name} (${iface.ip}/${iface.cidr})`;
                select.appendChild(option);
            });
        }
    } catch (e) {
        console.error('Error loading interfaces for route:', e);
    }
}

function removeRoute(routeId) {
    document.getElementById(`route-${routeId}`).remove();
}

async function loadNetworkInterfaces() {
    // This function was referenced in index.php but not implemented or I missed it.
    // Implementing purely to support the listener if needed, 
    // but the actual population happens in addRoute.
    // Ideally, we could pre-fetch interfaces.
}

async function createInstance() {
    const form = document.getElementById('createInstanceForm');
    const formData = new FormData(form);

    // Parse DNS
    const dnsInput = formData.get('dns_servers');
    let dnsServers = [];
    if (dnsInput && dnsInput.trim() !== '') {
        dnsServers = dnsInput.split(',').map(s => s.trim()).filter(s => s !== '');
    }

    // Gather routes if split tunnel
    const tunnelMode = formData.get('tunnel_mode');
    const routes = [];

    if (tunnelMode === 'split') {
        const routeNetworks = document.querySelectorAll('[data-route-network]');
        routeNetworks.forEach(input => {
            const routeId = input.getAttribute('data-route-network');
            const network = input.value.trim();
            const interfaceSelect = document.querySelector(`[data-route-interface="${routeId}"]`);
            const interfaceName = interfaceSelect ? interfaceSelect.value : '';

            if (network && interfaceName) {
                routes.push({ network, interface: interfaceName });
            }
        });
    }

    // Build request payload
    const payload = {
        action: 'create_instance',
        name: formData.get('name'),
        port: parseInt(formData.get('port')),
        subnet: formData.get('subnet'),
        protocol: 'udp',
        tunnel_mode: tunnelMode,
        routes: routes,
        dns_servers: dnsServers
    };

    try {
        const response = await fetch(API_AJAX_HANDLER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Istanza creata con successo!');
            // Improve Modal Dismissal: getOrCreateInstance + remove backdrop if needed
            const modalEl = document.getElementById('modal-create-instance');
            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
            modalInstance.hide();

            // Force removal of backdrop if it persists (Bootstrap bug workaround)
            setTimeout(() => {
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(bd => bd.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }, 300);

            form.reset();
            document.getElementById('routes-container').innerHTML = '';
            routeCounter = 0;
            loadInstances();
        } else {
            showNotification('danger', 'Errore creazione: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// --- INSTANCE MANAGEMENT ---

function openInstance(instance) {
    currentInstance = instance;
    document.getElementById('dashboard-view').style.display = 'none';
    document.getElementById('instance-view').style.display = 'block';

    document.getElementById('current-instance-name').textContent = instance.name;
    document.getElementById('current-instance-port').textContent = `Port: ${instance.port}`;
    document.getElementById('current-instance-subnet').textContent = `Subnet: ${instance.subnet}`;

    // Render DNS Badge
    const dnsContainer = document.getElementById('current-instance-dns-container');
    if (dnsContainer) {
        let dnsText = 'Default DNS';
        if (instance.dns_servers && instance.dns_servers.length > 0) {
            dnsText = instance.dns_servers.join(', ');
        }

        dnsContainer.innerHTML = `
            <span class="badge badge-outline text-blue ms-2" style="background: rgba(32, 107, 196, 0.1);">
                DNS: ${dnsText}
                <a href="#" class="ms-2 text-blue" onclick="openDnsEditModal(); return false;">
                    <i class="ti ti-pencil"></i>
                </a>
            </span>
        `;
    }

    fetchAndRenderClients();
    displayRoutes();
}

function openDnsEditModal() {
    if (!currentInstance) return;

    const input = document.getElementById('dns-servers-modal-input');
    if (currentInstance.dns_servers && Array.isArray(currentInstance.dns_servers)) {
        input.value = currentInstance.dns_servers.join(', ');
    } else {
        input.value = '';
    }

    new bootstrap.Modal(document.getElementById('modal-edit-dns')).show();
}

async function saveDnsConfig() {
    if (!currentInstance) return;

    const input = document.getElementById('dns-servers-modal-input').value;
    let dnsServers = [];
    if (input && input.trim() !== '') {
        dnsServers = input.split(',').map(s => s.trim()).filter(s => s !== '');
    }

    // We reuse update_instance_routes but keep current tunnel/routes
    const payload = {
        action: 'update_instance_routes',
        instance_id: currentInstance.id,
        tunnel_mode: currentInstance.tunnel_mode,
        routes: currentInstance.routes,
        dns_servers: dnsServers
    };

    try {
        const response = await fetch(API_AJAX_HANDLER, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'DNS aggiornati con successo!');
            currentInstance.dns_servers = dnsServers;

            // Update UI
            openInstance(currentInstance); // Re-render header

            // Close modal
            const modalEl = document.getElementById('modal-edit-dns');
            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
            modalInstance.hide();
        } else {
            showNotification('danger', 'Errore aggiornamento DNS: ' + (result.body?.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
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
                // Strip instance prefix for display
                const displayName = client.name.replace(`${currentInstance.name}_`, '');
                const fullName = client.name; // Keep full name for API calls

                if (client.status === 'connected') {
                    connBody.innerHTML += `
                        <tr>
                            <td>${displayName}</td>
                            <td>${client.virtual_ip || '-'}</td>
                            <td>${formatDateTime(client.connected_since)}</td>
                            <td>
                                <button class="btn btn-danger btn-sm btn-icon" onclick="revokeClient('${fullName}')">
                                    <i class="ti ti-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                } else {
                    availBody.innerHTML += `
                        <tr>
                            <td>${displayName}</td>
                            <td>
                                <button class="btn btn-primary btn-sm btn-icon" onclick="downloadClient('${fullName}')">
                                    <i class="ti ti-download"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-icon" onclick="revokeClient('${fullName}')">
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

// --- ROUTE MANAGEMENT ---

let editRouteCounter = 0;

function displayRoutes() {
    if (!currentInstance) return;

    // Display tunnel mode
    const tunnelModeDisplay = document.getElementById('tunnel-mode-display');
    tunnelModeDisplay.textContent = currentInstance.tunnel_mode === 'full' ? 'Full Tunnel' : 'Split Tunnel';
    tunnelModeDisplay.className = `badge bg-${currentInstance.tunnel_mode === 'full' ? 'primary' : 'warning'} ms-2`;

    // Display routes list
    const routesList = document.getElementById('routes-list');
    if (!currentInstance.routes || currentInstance.routes.length === 0) {
        routesList.innerHTML = '<p class="text-muted mt-2">Nessuna rotta personalizzata</p>';
    } else {
        let html = '<div class="list-group list-group-flush mt-2">';
        currentInstance.routes.forEach(route => {
            html += `
                <div class="list-group-item">
                    <div class="row align-items-center">
                        <div class="col-auto">
                            <i class="ti ti-route text-muted"></i>
                        </div>
                        <div class="col">
                            <strong>${route.network}</strong>
                            <div class="text-muted small">via ${route.interface}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        routesList.innerHTML = html;
    }
}

async function toggleRouteEdit() {
    const viewMode = document.getElementById('routes-view-mode');
    const editMode = document.getElementById('routes-edit-mode');

    viewMode.style.display = 'none';
    editMode.style.display = 'block';

    // Pre-populate edit form
    document.getElementById('tunnel-mode-edit').value = currentInstance.tunnel_mode;

    toggleRouteConfigEdit();

    // Clear and populate routes
    const container = document.getElementById('routes-edit-container');
    container.innerHTML = '';
    editRouteCounter = 0;

    if (currentInstance.routes && currentInstance.routes.length > 0) {
        for (const route of currentInstance.routes) {
            await addRouteEdit(route.network, route.interface);
        }
    }
}

function toggleRouteConfigEdit() {
    const tunnelMode = document.getElementById('tunnel-mode-edit').value;
    const container = document.getElementById('routes-edit-container');
    const addBtn = document.querySelector('button[onclick="addRouteEdit()"]');

    if (tunnelMode === 'split') {
        container.style.display = 'block';
        if (addBtn) addBtn.style.display = 'inline-block';
    } else {
        container.style.display = 'none';
        if (addBtn) addBtn.style.display = 'none';
    }
}

function cancelRouteEdit() {
    document.getElementById('routes-view-mode').style.display = 'block';
    document.getElementById('routes-edit-mode').style.display = 'none';
}

async function addRouteEdit(network = '', interfaceName = '') {
    const container = document.getElementById('routes-edit-container');
    const routeId = editRouteCounter++;

    const html = `
        <div class="row mb-2" id="edit-route-${routeId}">
            <div class="col-md-5">
                <input type="text" class="form-control" 
                    placeholder="192.168.1.0/24" 
                    data-edit-route-network="${routeId}" 
                    value="${network}">
            </div>
            <div class="col-md-5">
                <select class="form-select" 
                    data-edit-route-interface="${routeId}" 
                    id="edit-route-interface-${routeId}">
                    <option value="">Seleziona Interfaccia</option>
                </select>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-danger btn-sm" onclick="removeRouteEdit(${routeId})">
                    <i class="ti ti-trash"></i>
                </button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);

    // Populate interface dropdown
    await populateEditRouteInterface(routeId, interfaceName);
}

async function populateEditRouteInterface(routeId, selectedInterface = '') {
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_network_interfaces`);
        const result = await response.json();
        const select = document.getElementById(`edit-route-interface-${routeId}`);

        if (result.success && result.body) {
            result.body.forEach(iface => {
                const option = document.createElement('option');
                option.value = iface.name;
                option.textContent = `${iface.name} (${iface.ip}/${iface.cidr})`;
                if (iface.name === selectedInterface) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
        }
    } catch (e) {
        console.error('Error loading interfaces:', e);
    }
}

function removeRouteEdit(routeId) {
    document.getElementById(`edit-route-${routeId}`).remove();
}

async function saveRoutes() {
    if (!currentInstance) return;

    const tunnelMode = document.getElementById('tunnel-mode-edit').value;
    // DNS is handled separately now

    const routes = [];

    // Gather routes
    const routeNetworks = document.querySelectorAll('[data-edit-route-network]');
    routeNetworks.forEach(input => {
        const routeId = input.getAttribute('data-edit-route-network');
        const network = input.value.trim();
        const interfaceSelect = document.querySelector(`[data-edit-route-interface="${routeId}"]`);
        const interfaceName = interfaceSelect ? interfaceSelect.value : '';

        if (network && interfaceName) {
            routes.push({ network, interface: interfaceName });
        }
    });

    // Send update
    const payload = {
        action: 'update_instance_routes',
        instance_id: currentInstance.id,
        tunnel_mode: tunnelMode,
        routes: routes,
        dns_servers: currentInstance.dns_servers // Preserve existing DNS
    };

    try {
        const response = await fetch(API_AJAX_HANDLER, {
            method: 'PATCH', // Changed to PATCH (supported by api_client.php now)
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Rotte aggiornate con successo!');
            // Refresh instance data
            currentInstance.tunnel_mode = tunnelMode;
            currentInstance.routes = routes;

            displayRoutes();
            cancelRouteEdit();
        } else {
            showNotification('danger', 'Errore aggiornamento rotte: ' + (result.body?.detail || 'Sconosciuto'));
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
