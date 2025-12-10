// js/instance.js

let currentInstance = null;
let editRouteCounter = 0;

async function loadInstanceDetails(instanceId) {
    if (!instanceId) return;
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_instance&instance_id=${instanceId}`);
        const result = await response.json();

        if (result.success) {
            currentInstance = result.body;
            renderInstanceDetails();
            fetchAndRenderClients();
            displayRoutes();
        } else {
            showNotification('danger', 'Errore caricamento istanza: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

function renderInstanceDetails() {
    if (!currentInstance) return;

    document.getElementById('current-instance-name').textContent = currentInstance.name;

    // Render Port Badge (Soft Color: Blue Lt)
    document.getElementById('current-instance-port').innerHTML = `
        <span class="badge bg-blue-lt">Port: ${currentInstance.port}</span>
    `;

    // Render Subnet Badge (Soft Color: Green Lt)
    document.getElementById('current-instance-subnet').innerHTML = `
        <span class="badge bg-green-lt">Subnet: ${currentInstance.subnet}</span>
    `;

    // DNS badge is handled in Routes card logic now
}

// --- CLIENTS ---

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
                const displayName = client.name.replace(`${currentInstance.name}_`, '');
                const fullName = client.name;

                // Always render to Available Clients list (Left Side)
                availBody.innerHTML += `
                    <tr>
                        <td>
                            <div class="d-flex align-items-center">
                                ${client.status === 'connected' ? '<span class="status-dot status-dot-animated status-green me-2"></span>' : ''}
                                ${displayName}
                            </div>
                        </td>
                        <td>
                            <div class="d-flex gap-2 justify-content-end">
                                <button class="btn btn-primary btn-sm btn-icon" onclick="downloadClient('${fullName}')" title="Scarica Configurazione">
                                    <i class="ti ti-download"></i>
                                </button>
                                <button class="btn btn-danger btn-sm btn-icon" onclick="revokeClient('${fullName}')" title="Revoca Client">
                                    <i class="ti ti-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;

                // If connected, ALSO render to Connected Clients list (Right Side)
                if (client.status === 'connected') {
                    connBody.innerHTML += `
                        <tr>
                            <td>
                                <div class="d-flex align-items-center gap-2">
                                    <span class="status-indicator status-green status-indicator-animated">
                                        <span class="status-indicator-circle"></span>
                                        <span class="status-indicator-circle"></span>
                                        <span class="status-indicator-circle"></span>
                                    </span>
                                    ${displayName}
                                </div>
                            </td>
                            <td>
                                <div>${client.real_ip || '-'}</div>
                                <div class="small text-muted">VPN: ${client.virtual_ip || '-'}</div>
                            </td>
                            <td class="text-muted">
                                <div><i class="ti ti-arrow-down icon-sm text-green"></i> ${formatBytes(client.bytes_received)}</div>
                                <div><i class="ti ti-arrow-up icon-sm text-blue"></i> ${formatBytes(client.bytes_sent)}</div>
                            </td>
                            <td>${formatDateTime(client.connected_since)}</td>
                            <td>
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
            }
            if (connBody.innerHTML === '') {
                connBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nessun client connesso.</td></tr>';
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

    // --- VALIDATION ---
    const nameRegex = /^[a-zA-Z0-9_.-]+$/;
    if (name === '' || !nameRegex.test(name)) {
        input.classList.add('is-invalid');
        showNotification('danger', 'Il nome del client non è valido.');
        return;
    }
    // --- END VALIDATION ---


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

function downloadClient(clientName) {
    if (!currentInstance) return;
    window.location.href = `${API_AJAX_HANDLER}?action=download_client&instance_id=${currentInstance.id}&client_name=${clientName}`;
}

function revokeClient(clientName) {
    let displayName = clientName;
    if (currentInstance && clientName.startsWith(currentInstance.name + "_")) {
        displayName = clientName.replace(currentInstance.name + "_", "");
    }
    document.getElementById('revoke-client-name').textContent = displayName;
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

// --- ROUTES & DNS ---

function displayRoutes() {
    if (!currentInstance) return;

    const tunnelModeDisplay = document.getElementById('tunnel-mode-display');
    if (tunnelModeDisplay) {
        tunnelModeDisplay.textContent = currentInstance.tunnel_mode === 'full' ? 'Full Tunnel' : 'Split Tunnel';
        tunnelModeDisplay.className = `badge bg-${currentInstance.tunnel_mode === 'full' ? 'primary' : 'warning'} ms-2`;
    }

    const list = document.getElementById('routes-list');
    const dnsViewContainer = document.getElementById('dns-view-container');
    const currentDnsDisplay = document.getElementById('current-dns-display');

    list.innerHTML = '';

    // DNS Display Logic
    if (currentInstance.tunnel_mode === 'full') {
        if (dnsViewContainer) {
            dnsViewContainer.style.display = 'block';
            let dnsText = 'Default (Google)';
            if (currentInstance.dns_servers && currentInstance.dns_servers.length > 0) {
                dnsText = currentInstance.dns_servers.join(', ');
            }
            currentDnsDisplay.textContent = dnsText;
        }
    } else {
        if (dnsViewContainer) dnsViewContainer.style.display = 'none';
    }

    // Routes Display Logic
    if (currentInstance.tunnel_mode === 'full') {
        list.innerHTML = `
            <div class="list-group-item">
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">Full Tunnel</h5>
                </div>
                <p class="mb-1 text-muted">Tutto il traffico passa attraverso la VPN.</p>
            </div>
        `;
    } else {
        if (currentInstance.routes && currentInstance.routes.length > 0) {
            currentInstance.routes.forEach(route => {
                list.innerHTML += `
                    <div class="list-group-item">
                        <div class="row align-items-center">
                            <div class="col-auto">
                                <span class="badge bg-blue"></span>
                            </div>
                            <div class="col">
                                <span class="text-body d-block">${route.network}</span>
                                <small class="text-muted d-block">via ${route.interface}</small>
                            </div>
                        </div>
                    </div>
                `;
            });
        } else {
            list.innerHTML = `<div class="p-3 text-muted text-center">Nessuna rotta personalizzata configurata.</div>`;
        }
    }
}

function toggleRouteEdit() {
    const viewMode = document.getElementById('routes-view-mode');
    const editMode = document.getElementById('routes-edit-mode');

    viewMode.style.display = 'none';
    editMode.style.display = 'block';

    if (!currentInstance) return;

    document.getElementById('tunnel-mode-edit').value = currentInstance.tunnel_mode;
    renderRouteEditContainer();
}

function renderRouteEditContainer() {
    const container = document.getElementById('routes-edit-container');
    const tunnelMode = document.getElementById('tunnel-mode-edit').value;

    container.innerHTML = '';
    editRouteCounter = 0;

    // 1. DNS Input (Full Tunnel)
    if (tunnelMode === 'full') {
        let dnsValue = '';
        if (currentInstance.dns_servers && currentInstance.dns_servers.length > 0) {
            dnsValue = currentInstance.dns_servers.join(', ');
        }
        container.innerHTML += `
            <div class="mb-3">
                <label class="form-label">DNS Servers</label>
                <input type="text" class="form-control" id="dns-servers-edit-input" value="${dnsValue}" placeholder="Es: 1.1.1.1, 8.8.8.8">
                <div class="invalid-feedback">Uno o più indirizzi IP non sono validi.</div>
                <small class="form-hint">Lascia vuoto per usare i default (Google).</small>
            </div>
        `;
    }

    // 2. Routes (Split Tunnel)
    if (tunnelMode === 'split') {
        if (currentInstance.routes && currentInstance.routes.length > 0) {
            currentInstance.routes.forEach((route) => {
                addRouteEdit(route.network, route.interface);
            });
        } else {
            if (container.querySelectorAll('[data-edit-route-network]').length === 0) {
                addRouteEdit();
            }
        }
    }

    const addBtn = document.querySelector('button[onclick="addRouteEdit()"]');
    if (addBtn) {
        addBtn.style.display = (tunnelMode === 'split') ? 'inline-block' : 'none';
    }
}

function toggleRouteConfigEdit() {
    renderRouteEditContainer();
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
                <input type="text" class="form-control" placeholder="192.168.1.0/24" data-edit-route-network="${routeId}" value="${network}">
                <div class="invalid-feedback">Formato CIDR non valido (es. 192.168.1.0/24).</div>
            </div>
            <div class="col-md-5">
                <select class="form-select" data-edit-route-interface="${routeId}" id="edit-route-interface-${routeId}">
                    <option value="">Seleziona Interfaccia</option>
                </select>
                <div class="invalid-feedback">Seleziona un'interfaccia.</div>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-danger btn-sm" onclick="removeRouteEdit(${routeId})">
                    <i class="ti ti-trash"></i>
                </button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
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
    let isValid = true;

    // Helper functions for validation
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    const cidrRegex = /^([0-9]{1,3}\.){3}[0-9]{1,3}\/([0-9]|[1-2][0-9]|3[0-2])$/;
    
    // --- Clear previous validation states ---
    document.querySelectorAll('#routes-edit-mode .is-invalid').forEach(el => el.classList.remove('is-invalid'));

    let dnsServers = [];
    if (tunnelMode === 'full') {
        const dnsInput = document.getElementById('dns-servers-edit-input');
        if (dnsInput && dnsInput.value.trim() !== '') {
            dnsServers = dnsInput.value.split(',').map(s => s.trim()).filter(s => s !== '');
            for (const ip of dnsServers) {
                if (!ipRegex.test(ip)) {
                    isValid = false;
                    dnsInput.classList.add('is-invalid');
                    break; 
                }
            }
        }
    }

    const routes = [];
    if (tunnelMode === 'split') {
        const routeNetworkInputs = document.querySelectorAll('[data-edit-route-network]');
        routeNetworkInputs.forEach(input => {
            const routeId = input.getAttribute('data-edit-route-network');
            const network = input.value.trim();
            const interfaceSelect = document.querySelector(`[data-edit-route-interface="${routeId}"]`);
            
            if (network === '' || !cidrRegex.test(network)) {
                isValid = false;
                input.classList.add('is-invalid');
            }

            if (!interfaceSelect || interfaceSelect.value === '') {
                isValid = false;
                if(interfaceSelect) interfaceSelect.classList.add('is-invalid');
            }
            
            if (network && interfaceSelect && interfaceSelect.value) {
                routes.push({ network: network, interface: interfaceSelect.value });
            }
        });
    }

    if (!isValid) {
        showNotification('danger', 'Uno o più campi non sono validi. Controlla e riprova.');
        return;
    }

    const payload = {
        action: 'update_instance_routes',
        instance_id: currentInstance.id,
        tunnel_mode: tunnelMode,
        routes: routes,
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
            showNotification('success', 'Configurazione aggiornata!');
            // Reload details to verify
            loadInstanceDetails(currentInstance.id);
            cancelRouteEdit();
        } else {
            showNotification('danger', 'Errore aggiornamento: ' + (result.body?.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// DELETE ACTION
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
            window.location.href = 'index.php'; // Redirect to dashboard
        } else {
            showNotification('danger', 'Errore eliminazione: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Read instance ID from query string logic (handled in page script usually, or here)
    const urlParams = new URLSearchParams(window.location.search);
    const instanceId = urlParams.get('id');
    if (instanceId) {
        loadInstanceDetails(instanceId);
    }

    // Real-time validation for client name
    const clientNameInput = document.getElementById('clientNameInput');
    if (clientNameInput) {
        clientNameInput.addEventListener('input', () => {
            const nameRegex = /^[a-zA-Z0-9_.-]+$/;
            const value = clientNameInput.value;

            if (value.trim() === '' || !nameRegex.test(value)) {
                clientNameInput.classList.add('is-invalid');
            } else {
                clientNameInput.classList.remove('is-invalid');
            }
        });
    }
});
