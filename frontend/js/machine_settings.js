// State variables
let machineFirewallRules = [];
let networkInterfaces = [];
let currentEditingInterface = null; // Stores the interface being edited
let sortableInstance = null; // To hold the SortableJS instance

const chainOptionsMap = {
    filter: ['INPUT', 'OUTPUT', 'FORWARD'],
    nat: ['PREROUTING', 'POSTROUTING', 'OUTPUT'],
    mangle: ['PREROUTING', 'INPUT', 'FORWARD', 'OUTPUT', 'POSTROUTING'],
    raw: ['PREROUTING', 'OUTPUT']
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    // Load data when tabs are shown (lazy loading)
    const firewallTab = document.querySelector('a[data-bs-toggle="tab"][href="#tab-machine-firewall"]');
    if (firewallTab) {
        firewallTab.addEventListener('shown.bs.tab', loadMachineFirewallRules);
    }

    const networkTab = document.querySelector('a[data-bs-toggle="tab"][href="#tab-network-interfaces"]');
    if (networkTab) {
        networkTab.addEventListener('shown.bs.tab', loadNetworkInterfaces);
    }

    // Load initial data for the active tab (Firewall is active by default)
    loadMachineFirewallRules();

    // HIDE UI ELEMENTS FOR ADMIN READ ONLY
    if (window.userRole === 'admin_readonly') {
        const btnAddRule = document.getElementById('btn-add-machine-rule');
        if (btnAddRule) btnAddRule.style.display = 'none';
    }

    // --- Popover and Preview for Add Machine Rule Modal ---
    const addRuleModal = document.getElementById('modal-add-machine-rule');
    if (addRuleModal) {
        // Initialize popovers
        const popoverTriggerList = [].slice.call(addRuleModal.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });

        const form = document.getElementById('addMachineRuleForm');

        const updateIptablesPreviewAddModal = () => {
            const previewCode = document.getElementById('iptables-preview-add');
            if (!form || !previewCode) return;

            const table = form.elements['table'].value;
            const chain = form.elements['chain'].value || (chainOptionsMap[table][0] || 'CHAIN');
            const action = form.elements['action'].value.toUpperCase();
            const protocol = form.elements['protocol'].value;
            const source = form.elements['source'].value;
            const destination = form.elements['destination'].value;
            const port = form.elements['port'].value;
            const inInterface = form.elements['in_interface'].value;
            const outInterface = form.elements['out_interface'].value;
            const state = form.elements['state'].value;
            const comment = form.elements['comment'].value;

            let command = ['iptables'];
            if (table !== 'filter') {
                command.push('-t', table);
            }
            command.push('-A', chain);

            if (inInterface) command.push('-i', inInterface);
            if (outInterface) command.push('-o', outInterface);
            if (source) command.push('-s', source);
            if (destination && !['SNAT', 'DNAT'].includes(action)) command.push('-d', destination);

            if (protocol) {
                command.push('-p', protocol);
                if (port && (protocol === 'tcp' || protocol === 'udp')) {
                    command.push('--dport', port);
                }
            }

            if (state) {
                command.push('-m', 'state', '--state', state);
            }

            if (comment) {
                command.push('-m', 'comment', '--comment', `"${comment}"`);
            }

            command.push('-j', action);

            if (action === 'SNAT' && destination) {
                command.push('--to-source', destination);
            }
            if (action === 'DNAT' && destination) {
                command.push('--to-destination', destination);
            }

            previewCode.textContent = command.join(' ');
        };

        const updateChainOptions = (form) => {
            const tableSelect = form.elements['table'];
            const chainSelect = form.elements['chain'];
            const selectedTable = tableSelect.value;

            const currentChain = chainSelect.value;
            chainSelect.innerHTML = '';

            const options = chainOptionsMap[selectedTable] || [];
            let isCurrentChainValid = false;
            options.forEach(optionValue => {
                const option = document.createElement('option');
                option.value = optionValue;
                option.textContent = optionValue;
                chainSelect.appendChild(option);
                if (optionValue === currentChain) {
                    isCurrentChainValid = true;
                }
            });

            if (isCurrentChainValid) {
                chainSelect.value = currentChain;
            }

            updateIptablesPreviewAddModal();
        };


        // Attach event listeners to all inputs within the form
        form.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('input', updateIptablesPreviewAddModal);
            input.addEventListener('change', updateIptablesPreviewAddModal);
        });

        // Add specific listener for table to update chain options
        form.elements['table'].addEventListener('change', () => updateChainOptions(form));

        // Set initial state on modal show
        addRuleModal.addEventListener('shown.bs.modal', () => {
            document.getElementById('addMachineRuleForm').reset();
            toggleMachinePortInput(null, 'add');
            updateChainOptions(form);
        });
    }
});


// --- Machine Firewall Rules ---

// --- Machine Firewall Rules ---

let sortableInstances = [];

async function loadMachineFirewallRules() {
    const bodies = [
        'machine-firewall-rules-input-body',
        'machine-firewall-rules-output-body',
        'machine-firewall-rules-forward-body',
        'machine-firewall-rules-other-body'
    ];

    bodies.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Caricamento regole...</td></tr>';
    });

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_machine_firewall_rules`);
        const result = await response.json();

        if (result.success) {
            machineFirewallRules = result.body;
            renderMachineFirewallRules();

            // Initialize SortableJS for all tables
            // Destroy old instances
            sortableInstances.forEach(inst => inst.destroy());
            sortableInstances = [];

            bodies.forEach(bodyId => {
                const el = document.getElementById(bodyId);
                if (el) {
                    const sortable = new Sortable(el, {
                        animation: 150,
                        ghostClass: 'sortable-ghost',
                        handle: '.ti-grip-vertical',
                        group: 'machine-firewall', // Allow dragging between tables (optional, but maybe useful?)
                        // actually, dragging between chains CHANGES the rule definition. 
                        // It's safer to DISABLE dragging between tables for now to avoid accidental Chain changes.
                        // group: null, 
                        onEnd: function (evt) {
                            // User reordered rows. We need to recalculate the global order.
                            recalculateAndSaveOrder();
                        }
                    });
                    sortableInstances.push(sortable);
                }
            });

        } else {
            showNotification('danger', 'Errore caricamento regole firewall macchina: ' + (result.body.detail || 'Sconosciuto'));
            bodies.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Errore caricamento.</td></tr>';
            });
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione caricando regole firewall macchina: ' + e.message);
        bodies.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Errore.</td></tr>';
        });
    }
}

function recalculateAndSaveOrder() {
    // We scrape the DOM to get the new order of IDs
    // We process tables in a specific order: Input, Output, Forward, Other.
    // This effectively groups rules by chain in the saved file/global order.

    const bodies = [
        'machine-firewall-rules-input-body',
        'machine-firewall-rules-output-body',
        'machine-firewall-rules-forward-body',
        'machine-firewall-rules-other-body'
    ];

    let newOrder = 0;
    const newGlobalList = []; // To update local state

    bodies.forEach(bodyId => {
        const tbody = document.getElementById(bodyId);
        if (!tbody) return;

        // Iterate over rows
        const rows = tbody.querySelectorAll('tr[data-id]');
        rows.forEach(row => {
            const id = row.getAttribute('data-id');
            const rule = machineFirewallRules.find(r => r.id === id);
            if (rule) {
                rule.order = newOrder++;
                newGlobalList.push(rule);
            }
        });
    });

    // Sort logic handled, now update backend
    machineFirewallRules = newGlobalList; // Update local state sorted
    applyMachineFirewallRules();
}

function renderMachineFirewallRules() {
    const bodies = {
        input: document.getElementById('machine-firewall-rules-input-body'),
        output: document.getElementById('machine-firewall-rules-output-body'),
        forward: document.getElementById('machine-firewall-rules-forward-body'),
        other: document.getElementById('machine-firewall-rules-other-body')
    };

    // Clear all
    Object.values(bodies).forEach(el => { if (el) el.innerHTML = ''; });

    if (machineFirewallRules.length === 0) {
        Object.values(bodies).forEach(el => { if (el) el.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Nessuna regola definita.</td></tr>'; });
        return;
    }

    // Sort by order first
    machineFirewallRules.sort((a, b) => a.order - b.order);

    machineFirewallRules.forEach((rule, index) => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-id', rule.id);

        let badgeClass = 'bg-secondary';
        if (rule.action === 'ACCEPT') badgeClass = 'bg-success';
        if (rule.action === 'DROP') badgeClass = 'bg-danger';
        if (rule.action === 'REJECT') badgeClass = 'bg-warning';
        if (rule.action === 'MASQUERADE') badgeClass = 'bg-info';

        // Determine destination table
        let targetBody = bodies.other;
        if (rule.table === 'filter' || !rule.table) {
            if (rule.chain === 'INPUT' || rule.chain === 'FW_INPUT') targetBody = bodies.input;
            else if (rule.chain === 'OUTPUT' || rule.chain === 'FW_OUTPUT') targetBody = bodies.output;
            else if (rule.chain === 'FORWARD' || rule.chain === 'FW_FORWARD') targetBody = bodies.forward;
        }

        // Columns differ slightly for Input/Output/Forward/Other? 
        // We simplified the generic renderer in previous version, but now HTML tables have different headers.
        // We need to render matching TD structure.

        let innerHTML = `<td class="w-1" style="cursor: grab;"><i class="ti ti-grip-vertical"></i></td>`;
        innerHTML += `<td><span class="badge ${badgeClass}">${rule.action}</span></td>`;

        if (targetBody === bodies.other) {
            innerHTML += `<td>${rule.table || 'filter'}</td>`;
            innerHTML += `<td>${rule.chain}</td>`;
            innerHTML += `<td>${rule.protocol ? rule.protocol.toUpperCase() : 'ANY'}</td>`;
            innerHTML += `<td><code>${rule.source || 'ANY'}</code></td>`;
            innerHTML += `<td><code>${rule.destination || 'ANY'}</code></td>`;
            innerHTML += `<td>${rule.port || '*'}</td>`;
            innerHTML += `<td>${rule.comment || ''}</td>`;
        } else {
            innerHTML += `<td>${rule.protocol ? rule.protocol.toUpperCase() : 'ANY'}</td>`;
            innerHTML += `<td><code>${rule.source || 'ANY'}</code></td>`;
            innerHTML += `<td><code>${rule.destination || 'ANY'}</code></td>`;
            innerHTML += `<td>${rule.port || '*'}</td>`;

            if (targetBody === bodies.input) {
                innerHTML += `<td>${rule.in_interface || '*'}</td>`;
            } else if (targetBody === bodies.output) {
                innerHTML += `<td>${rule.out_interface || '*'}</td>`;
            } else if (targetBody === bodies.forward) {
                innerHTML += `<td>${rule.in_interface || '*'}</td>`;
                innerHTML += `<td>${rule.out_interface || '*'}</td>`;
            }
            innerHTML += `<td>${rule.comment || ''}</td>`;
        }

        if (window.userRole !== 'admin_readonly') {
            innerHTML += `
            <td class="text-end">
                <button class="btn btn-sm btn-ghost-primary" onclick="openEditMachineRuleModal('${rule.id}')" title="Modifica">
                    <i class="ti ti-edit"></i>
                </button>
                <button class="btn btn-sm btn-ghost-danger" onclick="confirmDeleteMachineRule('${rule.id}')" title="Elimina">
                    <i class="ti ti-trash"></i>
                </button>
            </td>
        `;
        } else {
            innerHTML += `<td></td>`;
        }

        tr.innerHTML = innerHTML;
        if (targetBody) targetBody.appendChild(tr);
    });

    // Check if any body is empty and add placeholder
    Object.values(bodies).forEach(el => {
        if (el && el.children.length === 0) {
            const colSpan = (el === bodies.other || el === bodies.forward) ? 10 : 9;
            el.innerHTML = `<tr><td colspan="${colSpan}" class="text-center text-muted">Nessuna regola in questa sezione.</td></tr>`;
        }
    });
}

async function addMachineFirewallRule() {
    const form = document.getElementById('addMachineRuleForm');
    const ruleData = {
        chain: form.elements['chain'].value,
        action: form.elements['action'].value,
        protocol: form.elements['protocol'].value || null,
        source: form.elements['source'].value || null,
        destination: form.elements['destination'].value || null,
        port: form.elements['port'].value || null,
        in_interface: form.elements['in_interface'].value || null,
        out_interface: form.elements['out_interface'].value || null,
        state: form.elements['state'].value || null,
        comment: form.elements['comment'].value || null,
        table: form.elements['table'].value
    };

    // Basic validation
    if (!ruleData.chain || !ruleData.action) {
        showNotification('danger', 'Chain e Azione sono campi obbligatori.');
        return;
    }

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=add_machine_firewall_rule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ruleData)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Regola firewall globale aggiunta con successo.');
            bootstrap.Modal.getInstance(document.getElementById('modal-add-machine-rule')).hide();
            await loadMachineFirewallRules();
        } else {
            showNotification('danger', 'Errore aggiunta regola: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

function confirmDeleteMachineRule(ruleId) {
    const rule = machineFirewallRules.find(r => r.id === ruleId);
    if (!rule) {
        showNotification('danger', 'Regola non trovata per l\'eliminazione.');
        return;
    }

    let badgeClass = 'bg-secondary';
    if (rule.action === 'ACCEPT') badgeClass = 'bg-success';
    if (rule.action === 'DROP') badgeClass = 'bg-danger';
    if (rule.action === 'REJECT') badgeClass = 'bg-warning';
    if (rule.action === 'MASQUERADE') badgeClass = 'bg-info';

    const ruleDescriptionHtml = `
        <strong>Azione:</strong> <span class="badge ${badgeClass}">${rule.action}</span><br>
        <strong>Chain:</strong> ${rule.chain}<br>
        <strong>Protocollo:</strong> ${rule.protocol ? rule.protocol.toUpperCase() : 'ANY'}<br>
        <strong>Destinazione:</strong> <code>${rule.destination || 'ANY'}</code><br>
        <strong>Porta:</strong> ${rule.port || '*'}<br>
        <strong>Sorgente:</strong> <code>${rule.source || 'ANY'}</code>
    `;

    document.getElementById('delete-machine-rule-summary').innerHTML = ruleDescriptionHtml;
    document.getElementById('confirm-delete-machine-rule-button').onclick = () => performDeleteMachineRule(ruleId);
    new bootstrap.Modal(document.getElementById('modal-confirm-delete-machine-rule')).show();
}

async function performDeleteMachineRule(ruleId) {
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=delete_machine_firewall_rule&rule_id=${encodeURIComponent(ruleId)}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Regola firewall globale eliminata.');
            await loadMachineFirewallRules();
        } else {
            showNotification('danger', 'Errore eliminazione regola: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

async function applyMachineFirewallRules() {
    const orders = machineFirewallRules.map(rule => ({
        id: rule.id,
        order: rule.order
    }));

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=apply_machine_firewall_rules`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orders)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Modifiche alle regole firewall globali applicate con successo.');
        } else {
            showNotification('danger', 'Errore applicazione regole: ' + (result.body.detail || 'Sconosciuto'));
            // If applying fails, reload the state from the server to prevent UI inconsistencies
            await loadMachineFirewallRules();
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
        await loadMachineFirewallRules();
    }
}


function toggleMachinePortInput(protocol, modalType) {
    const portContainer = document.getElementById(`machine-port-container-${modalType}`);
    if (!portContainer) return;

    if (protocol === 'tcp' || protocol === 'udp') {
        portContainer.style.display = 'block';
    } else {
        portContainer.style.display = 'none';
        portContainer.querySelector('input[name="port"]').value = ''; // Clear value when hidden
    }
}


// --- Network Interfaces ---

async function loadNetworkInterfaces() {
    const tbody = document.getElementById('network-interfaces-table-body');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Caricamento interfacce...</td></tr>';

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_machine_network_interfaces`);
        const result = await response.json();

        if (result.success) {
            networkInterfaces = result.body;
            renderNetworkInterfaces();
        } else {
            showNotification('danger', 'Errore caricamento interfacce di rete: ' + (result.body.detail || 'Sconosciuto'));
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Errore caricamento.</td></tr>';
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione caricando interfacce di rete: ' + e.message);
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">Errore di connessione.</td></tr>';
    }
}

function renderNetworkInterfaces() {
    const tbody = document.getElementById('network-interfaces-table-body');
    tbody.innerHTML = '';

    if (networkInterfaces.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Nessuna interfaccia di rete trovata.</td></tr>';
        return;
    }

    networkInterfaces.forEach(iface => {
        const tr = document.createElement('tr');

        let ipDisplay = 'N/A';
        let cidrDisplay = 'N/A';
        let netmaskDisplay = 'N/A';

        if (iface.configured_ips && iface.configured_ips.length > 0) {
            const primaryIp = iface.configured_ips[0];
            ipDisplay = primaryIp.ip;
            cidrDisplay = primaryIp.cidr;
            netmaskDisplay = primaryIp.netmask;
            if (iface.configured_ips.length > 1) {
                ipDisplay += ` (+${iface.configured_ips.length - 1})`;
            }
        }

        tr.innerHTML = `
            <td>${iface.name}</td>
            <td>${iface.mac_address || 'N/A'}</td>
            <td><span class="badge bg-${iface.link_status === 'UP' ? 'success' : 'danger'}">${iface.link_status}</span></td>
            <td>${ipDisplay}</td>
            <td>${cidrDisplay}</td>
            <td>${netmaskDisplay}</td>
            <td class="text-end">
                ${window.userRole !== 'admin_readonly' ? `
                <button class="btn btn-sm btn-primary" onclick="openEditNetworkInterfaceModal('${iface.name}')">
                    <i class="ti ti-edit"></i> Configura
                </button>` : ''}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function openEditNetworkInterfaceModal(interfaceName) {
    currentEditingInterface = networkInterfaces.find(iface => iface.name === interfaceName);
    if (!currentEditingInterface) {
        showNotification('danger', `Interfaccia ${interfaceName} non trovata.`);
        return;
    }

    document.getElementById('edit-interface-name').textContent = currentEditingInterface.name;
    document.getElementById('edit-interface-hidden-name').value = currentEditingInterface.name;
    document.getElementById('edit-interface-mac').textContent = currentEditingInterface.mac_address || 'N/A';
    document.getElementById('edit-interface-link-status').textContent = currentEditingInterface.link_status || 'UNKNOWN';

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_machine_network_interface_config&interface_name=${encodeURIComponent(interfaceName)}`);
        const result = await response.json();

        if (result.success) {
            const config = result.body;

            let ipMethod = 'dhcp';
            if (config && config.dhcp4 === false && config.addresses && config.addresses.length > 0) {
                ipMethod = 'static';
            } else if (config && config.dhcp4 === false && (!config.addresses || config.addresses.length === 0)) {
                ipMethod = 'none';
            }
            document.getElementById('edit-interface-ip-method').value = ipMethod;

            const ipAddressesContainer = document.getElementById('static-ip-addresses-container');
            ipAddressesContainer.innerHTML = '';
            if (ipMethod === 'static' && config.addresses && config.addresses.length > 0) {
                config.addresses.forEach(addr => addIpAddressField(addr));
            } else {
                addIpAddressField();
            }

            document.getElementById('edit-interface-gateway').value = (config.routes && config.routes.length > 0) ? config.routes[0].via : '';
            document.getElementById('edit-interface-nameservers').value = (config.nameservers && config.nameservers.addresses) ? config.nameservers.addresses.join(', ') : '';

            toggleIpConfigFields(ipMethod);
            new bootstrap.Modal(document.getElementById('modal-edit-network-interface')).show();

        } else {
            showNotification('danger', 'Errore caricamento configurazione Netplan: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione caricando configurazione Netplan: ' + e.message);
    }
}

function toggleIpConfigFields(method) {
    const staticIpFields = document.getElementById('static-ip-fields');
    if (method === 'static') {
        staticIpFields.style.display = 'block';
    } else {
        staticIpFields.style.display = 'none';
    }
}

function addIpAddressField(ipCidr = '') {
    const container = document.getElementById('static-ip-addresses-container');
    const div = document.createElement('div');
    div.className = 'input-group mb-2';
    div.innerHTML = `
        <input type="text" class="form-control" placeholder="E.g., 192.168.1.10/24" value="${ipCidr}">
        <button type="button" class="btn btn-outline-danger" onclick="this.closest('.input-group').remove()">
            <i class="ti ti-trash"></i>
        </button>
    `;
    container.appendChild(div);
}

async function saveNetworkInterfaceConfig() {
    const interfaceName = document.getElementById('edit-interface-hidden-name').value;
    const ipMethod = document.getElementById('edit-interface-ip-method').value;

    let netplanConfig = {};

    if (ipMethod === 'dhcp') {
        netplanConfig = { dhcp4: true };
    } else if (ipMethod === 'static') {
        const ipAddresses = [];
        document.querySelectorAll('#static-ip-addresses-container input').forEach(input => {
            const val = input.value.trim();
            if (val) {
                if (!/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/.test(val)) {
                    showNotification('danger', `Indirizzo IP non valido: ${val}`);
                    return;
                }
                ipAddresses.push(val);
            }
        });

        const gateway = document.getElementById('edit-interface-gateway').value.trim();
        const nameservers = document.getElementById('edit-interface-nameservers').value.trim();
        let dnsConfig = {};
        if (nameservers) {
            dnsConfig = { addresses: nameservers.split(',').map(s => s.trim()) };
        }

        netplanConfig = {
            dhcp4: false,
            addresses: ipAddresses,
        };
        if (gateway) {
            netplanConfig.routes = [{ to: '0.0.0.0/0', via: gateway }];
        }
        if (Object.keys(dnsConfig).length > 0) {
            netplanConfig.nameservers = dnsConfig;
        }

    } else if (ipMethod === 'none') {
        netplanConfig = { dhcp4: false, addresses: [], routes: [], nameservers: {} };
    }

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=update_machine_network_interface_config&interface_name=${encodeURIComponent(interfaceName)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(netplanConfig)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Configurazione interfaccia salvata e applicata con successo.');
            bootstrap.Modal.getInstance(document.getElementById('modal-edit-network-interface')).hide();
            loadNetworkInterfaces();
        } else {
            showNotification('danger', 'Errore salvataggio configurazione: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// Global notification function (assuming it's defined in header or a common utils)
// function showNotification(type, message) { ... }

function openEditMachineRuleModal(ruleId) {
    const rule = machineFirewallRules.find(r => r.id === ruleId);
    if (!rule) {
        showNotification('danger', 'Regola non trovata per la modifica.');
        return;
    }

    const form = document.getElementById('editMachineRuleForm');
    form.elements['id'].value = rule.id;
    form.elements['table'].value = rule.table;
    form.elements['action'].value = rule.action;
    form.elements['protocol'].value = rule.protocol || '';
    form.elements['source'].value = rule.source || '';
    form.elements['destination'].value = rule.destination || '';
    form.elements['port'].value = rule.port || '';
    form.elements['in_interface'].value = rule.in_interface || '';
    form.elements['out_interface'].value = rule.out_interface || '';
    form.elements['state'].value = rule.state || '';
    form.elements['comment'].value = rule.comment || '';

    // Update chain options for the specific table and select the correct one
    // Verify casing
    const selectedTable = (rule.table || 'filter').toLowerCase();
    const selectedChain = (rule.chain || '').toUpperCase();

    // Populate Chain Select
    const chainSelect = form.elements['chain'];
    chainSelect.innerHTML = '';

    const options = chainOptionsMap[selectedTable] || [];
    options.forEach(optionValue => {
        const option = document.createElement('option');
        option.value = optionValue;
        option.textContent = optionValue;
        if (optionValue === selectedChain) {
            option.selected = true;
        }
        chainSelect.appendChild(option);
    });

    // Add listener for table change to update chains dynamically in Edit Modal too
    const tableSelect = form.elements['table'];
    // Remove old listener if any (to avoid duplicates if modal opened multiple times, though simple assignment overwrites 'onchange' property, addEventListener stacks. 
    // Best to set onchange attribute or handle in init.
    // Let's set it via onchange property for simplicity here to avoid stacking
    tableSelect.onchange = function () {
        const newTable = this.value;
        const newOptions = chainOptionsMap[newTable] || [];
        chainSelect.innerHTML = '';
        newOptions.forEach(opt => {
            const el = document.createElement('option');
            el.value = opt;
            el.textContent = opt;
            chainSelect.appendChild(el);
        });
        updateIptablesPreviewEditModal();
    };


    toggleMachinePortInput(rule.protocol, 'edit');
    updateIptablesPreviewEditModal(); // Set initial preview

    new bootstrap.Modal(document.getElementById('modal-edit-machine-rule')).show();
}

async function updateMachineFirewallRule() {
    const form = document.getElementById('editMachineRuleForm');
    const ruleId = form.elements['id'].value;

    const ruleData = {
        id: ruleId,
        chain: form.elements['chain'].value,
        action: form.elements['action'].value,
        protocol: form.elements['protocol'].value || null,
        source: form.elements['source'].value || null,
        destination: form.elements['destination'].value || null,
        port: form.elements['port'].value || null,
        in_interface: form.elements['in_interface'].value || null,
        out_interface: form.elements['out_interface'].value || null,
        state: form.elements['state'].value || null,
        comment: form.elements['comment'].value || null,
        table: form.elements['table'].value
    };

    if (!ruleData.chain || !ruleData.action) {
        showNotification('danger', 'Chain e Azione sono campi obbligatori.');
        return;
    }

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=update_machine_firewall_rule&rule_id=${encodeURIComponent(ruleId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ruleData)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Regola firewall aggiornata con successo.');
            bootstrap.Modal.getInstance(document.getElementById('modal-edit-machine-rule')).hide();
            await loadMachineFirewallRules();
        } else {
            showNotification('danger', 'Errore aggiornamento regola: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// --- Preview and dynamic inputs for Edit Modal ---
document.addEventListener('DOMContentLoaded', () => {
    const editRuleModal = document.getElementById('modal-edit-machine-rule');
    if (editRuleModal) {
        const form = document.getElementById('editMachineRuleForm');
        form.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('input', updateIptablesPreviewEditModal);
            input.addEventListener('change', updateIptablesPreviewEditModal);
        });
        form.elements['table'].addEventListener('change', () => {
            // Get the correct chain dropdown for the edit modal
            const chainSelect = form.elements['chain'];
            const selectedTable = form.elements['table'].value;

            chainSelect.innerHTML = '';
            const options = chainOptionsMap[selectedTable] || [];
            options.forEach(optionValue => {
                const option = document.createElement('option');
                option.value = optionValue;
                option.textContent = optionValue;
                chainSelect.appendChild(option);
            });
            updateIptablesPreviewEditModal();
        });
    }
});

function updateIptablesPreviewEditModal() {
    const form = document.getElementById('editMachineRuleForm');
    const previewCode = document.getElementById('iptables-preview-edit');
    if (!form || !previewCode) return;

    const table = form.elements['table'].value;
    const chain = form.elements['chain'].value || 'CHAIN';
    const action = form.elements['action'].value.toUpperCase();
    const protocol = form.elements['protocol'].value;
    const source = form.elements['source'].value;
    const destination = form.elements['destination'].value;
    const port = form.elements['port'].value;
    const inInterface = form.elements['in_interface'].value;
    const outInterface = form.elements['out_interface'].value;
    const state = form.elements['state'].value;
    const comment = form.elements['comment'].value;

    let command = ['iptables'];
    if (table !== 'filter') {
        command.push('-t', table);
    }
    // For preview, we show -A, but the backend will use -I for ordering
    command.push('-A', chain);

    if (inInterface) command.push('-i', inInterface);
    if (outInterface) command.push('-o', outInterface);
    if (source) command.push('-s', source);
    if (destination && !['SNAT', 'DNAT'].includes(action)) command.push('-d', destination);

    if (protocol) {
        command.push('-p', protocol);
        if (port && (protocol === 'tcp' || protocol === 'udp')) {
            command.push('--dport', port);
        }
    }

    if (state) {
        command.push('-m', 'state', '--state', state);
    }

    if (comment) {
        command.push('-m', 'comment', '--comment', `"${comment}"`);
    }

    command.push('-j', action);

    if (action === 'SNAT' && destination) {
        command.push('--to-source', destination);
    }
    if (action === 'DNAT' && destination) {
        command.push('--to-destination', destination);
    }

    previewCode.textContent = command.join(' ');
}

function openEditMachineRuleModal(ruleId) {
    const rule = machineFirewallRules.find(r => r.id === ruleId);
    if (!rule) {
        showNotification('danger', 'Regola non trovata per la modifica.');
        return;
    }

    const form = document.getElementById('editMachineRuleForm');
    form.elements['id'].value = rule.id;
    form.elements['table'].value = rule.table;
    form.elements['action'].value = rule.action;
    form.elements['protocol'].value = rule.protocol || '';
    form.elements['source'].value = rule.source || '';
    form.elements['destination'].value = rule.destination || '';
    form.elements['port'].value = rule.port || '';
    form.elements['in_interface'].value = rule.in_interface || '';
    form.elements['out_interface'].value = rule.out_interface || '';
    form.elements['state'].value = rule.state || '';
    form.elements['comment'].value = rule.comment || '';

    // Update chain options for the specific table and select the correct one
    const chainSelect = form.elements['chain'];
    const selectedTable = rule.table;
    chainSelect.innerHTML = '';
    const options = chainOptionsMap[selectedTable] || [];
    options.forEach(optionValue => {
        const option = document.createElement('option');
        option.value = optionValue;
        option.textContent = optionValue;
        if (optionValue === rule.chain) {
            option.selected = true;
        }
        chainSelect.appendChild(option);
    });

    toggleMachinePortInput(rule.protocol, 'edit');
    updateIptablesPreviewEditModal(); // Set initial preview

    new bootstrap.Modal(document.getElementById('modal-edit-machine-rule')).show();
}

async function updateMachineFirewallRule() {
    const form = document.getElementById('editMachineRuleForm');
    const ruleId = form.elements['id'].value;

    const ruleData = {
        id: ruleId,
        chain: form.elements['chain'].value,
        action: form.elements['action'].value,
        protocol: form.elements['protocol'].value || null,
        source: form.elements['source'].value || null,
        destination: form.elements['destination'].value || null,
        port: form.elements['port'].value || null,
        in_interface: form.elements['in_interface'].value || null,
        out_interface: form.elements['out_interface'].value || null,
        state: form.elements['state'].value || null,
        comment: form.elements['comment'].value || null,
        table: form.elements['table'].value
    };

    if (!ruleData.chain || !ruleData.action) {
        showNotification('danger', 'Chain e Azione sono campi obbligatori.');
        return;
    }

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=update_machine_firewall_rule&rule_id=${encodeURIComponent(ruleId)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ruleData)
        });
        const result = await response.json();

        if (result.success) {
            showNotification('success', 'Regola firewall aggiornata con successo.');
            bootstrap.Modal.getInstance(document.getElementById('modal-edit-machine-rule')).hide();
            loadMachineFirewallRules();
        } else {
            showNotification('danger', 'Errore aggiornamento regola: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}

// --- Preview and dynamic inputs for Edit Modal ---
document.addEventListener('DOMContentLoaded', () => {
    const editRuleModal = document.getElementById('modal-edit-machine-rule');
    if (editRuleModal) {
        const form = document.getElementById('editMachineRuleForm');
        form.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('input', updateIptablesPreviewEditModal);
            input.addEventListener('change', updateIptablesPreviewEditModal);
        });
        form.elements['table'].addEventListener('change', () => {
            // Get the correct chain dropdown for the edit modal
            const chainSelect = form.elements['chain'];
            const selectedTable = form.elements['table'].value;

            chainSelect.innerHTML = '';
            const options = chainOptionsMap[selectedTable] || [];
            options.forEach(optionValue => {
                const option = document.createElement('option');
                option.value = optionValue;
                option.textContent = optionValue;
                chainSelect.appendChild(option);
            });
            updateIptablesPreviewEditModal();
        });
    }
});

function updateIptablesPreviewEditModal() {
    const form = document.getElementById('editMachineRuleForm');
    const previewCode = document.getElementById('iptables-preview-edit');
    if (!form || !previewCode) return;

    const table = form.elements['table'].value;
    const chain = form.elements['chain'].value || 'CHAIN';
    const action = form.elements['action'].value.toUpperCase();
    const protocol = form.elements['protocol'].value;
    const source = form.elements['source'].value;
    const destination = form.elements['destination'].value;
    const port = form.elements['port'].value;
    const inInterface = form.elements['in_interface'].value;
    const outInterface = form.elements['out_interface'].value;
    const state = form.elements['state'].value;
    const comment = form.elements['comment'].value;

    let command = ['iptables'];
    if (table !== 'filter') {
        command.push('-t', table);
    }
    // For preview, we show -A, but the backend will use -I for ordering
    command.push('-A', chain);

    if (inInterface) command.push('-i', inInterface);
    if (outInterface) command.push('-o', outInterface);
    if (source) command.push('-s', source);
    if (destination && !['SNAT', 'DNAT'].includes(action)) command.push('-d', destination);

    if (protocol) {
        command.push('-p', protocol);
        if (port && (protocol === 'tcp' || protocol === 'udp')) {
            command.push('--dport', port);
        }
    }

    if (state) {
        command.push('-m', 'state', '--state', state);
    }

    if (comment) {
        command.push('-m', 'comment', '--comment', `"${comment}"`);
    }

    command.push('-j', action);

    if (action === 'SNAT' && destination) {
        command.push('--to-source', destination);
    }
    if (action === 'DNAT' && destination) {
        command.push('--to-destination', destination);
    }

    previewCode.textContent = command.join(' ');
}

// Override original toggle function to handle both modals
function toggleMachinePortInput(protocol, modalType) {
    const portContainer = document.getElementById(`machine-port-container-${modalType}`);
    if (!portContainer) return;

    if (protocol === 'tcp' || protocol === 'udp') {
        portContainer.style.display = 'block';
    } else {
        portContainer.style.display = 'none';
        portContainer.querySelector('input[name="port"]').value = ''; // Clear value when hidden
    }
}

