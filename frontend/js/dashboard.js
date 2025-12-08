// js/dashboard.js

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
                        <div class="card instance-card" onclick='location.href="instance.php?id=${inst.id}"'>
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <span class="status-dot ${statusColor} me-2"></span>
                                    <h3 class="card-title m-0">${inst.name}</h3>
                                </div>
                                <div class="text-muted">
                                    <div><strong>Porta:</strong> ${inst.port}</div>
                                    <div><strong>Subnet:</strong> ${inst.subnet}</div>
                                    <div><strong>Subnet:</strong> ${inst.subnet}</div>
                                    <div class="mt-2 text-dark">
                                        <span class="badge ${inst.tunnel_mode === 'full' ? 'bg-primary-lt' : 'bg-warning-lt'}">
                                            ${inst.tunnel_mode === 'full' ? 'Full Tunnel' : 'Split Tunnel'}
                                        </span>
                                    </div>
                                    <div class="d-flex align-items-center mt-2">
                                        <i class="ti ti-users me-1"></i>
                                        <strong>${inst.connected_clients || 0}</strong> &nbsp;Client Attivi
                                    </div>
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

// Instance Creation Logic
let routeCounter = 0;

function toggleRouteConfig() {
    const tunnelMode = document.getElementById('tunnel-mode-select').value;
    const routesConfig = document.getElementById('routes-config');

    if (tunnelMode === 'split') {
        routesConfig.style.display = 'block';
        if (document.getElementById('routes-container').children.length === 0) {
            addRoute();
        }
    } else {
        routesConfig.style.display = 'none';
    }

    const dnsInput = document.querySelector('input[name="dns_servers"]');
    if (dnsInput) {
        // Find the specific parent div for the DNS input group
        // In index.php it's a div.mb-3 directly containing the label and input
        const container = dnsInput.closest('.mb-3');
        if (container) {
            if (tunnelMode === 'full') {
                container.style.display = 'block';
                dnsInput.disabled = false;
            } else {
                container.style.display = 'none';
                dnsInput.disabled = true;
                dnsInput.value = '';
            }
        }
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
    populateRouteInterface(routeId);
}

function removeRoute(routeId) {
    document.getElementById(`route-${routeId}`).remove();
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

async function createInstance() {
    const form = document.getElementById('createInstanceForm');
    const formData = new FormData(form);

    const dnsInput = formData.get('dns_servers');
    let dnsServers = [];
    if (dnsInput && dnsInput.trim() !== '') {
        dnsServers = dnsInput.split(',').map(s => s.trim()).filter(s => s !== '');
    }

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

            const modalEl = document.getElementById('modal-create-instance');
            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
            modalInstance.hide();

            // Fix backdrop
            setTimeout(() => {
                document.querySelectorAll('.modal-backdrop').forEach(bd => bd.remove());
                document.body.classList.remove('modal-open');
                document.body.style = '';
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

document.addEventListener('DOMContentLoaded', () => {
    loadInstances();
    const instanceModal = document.getElementById('modal-create-instance');
    if (instanceModal) {
        // Possible init code
    }
    loadTopClients();
});

async function loadTopClients() {
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_top_clients`);
        const result = await response.json();
        const container = document.getElementById('top-clients-container');

        if (!container) return;
        container.innerHTML = '';

        if (result.success) {
            const clients = result.body;
            if (clients.length === 0) {
                container.innerHTML = '<div class="text-muted text-center py-3">Nessun client attivo al momento.</div>';
                return;
            }

            const maxBytes = Math.max(...clients.map(c => c.total_bytes));

            clients.forEach(client => {
                const percentage = maxBytes > 0 ? (client.total_bytes / maxBytes) * 100 : 0;
                const displayName = client.client_name.replace(`${client.instance_name}_`, '');

                let timeStr = '-';
                if (client.connected_since && client.connected_since !== '-') {
                    const date = new Date(client.connected_since);
                    // Check if valid date
                    if (!isNaN(date.getTime())) {
                        timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    } else {
                        timeStr = client.connected_since;
                    }
                }

                const html = `
                    <div class="mb-3">
                        <div class="d-flex justify-content-between mb-1">
                            <div>
                                <span class="fw-bold">${displayName}</span>
                                <span class="text-muted small ms-2">(${client.instance_name})</span>
                            </div>
                            <div class="text-end">
                                <span class="fw-bold text-dark">${formatBytes(client.total_bytes)}</span>
                                <div class="text-muted small">Connesso: ${timeStr}</div>
                            </div>
                        </div>
                        <div class="progress progress-sm">
                            <div class="progress-bar bg-primary" style="width: ${percentage}%" role="progressbar"></div>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            });
        }
    } catch (e) {
        console.error('Error loading top clients:', e);
    }
}
