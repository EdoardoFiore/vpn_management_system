// State (Firewall specific)
let allGroups = [];
let currentGroupId = null;
let availableClientData = []; // Store client info for selector

// Unlike standalone, we wait for the main instance logic to initialize us or checking tab
// But for simplicity, we can just expose loadGroups and call it when tab is shown, 
// or call it after loadInstanceDetails finishes.

// Hook into the tab switch for lazy loading?
document.addEventListener('DOMContentLoaded', () => {
    const tabEl = document.querySelector('a[data-bs-toggle="tab"][href="#tab-firewall"]');
    if (tabEl) {
        tabEl.addEventListener('shown.bs.tab', function (event) {
            if (currentInstance) {
                loadGroups();
            }
        });
    }
});

// --- Groups Management ---

async function loadGroups() {
    if (!currentInstance) return;

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_groups&instance_id=${currentInstance.id}`);
        const result = await response.json();

        if (result.success) {
            allGroups = result.body;
            renderGroupsList();

            // Refreshes the active view if a group is selected
            if (currentGroupId) {
                // Check if group still exists
                const group = allGroups.find(g => g.id === currentGroupId);
                if (group) {
                    selectGroup(currentGroupId);
                } else {
                    // Group was deleted remotely? Deselect
                    currentGroupId = null;
                    document.getElementById('group-details-container').style.display = 'none';
                    document.getElementById('no-group-selected').style.display = 'block';
                }
            }
        } else {
            console.error(result.body.detail);
        }
    } catch (e) {
        console.error("Error loading groups:", e);
    }
}

function renderGroupsList() {
    const list = document.getElementById('groups-list');
    list.innerHTML = '';

    if (allGroups.length === 0) {
        list.innerHTML = '<div class="list-group-item text-muted text-center">Nessun gruppo creato.</div>';
        return;
    }

    allGroups.forEach(group => {
        const item = document.createElement('a');
        item.href = '#';
        item.className = `list-group-item list-group-item-action ${group.id === currentGroupId ? 'active' : ''}`;
        item.onclick = (e) => {
            e.preventDefault();
            selectGroup(group.id);
        };
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>${group.name}</span>
                <span class="badge bg-secondary rounded-pill">${group.members.length}</span>
            </div>
            <small class="text-muted d-block text-truncate">${group.description}</small>
        `;
        list.appendChild(item);
    });
}

async function createGroup() {
    if (!currentInstance) return;

    const name = document.getElementById('group-name-input').value;
    const desc = document.getElementById('group-desc-input').value;

    if (!name) return alert("Inserisci un nome.");

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'create_group',
            name: name,
            instance_id: currentInstance.id, // Inject Instance ID
            description: desc
        })
    });
    const result = await response.json();

    if (result.success) {
        bootstrap.Modal.getInstance(document.getElementById('modal-create-group')).hide();
        document.getElementById('group-name-input').value = '';
        loadGroups();
    } else {
        alert("Errore: " + result.body.detail);
    }
}

async function deleteCurrentGroup() {
    if (!currentGroupId) return;
    if (!confirm("Sei sicuro? Questo rimuoverà tutte le regole e rilascerà gli IP statici dei membri.")) return;

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `action=delete_group&group_id=${encodeURIComponent(currentGroupId)}`
    });

    const result = await response.json();
    if (result.success) {
        currentGroupId = null;
        document.getElementById('group-details-container').style.display = 'none';
        document.getElementById('no-group-selected').style.display = 'block';
        loadGroups();
    } else {
        alert("Errore: " + result.body.detail);
    }
}

function selectGroup(groupId) {
    currentGroupId = groupId;
    renderGroupsList();

    const group = allGroups.find(g => g.id === groupId);
    if (group) {
        document.getElementById('selected-group-title').textContent = `Membri di: ${group.name}`;
        document.getElementById('group-details-container').style.display = 'block';
        document.getElementById('no-group-selected').style.display = 'none';
        renderMembers(group);
        loadRules(groupId);
    }
}

// --- Members Management ---

function renderMembers(group) {
    const tbody = document.getElementById('members-table-body');
    tbody.innerHTML = '';

    if (group.members.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Nessun membro.</td></tr>';
        return;
    }

    group.members.forEach(memberId => {
        // CLEANUP NAME: Remove instance prefix for display
        // We know memberId is "{instance}_{client}"
        let displayUser = memberId;
        if (currentInstance && memberId.startsWith(currentInstance.name + "_")) {
            displayUser = memberId.replace(currentInstance.name + "_", "");
        }

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${displayUser}</td>
            <td>
                <button class="btn btn-sm btn-ghost-danger" onclick="removeMember('${memberId}')">
                    <i class="ti ti-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function openAddMemberModal() {
    if (!currentInstance) return;

    const modal = new bootstrap.Modal(document.getElementById('modal-add-member'));
    modal.show();

    const select = document.getElementById('member-select');
    select.innerHTML = '<option value="">Caricamento...</option>';
    select.disabled = true;

    try {
        // 1. Get all members already in any group for this instance
        const existingMembers = new Set();
        allGroups.filter(g => g.instance_id === currentInstance.id)
                 .forEach(g => {
                     g.members.forEach(m => existingMembers.add(m));
                 });

        // 2. Load available clients from the API
        const clientResp = await fetch(`${API_AJAX_HANDLER}?action=get_clients&instance_id=${currentInstance.id}`);
        const clientData = await clientResp.json();
        const clients = clientData.body || [];

        availableClientData = [];
        select.innerHTML = '<option value="">Seleziona un utente...</option>';
        let optionsAdded = 0;

        // 3. Populate dropdown, excluding existing members
        clients.forEach(c => {
            const clientIdentifier = c.name; // The name from get_clients is the full identifier
            
            if (existingMembers.has(clientIdentifier)) {
                return; // Skip this client, it's already in a group
            }
            
            const displayName = clientIdentifier.replace(`${currentInstance.name}_`, "");

            availableClientData.push({
                id: clientIdentifier,
                client_name: displayName,
                instance_name: currentInstance.name,
                subnet: currentInstance.subnet,
                display: displayName
            });

            const opt = document.createElement('option');
            opt.value = clientIdentifier;
            opt.textContent = displayName;
            select.appendChild(opt);
            optionsAdded++;
        });
        
        if (optionsAdded === 0) {
            select.innerHTML = '<option value="" disabled>Nessun client disponibile o tutti già in un gruppo.</option>';
            select.disabled = true;
        } else {
            select.disabled = false;
        }

    } catch (e) {
        select.innerHTML = '<option value="">Errore caricamento</option>';
        console.error(e);
    }
}

async function addMember() {
    const select = document.getElementById('member-select');
    const clientId = select.value;
    if (!clientId) return;

    const clientData = availableClientData.find(c => c.id === clientId);
    if (!clientData) return;

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'add_group_member',
            group_id: currentGroupId,
            client_identifier: clientId,
            subnet_info: {
                instance_name: clientData.instance_name,
                subnet: clientData.subnet
            }
        })
    });

    const result = await response.json();
    if (result.success) {
        bootstrap.Modal.getInstance(document.getElementById('modal-add-member')).hide();
        loadGroups(); // Reload to refresh member list
    } else {
        alert("Errore: " + result.body.detail);
    }
}

async function removeMember(clientId) {
    if (!currentInstance) return;
    if (!confirm(`Rimuovere utente dal gruppo?`)) return;

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'remove_group_member',
            group_id: currentGroupId,
            client_identifier: clientId,
            instance_name: currentInstance.name // We know it matches
        })
    });

    const result = await response.json();
    if (result.success) {
        loadGroups();
    } else {
        alert("Errore: " + result.body.detail);
    }
}

// --- Rules Management ---

async function loadRules(groupId) {
    const tbody = document.getElementById('rules-table-body');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Caricamento...</td></tr>';

    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_rules&group_id=${groupId}`);
        const result = await response.json();

        if (result.success) {
            renderRules(result.body);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Errore caricamento regole.</td></tr>';
        }
    } catch (e) {
        console.error(e);
    }
}

function renderRules(rules) {
    const tbody = document.getElementById('rules-table-body');
    tbody.innerHTML = '';

    if (rules.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nessuna regola definita.</td></tr>';
        return;
    }

    rules.sort((a, b) => a.order - b.order);

    rules.forEach((rule, index) => {
        const tr = document.createElement('tr');

        let badgeClass = 'bg-secondary';
        if (rule.action === 'ACCEPT') badgeClass = 'bg-success';
        if (rule.action === 'DROP') badgeClass = 'bg-danger';

        tr.innerHTML = `
            <td>
                <div class="btn-group-vertical btn-group-sm">
                    <button class="btn btn-icon" onclick="moveRule('${rule.id}', -1)" ${index === 0 ? 'disabled' : ''}>
                        <i class="ti ti-chevron-up"></i>
                    </button>
                    <button class="btn btn-icon" onclick="moveRule('${rule.id}', 1)" ${index === rules.length - 1 ? 'disabled' : ''}>
                        <i class="ti ti-chevron-down"></i>
                    </button>
                </div>
            </td>
            <td><span class="badge ${badgeClass}">${rule.action}</span></td>
            <td>${rule.protocol.toUpperCase()}</td>
            <td><code>${rule.destination}</code></td>
            <td>${rule.port || '*'}</td>
            <td class="text-end">
                <button class="btn btn-sm btn-ghost-danger" onclick="deleteRule('${rule.id}')">
                    <i class="ti ti-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Store current rules to handle reordering logic locally before saving
    window.currentRules = rules;
}

function togglePortInput() {
    const proto = document.getElementById('rule-proto').value;
    const portContainer = document.getElementById('port-container');
    if (proto === 'tcp' || proto === 'udp') {
        portContainer.style.display = 'block';
    } else {
        portContainer.style.display = 'none';
        document.getElementById('rule-port').value = '';
    }
}

async function createRule() {
    const action = document.getElementById('rule-action').value;
    const proto = document.getElementById('rule-proto').value;
    const destInput = document.getElementById('rule-dest');
    const portInput = document.getElementById('rule-port');
    const descInput = document.getElementById('rule-desc');

    // --- VALIDATION ---
    let isValid = true;
    const dest = destInput.value.trim();
    let port = portInput.value.trim(); // Use let to allow modification

    // Reset validation
    destInput.classList.remove('is-invalid');
    portInput.classList.remove('is-invalid');

    const cidrRegex = /^([0-9]{1,3}\.){3}[0-9]{1,3}(\/([0-9]|[1-2][0-9]|3[0-2]))?$/;
    const portRegex = /^\d{1,5}$/;
    const portRangeRegex = /^\d{1,5}:\d{1,5}$/;

    if (dest === '' || (!cidrRegex.test(dest) && dest.toLowerCase() !== 'any')) {
        isValid = false;
        destInput.classList.add('is-invalid');
    }

    if (port !== '' && (proto === 'tcp' || proto === 'udp')) {
        if (portRegex.test(port)) {
            const portNum = parseInt(port, 10);
            if (portNum < 1 || portNum > 65535) {
                isValid = false;
                portInput.classList.add('is-invalid');
            }
        } else if (portRangeRegex.test(port)) {
            const [start, end] = port.split(':').map(p => parseInt(p, 10));
            if (start < 1 || start > 65535 || end < 1 || end > 65535 || start >= end) {
                isValid = false;
                portInput.classList.add('is-invalid');
            }
        } else {
            isValid = false;
            portInput.classList.add('is-invalid');
        }
    } else if (port !== '' && (proto !== 'tcp' && proto !== 'udp')) {
        isValid = false;
        portInput.classList.add('is-invalid');
    }

    if (!isValid) {
        showNotification('danger', 'Uno o più campi della regola non sono validi.');
        return;
    }
    // --- END VALIDATION ---

    // Sanitize payload: ensure port is null for non-TCP/UDP protocols
    if (proto !== 'tcp' && proto !== 'udp') {
        port = null;
    }

    const response = await fetch(`${API_AJAX_HANDLER}?action=create_rule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            group_id: currentGroupId,
            action: action,
            protocol: proto,
            destination: dest,
            port: port,
            description: descInput.value
        })
    });

    const result = await response.json();
    if (result.success) {
        // Reset form and hide modal
        destInput.value = '';
        portInput.value = '';
        descInput.value = '';
        document.getElementById('rule-action').value = 'ACCEPT';
        document.getElementById('rule-proto').value = 'tcp';
        togglePortInput();
        
        const modalInstance = bootstrap.Modal.getInstance(document.getElementById('modal-add-rule'));
        if (modalInstance) {
            modalInstance.hide();
        }
        loadRules(currentGroupId);
    } else {
        showNotification('danger', 'Errore: ' + (result.body.detail || 'Sconosciuto'));
    }
}

function openAddRuleModal() {
    const modal = new bootstrap.Modal(document.getElementById('modal-add-rule'));
    modal.show();
}

async function deleteRule(ruleId) {
    if (!confirm("Eliminare questa regola?")) return;

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `action=delete_rule&rule_id=${encodeURIComponent(ruleId)}`
    });

    if ((await response.json()).success) {
        loadRules(currentGroupId);
    }
}

async function moveRule(ruleId, direction) {
    // Find current index
    const index = window.currentRules.findIndex(r => r.id === ruleId);
    if (index === -1) return;

    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= window.currentRules.length) return;

    // Swap order values
    // Actually we just swap positions in array and reassign order = index
    const rules = [...window.currentRules];
    [rules[index], rules[newIndex]] = [rules[newIndex], rules[index]];

    // Prepare update payload
    const updates = rules.map((r, i) => ({
        id: r.id,
        order: i
    }));

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'reorder_rules',
            orders: updates
        })
    });

    if ((await response.json()).success) {
        loadRules(currentGroupId); // Reload to reflect changes
    }
}
