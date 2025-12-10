// State (Firewall specific)
let allGroups = [];
let currentGroupId = null;
let availableClientData = []; // Store client info for selector
let sortableGroupRulesInstance = null; // To hold the SortableJS instance for group rules

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
            // Add this: Populate the default policy dropdown
            document.getElementById('instance-firewall-default-policy').value = currentInstance.firewall_default_policy;

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
            window.currentRules = result.body; // Store rules globally for this context
            renderRules(window.currentRules);

            // Initialize SortableJS
            if (sortableGroupRulesInstance) {
                sortableGroupRulesInstance.destroy();
            }
            sortableGroupRulesInstance = new Sortable(tbody, {
                animation: 150,
                ghostClass: 'sortable-ghost',
                handle: '.ti-grip-vertical',
                filter: '.non-draggable-rule', // Add this line
                onMove: function (evt) {
                    // Prevent any item from being moved if the related element (the one it's trying to move over/next to) is the non-draggable rule
                    if (evt.related.classList.contains('non-draggable-rule')) {
                        return false;
                    }
                    // Also prevent the non-draggable rule itself from being moved if it somehow gets initiated
                    if (evt.dragged.classList.contains('non-draggable-rule')) {
                        return false;
                    }
                    return true; // Allow move otherwise
                },
                onEnd: function(evt) {
                    // Get the moved item
                    const movedItem = window.currentRules.splice(evt.oldIndex, 1)[0];
                    // Insert it at the new index
                    window.currentRules.splice(evt.newIndex, 0, movedItem);
                    
                    // The UI is already updated by SortableJS, we just need to save the new order.
                    applyRuleOrder();
                }
            });
            
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Errore caricamento regole.</td></tr>';
        }
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Errore di connessione.</td></tr>';
    }
}

function renderRules(rules) {
    const tbody = document.getElementById('rules-table-body');
    tbody.innerHTML = '';

    if (rules.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nessuna regola definita.</td></tr>';
        // DO NOT RETURN HERE - allow default policy row to be appended
    } else {
        rules.sort((a, b) => a.order - b.order);

        rules.forEach((rule, index) => {
            const tr = document.createElement('tr');
            tr.dataset.id = rule.id;

            let badgeClass = 'bg-secondary';
            if (rule.action === 'ACCEPT') badgeClass = 'bg-success';
            if (rule.action === 'DROP') badgeClass = 'bg-danger';

            tr.innerHTML = `
                <td class="w-1" style="cursor: grab;">
                    <i class="ti ti-grip-vertical"></i>
                </td>
                <td><span class="badge ${badgeClass}">${rule.action}</span></td>
                <td>${rule.protocol.toUpperCase()}</td>
                <td><code>${rule.destination}</code></td>
                <td>${rule.port || '*'}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-ghost-primary" onclick="openEditRuleModal('${rule.id}')" title="Modifica">
                        <i class="ti ti-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-ghost-danger" onclick="confirmDeleteRule('${rule.id}')" title="Elimina">
                        <i class="ti ti-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Always add a virtual rule for the instance's default firewall policy at the end
    const trDefault = document.createElement('tr');
    trDefault.className = 'table-secondary non-draggable-rule'; // Style to distinguish it and make non-draggable
    
    let defaultPolicyDisplay = 'N/A';
    let defaultPolicyBadgeClass = 'bg-secondary';
    let defaultPolicyTitle = 'Policy di default dell\'istanza (caricamento...)';

    if (currentInstance && currentInstance.firewall_default_policy) {
        const defaultPolicy = currentInstance.firewall_default_policy.toUpperCase();
        defaultPolicyDisplay = defaultPolicy;
        if (defaultPolicy === 'ACCEPT') defaultPolicyBadgeClass = 'bg-success';
        if (defaultPolicy === 'DROP') defaultPolicyBadgeClass = 'bg-danger';
        defaultPolicyTitle = 'Regola di default dell\'istanza. Non modificabile qui.';
    }

    trDefault.innerHTML = `
        <td></td>
        <td><span class="badge ${defaultPolicyBadgeClass}">${defaultPolicyDisplay}</span></td>
        <td>ANY</td>
        <td><code>ANY</code></td>
        <td>*</td>
        <td class="text-end">
            <span class="text-muted" title="${defaultPolicyTitle}">Default Instance Policy</span>
        </td>
    `;
    tbody.appendChild(trDefault);

    // Store current rules to handle reordering logic locally before saving
    // This needs to be after appending trDefault if trDefault is not part of sortable rules
    // If trDefault is meant to be non-sortable, its append position is fine here.
    window.currentRules = rules;
}

// Modified `togglePortInput` to accept a modalType
function togglePortInput(protocol, modalType = 'add') {
    let portContainerId;
    let portInputId;

    if (modalType === 'add') {
        portContainerId = 'port-container';
        portInputId = 'rule-port';
    } else if (modalType === 'edit') {
        portContainerId = 'edit-port-container';
        portInputId = 'edit-rule-port';
    } else {
        return; // Invalid modalType
    }

    const portContainer = document.getElementById(portContainerId);
    const portInput = document.getElementById(portInputId);

    if (!portContainer) return;
    
    if (protocol === 'tcp' || protocol === 'udp') {
        portContainer.style.display = 'block';
    } else {
        portContainer.style.display = 'none';
        if (portInput) portInput.value = ''; // Clear value when hidden
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

// Renamed and modified `openAddRuleModal` for creating new rules
function openCreateRuleModal() {
    // Reset the form fields for a new rule
    document.getElementById('rule-action').value = 'ACCEPT';
    document.getElementById('rule-proto').value = 'tcp';
    document.getElementById('rule-dest').value = '';
    document.getElementById('rule-port').value = '';
    document.getElementById('rule-desc').value = '';
    // Ensure port input visibility is correct for default protocol
    togglePortInput('tcp', 'add'); 

    new bootstrap.Modal(document.getElementById('modal-add-rule')).show();
}

// New function to show the confirmation modal
function confirmDeleteRule(ruleId) {
    const rule = window.currentRules.find(r => r.id === ruleId);
    if (!rule) {
        // Handle error: rule not found, maybe show a generic error or just return
        console.error("Rule not found for ID:", ruleId);
        return;
    }

    let badgeClass = 'bg-secondary';
    if (rule.action === 'ACCEPT') badgeClass = 'bg-success';
    if (rule.action === 'DROP') badgeClass = 'bg-danger';

    const ruleDescriptionHtml = `
        <strong>Azione:</strong> <span class="badge ${badgeClass}">${rule.action}</span><br>
        <strong>Protocollo:</strong> ${rule.protocol.toUpperCase()}<br>
        <strong>Destinazione:</strong> <code>${rule.destination}</code><br>
        <strong>Porta:</strong> ${rule.port || '*'}
    `;

    document.getElementById('delete-rule-summary').innerHTML = ruleDescriptionHtml;
    document.getElementById('confirm-delete-rule-button').onclick = () => performDeleteRule(ruleId);
    new bootstrap.Modal(document.getElementById('modal-delete-rule-confirm')).show();
}

// Renamed from deleteRule to performDeleteRule
async function performDeleteRule(ruleId) {
    // The modal should be dismissed by the button's data-bs-dismiss="modal"
    // So no need to close it here.

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `action=delete_rule&rule_id=${encodeURIComponent(ruleId)}`
    });

    if ((await response.json()).success) {
        showNotification('success', 'Regola firewall eliminata.');
        loadRules(currentGroupId);
    } else {
        showNotification('danger', 'Errore eliminazione regola.');
    }
}

// Function to open the Edit Rule Modal and populate it
function openEditRuleModal(ruleId) {
    const rule = window.currentRules.find(r => r.id === ruleId);
    if (!rule) {
        showNotification('danger', 'Regola non trovata per la modifica.');
        return;
    }
    
    window.currentEditingRule = rule; // Store the rule being edited

    // Populate the form fields
    document.getElementById('rule-id').value = rule.id;
    document.getElementById('edit-rule-action').value = rule.action;
    document.getElementById('edit-rule-proto').value = rule.protocol;
    document.getElementById('edit-rule-dest').value = rule.destination;
    document.getElementById('edit-rule-port').value = rule.port || '';
    document.getElementById('edit-rule-desc').value = rule.description || '';

    // Adjust port input visibility based on protocol
    togglePortInput(rule.protocol, 'edit');

    new bootstrap.Modal(document.getElementById('modal-edit-rule')).show();
}

async function updateRule() {
    const ruleId = document.getElementById('rule-id').value;
    const action = document.getElementById('edit-rule-action').value;
    const proto = document.getElementById('edit-rule-proto').value;
    const destInput = document.getElementById('edit-rule-dest');
    const portInput = document.getElementById('edit-rule-port');
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

    try {
        const response = await fetch(`${API_AJAX_HANDLER}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'update_rule',
                rule_id: ruleId,
                group_id: currentGroupId, // Ensure group_id is sent
                action_type: action, // Changed from 'action' to 'action_type' to avoid conflict with 'action' for API call
                protocol: proto,
                destination: dest,
                port: port,
                description: descInput.value
            })
        });

        const result = await response.json();
        if (result.success) {
            showNotification('success', 'Regola firewall aggiornata con successo.');
            bootstrap.Modal.getInstance(document.getElementById('modal-edit-rule')).hide();
            loadRules(currentGroupId);
        } else {
            showNotification('danger', 'Errore aggiornamento regola: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}


async function applyRuleOrder() {
    if (!window.currentRules) return;

    const updates = window.currentRules.map((rule, index) => ({
        id: rule.id,
        order: index
    }));

    try {
        const response = await fetch(`${API_AJAX_HANDLER}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'reorder_rules',
                orders: updates
            })
        });

        const result = await response.json();
        if (result.success) {
            showNotification('success', 'Ordinamento delle regole salvato.');
            // We can optionally reload to be safe, but the local state should be correct.
            loadRules(currentGroupId); 
        } else {
            showNotification('danger', `Errore durante il salvataggio dell'ordine: ${result.body.detail || 'Sconosciuto'}`);
            // Fallback to reload from server on error
            loadRules(currentGroupId);
        }
    } catch (e) {
        showNotification('danger', `Errore di connessione: ${e.message}`);
        loadRules(currentGroupId);
    }
}

async function saveInstanceFirewallPolicy() {
    if (!currentInstance) {
        showNotification("danger", "Errore: Istanza non selezionata.");
        return;
    }

    const policy = document.getElementById('instance-firewall-default-policy').value;

    try {
        const response = await fetch(`${API_AJAX_HANDLER}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'update_instance_firewall_policy', // Action for ajax_handler.php
                instance_id: currentInstance.id,
                default_policy: policy // Parameter name expected by backend
            })
        });
        const result = await response.json();

        if (result.success) { // Check result.success from ajax_handler.php
            showNotification('success', 'Policy firewall predefinita aggiornata con successo.');
            // Update currentInstance object in JS to reflect the new policy
            currentInstance.firewall_default_policy = policy;
            // Re-render rules to reflect the change in default policy (especially the "virtual" default rule)
            if (currentGroupId) { // Only reload if a group is currently selected
                loadRules(currentGroupId);
            }
        } else {
            showNotification('danger', 'Errore salvataggio policy: ' + (result.body.detail || 'Sconosciuto'));
        }
    } catch (e) {
        showNotification('danger', 'Errore di connessione: ' + e.message);
    }
}