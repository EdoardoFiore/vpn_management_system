
// State
let allGroups = [];
let currentGroupId = null;
let availableClientData = []; // Store client info for selector

document.addEventListener('DOMContentLoaded', () => {
    loadGroups();
});

// --- Groups Management ---

async function loadGroups() {
    try {
        const response = await fetch(`${API_AJAX_HANDLER}?action=get_groups`);
        const result = await response.json();

        if (result.success) {
            allGroups = result.body;
            renderGroupsList();
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
    const name = document.getElementById('group-name-input').value;
    const desc = document.getElementById('group-desc-input').value;

    if (!name) return alert("Inserisci un nome.");

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create_group', name: name, description: desc })
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
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nessun membro.</td></tr>';
        return;
    }

    group.members.forEach(memberId => {
        // Simple parser for memberId "instance_client"
        // Heuristic: Last part is client, rest is instance (handles underscores in instance name)
        // Actually best to look it up, but for display let's try to split carefully.
        // Or just display raw ID if not parsable.
        // Assuming format {INSTANCE_NAME}_{CLIENT_NAME}
        // BUT OpenVPN script generates random instance names? No, user defines them.

        let displayUser = memberId;
        let displayInstance = '-';

        // This is tricky without metadata. We know how we stored it.
        // We can just display it.

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${displayUser}</td>
            <td>-</td>
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
    const modal = new bootstrap.Modal(document.getElementById('modal-add-member'));
    modal.show();

    const select = document.getElementById('member-select');
    select.innerHTML = '<option value="">Caricamento...</option>';
    select.disabled = true;

    // Load available clients from all instances
    try {
        // Fetch instances first
        const instResp = await fetch(`${API_AJAX_HANDLER}?action=get_instances`);
        const instData = await instResp.json();
        const instances = instData.body || [];

        availableClientData = [];

        select.innerHTML = '<option value="">Seleziona un utente...</option>';

        for (const inst of instances) {
            const clientResp = await fetch(`${API_AJAX_HANDLER}?action=get_clients&instance_id=${inst.id}`);
            const clientData = await clientResp.json();
            const clients = clientData.body || [];

            clients.forEach(c => {
                // Check if already in current group?
                // Or in ANY group? Ideally backend prevents duplicate static IP assignment collision.
                // Backend `add_member` handles allocation.

                const id = `${inst.name}_${c.name}`;
                availableClientData.push({
                    id: id,
                    client_name: c.name,
                    instance_name: inst.name,
                    subnet: inst.subnet,
                    display: `${c.name} (${inst.name})`
                });

                const opt = document.createElement('option');
                opt.value = id;
                opt.textContent = `${c.name} (${inst.name})`;
                select.appendChild(opt);
            });
        }
        select.disabled = false;

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
    // We need instance name for cleanup.
    // Try to derive it from availableClientData if cached, or parse it.
    // Heuristic: clientId = instance_client. 
    // We stored everything as string.
    // Let's implement a parsing strategy assume instance name doesn't contain "_custom_" ?
    // Actually, `remove_group_member` needs `instance_name` to find the CCD file.

    // Quick fix: loop `availableClientData`? It might be empty if we refreshed.
    // Better: parse string. 
    // Actually the robust way is backend should handle it, BUT backend expects it.
    // Let's iterate `allGroups` members? No.
    // Let's try to pass instance name by splitting. 
    // If instance is "server_test" and client is "client1", id is "server_test_client1".
    // We don't know where to split.
    // Backend `remove_client_from_all_groups` does lookup via `firewall_manager` iteration.
    // But `remove_member_from_group` API endpoint requires `instance_name` query param.
    // Wait, the API endpoint `remove_group_member` takes `group_id`, `client_id`, `instance_name`.
    // I should probably store `instance_name` in `group.json` members list as object.
    // But I defined `members: List[str]`.

    // Workaround: The backend `ip_manager` needs instance name.
    // Can we fetch instances and match prefix?
    // Let's implement a small helper to guess instance name.

    // UI Hack: We'll assume the user loaded the Add Member modal at least once? No.
    // Let's fetch instances silently if needed.

    let instanceName = null;
    try {
        const instResp = await fetch(`${API_AJAX_HANDLER}?action=get_instances`);
        const instData = await instResp.json();
        const instances = instData.body || [];

        for (const inst of instances) {
            if (clientId.startsWith(inst.name + "_")) {
                instanceName = inst.name;
                break; // Best guess
            }
        }
    } catch (e) { }

    if (!instanceName) {
        alert("Impossibile determinare l'istanza del client. Riprova.");
        return;
    }

    if (!confirm(`Rimuovere ${clientId} dal gruppo?`)) return;

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'remove_group_member',
            group_id: currentGroupId,
            client_identifier: clientId,
            instance_name: instanceName
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
    const dest = document.getElementById('rule-dest').value;
    const port = document.getElementById('rule-port').value;
    const desc = document.getElementById('rule-desc').value;

    if (!dest) return alert("Destinazione richiesta.");

    const response = await fetch(`${API_AJAX_HANDLER}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'create_rule',
            group_id: currentGroupId,
            action: action,
            protocol: proto,
            destination: dest,
            port: port,
            description: desc
        })
    });

    const result = await response.json();
    if (result.success) {
        bootstrap.Modal.getInstance(document.getElementById('modal-add-rule')).hide();
        loadRules(currentGroupId);
    } else {
        alert("Errore: " + result.body.detail);
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
