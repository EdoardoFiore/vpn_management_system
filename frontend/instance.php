<?php
// instance.php
if (!isset($_GET['id']) || empty($_GET['id'])) {
    header('Location: index.php');
    exit;
}
require_once 'includes/header.php';
?>

<div id="notification-container"></div>

<div class="mb-4">
    <a href="index.php" class="btn btn-ghost-secondary">
        <i class="ti ti-arrow-left icon"></i> Torna alla Dashboard
    </a>
</div>

<div class="d-flex justify-content-between align-items-center mb-3">
    <h2 id="current-instance-name">Caricamento...</h2>
    <div class="d-flex align-items-center">
        <span id="current-instance-port" class="me-2"></span>
        <span id="current-instance-subnet" class="me-2"></span>
        <button class="btn btn-danger btn-sm btn-icon" onclick="deleteInstancePrompt()">
            <i class="ti ti-trash"></i>
        </button>
    </div>
</div>

<!-- Tabs Navigation -->
<ul class="nav nav-tabs mb-3" data-bs-toggle="tabs">
    <li class="nav-item">
        <a href="#tab-clients" class="nav-link active" data-bs-toggle="tab">Gestione Client</a>
    </li>
    <li class="nav-item">
        <a href="#tab-routes" class="nav-link" data-bs-toggle="tab">Rotte & DNS</a>
    </li>
    <li class="nav-item">
        <a href="#tab-firewall" class="nav-link" data-bs-toggle="tab">Firewall / ACL</a>
    </li>
</ul>

<div class="tab-content">
    
    <!-- Client Management Tab -->
    <div class="tab-pane active show" id="tab-clients">
        <div class="card mb-4">
            <div class="card-header">
                <h3 class="card-title">Aggiungi Nuovo Client</h3>
            </div>
            <div class="card-body">
                <form id="addClientForm" onsubmit="event.preventDefault(); createClient();">
                    <div class="row g-2">
                        <div class="col">
                            <input type="text" id="clientNameInput" class="form-control" placeholder="Es: laptop-mario-rossi"
                                required>
                            <div class="invalid-feedback">Solo lettere, numeri, trattini, punti e underscore.</div>
                        </div>
                        <div class="col-auto">
                            <button type="submit" class="btn btn-primary">
                                <i class="ti ti-plus icon"></i> Crea Client
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <div class="card mb-4" style="height: 400px; display: flex; flex-direction: column;">
                    <div class="card-header">
                        <h3 class="card-title">Client Disponibili</h3>
                        <div class="card-actions">
                            <button class="btn btn-icon" onclick="fetchAndRenderClients()">
                                <i class="ti ti-refresh"></i>
                            </button>
                        </div>
                    </div>
                    <div class="table-responsive" style="flex: 1; overflow-y: auto;">
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
                <div class="card mb-4" style="height: 400px; display: flex; flex-direction: column;">
                    <div class="card-header">
                        <h3 class="card-title">Client Connessi</h3>
                        <div class="card-actions">
                            <button class="btn btn-icon" onclick="fetchAndRenderClients()">
                                <i class="ti ti-refresh"></i>
                            </button>
                        </div>
                    </div>
                    <div class="table-responsive" style="flex: 1; overflow-y: auto;">
                        <table class="table table-vcenter card-table table-striped">
                            <thead>
                                <tr>
                                    <th>Client</th>
                                    <th>Indirizzi IP</th>
                                    <th>Traffico</th>
                                    <th>Connesso da</th>
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

    <!-- Routes Tab -->
    <div class="tab-pane" id="tab-routes">
         <div class="card">
            <div class="card-header">
                <h3 class="card-title">Rotte e DNS Personalizzati</h3>
                <div class="card-actions">
                    <button class="btn btn-sm btn-primary" onclick="toggleRouteEdit()">
                        <i class="ti ti-edit"></i> Modifica
                    </button>
                </div>
            </div>
            <div class="card-body">
                <!-- VIEW MODE -->
                <div id="routes-view-mode">
                    <div class="d-flex align-items-center mb-3">
                        <strong>Modalità:</strong>
                        <span id="tunnel-mode-display" class="badge bg-secondary ms-2">-</span>
                    </div>

                    <!-- DNS Display -->
                    <div id="dns-view-container" class="mb-3" style="display: none;">
                        <strong>DNS Servers:</strong> <span id="current-dns-display" class="text-muted">Default</span>
                    </div>

                    <div id="routes-list" class="list-group list-group-flush"></div>
                </div>

                <!-- EDIT MODE -->
                <div id="routes-edit-mode" style="display: none;">
                    <div class="mb-3">
                        <label class="form-label">Modalità Tunnel</label>
                        <select class="form-select" id="tunnel-mode-edit" onchange="toggleRouteConfigEdit()">
                            <option value="full">Full Tunnel</option>
                            <option value="split">Split Tunnel</option>
                        </select>
                    </div>

                    <div id="routes-edit-container"></div>

                    <button type="button" class="btn btn-sm btn-outline-primary mb-3" onclick="addRouteEdit()"
                        style="display: none;">
                        <i class="ti ti-plus"></i> Aggiungi Rotta
                    </button>

                    <div class="d-flex justify-content-end gap-2 mt-3">
                        <button class="btn btn-secondary" onclick="cancelRouteEdit()">Annulla</button>
                        <button class="btn btn-success" onclick="saveRoutes()">Salva Modifiche</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Firewall Tab (New) -->
    <div class="tab-pane" id="tab-firewall">
        <div class="card mb-3">
            <div class="card-header">
                <h3 class="card-title">Policy di Default Firewall Istanza</h3>
            </div>
            <div class="card-body">
                <div class="mb-3">
                    <label class="form-label">Policy Iniziale per il Traffico dei Client VPN</label>
                    <select class="form-select" id="instance-firewall-default-policy">
                        <option value="ACCEPT">ACCEPT (Consenti tutto ciò che non è esplicitamente bloccato)</option>
                        <option value="DROP">DROP (Blocca tutto ciò che non è esplicitamente consentito)</option>
                    </select>
                    <small class="form-hint">Questa policy si applica a tutto il traffico che proviene dai client VPN di questa istanza e che non corrisponde a nessuna delle regole dei gruppi ACL definite.</small>
                </div>
                <button class="btn btn-primary" onclick="saveInstanceFirewallPolicy()">Salva Policy</button>
            </div>
        </div>
        <div class="row row-cards">
            <!-- Sidebar: Groups List -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Gruppi</h3>
                        <div class="card-actions">
                             <a href="#" class="btn btn-sm btn-primary" data-bs-toggle="modal" data-bs-target="#modal-create-group">
                                <i class="ti ti-plus"></i> Nuovo
                            </a>
                        </div>
                    </div>
                    <div class="list-group list-group-flush" id="groups-list">
                        <div class="list-group-item text-center">Caricamento...</div>
                    </div>
                </div>
            </div>

            <!-- Main Content: Selected Group Details -->
            <div class="col-md-8">
                <div id="group-details-container" style="display: none;">
                    <!-- Members Card -->
                    <div class="card mb-3">
                        <div class="card-header">
                            <h3 class="card-title" id="selected-group-title">Membri</h3>
                            <div class="card-actions">
                                <button class="btn btn-sm btn-outline-danger" onclick="deleteCurrentGroup()">Elimina Gruppo</button>
                                <button class="btn btn-sm btn-primary" onclick="openAddMemberModal()">Aggiungi</button>
                            </div>
                        </div>
                        <div class="card-body p-0">
                             <div class="table-responsive">
                                <table class="table table-vcenter card-table">
                                    <thead>
                                        <tr>
                                            <th>Utente</th>
                                            <th class="w-1"></th>
                                        </tr>
                                    </thead>
                                    <tbody id="members-table-body"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- Rules Card -->
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Regole Firewall</h3>
                            <div class="card-actions">
                                <button class="btn btn-sm btn-primary" onclick="openAddRuleModal()">Aggiungi Regola</button>
                            </div>
                        </div>
                        <div class="card-table table-responsive">
                            <table class="table table-vcenter">
                                <thead>
                                    <tr>
                                        <th class="w-1">Ordin.</th>
                                        <th>Azione</th>
                                        <th>Proto</th>
                                        <th>Dest.</th>
                                        <th>Porta</th>
                                        <th class="w-1"></th>
                                    </tr>
                                </thead>
                                <tbody id="rules-table-body"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div id="no-group-selected" class="card card-body text-center py-5">
                    <h3 class="text-muted">Seleziona un gruppo.</h3>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Modal Create Group -->
<div class="modal modal-blur fade" id="modal-create-group" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Nuovo Gruppo</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <label class="form-label">Nome Gruppo</label>
                    <input type="text" class="form-control" id="group-name-input" placeholder="Es. Amministrazione">
                </div>
                <div class="mb-3">
                    <label class="form-label">Descrizione</label>
                    <input type="text" class="form-control" id="group-desc-input" placeholder="Opzionale">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-primary" onclick="createGroup()">Crea Gruppo</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Add Member -->
<div class="modal modal-blur fade" id="modal-add-member" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Aggiungi Membro</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                 <div class="mb-3">
                    <label class="form-label">Seleziona Cliente</label>
                    <select class="form-select" id="member-select">
                        <option value="">Caricamento...</option>
                    </select>
                    <small class="form-hint">Vengono mostrati solo i client di questa istanza.</small>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-primary" onclick="addMember()">Aggiungi</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Add Rule -->
<div class="modal modal-blur fade" id="modal-add-rule" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Nuova Regola Firewall</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label">Azione</label>
                        <select class="form-select" id="rule-action">
                            <option value="ACCEPT">ACCEPT (Consenti)</option>
                            <option value="DROP">DROP (Blocca)</option>
                            <option value="REJECT">REJECT (Rifiuta)</option>
                        </select>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label">Protocollo</label>
                        <select class="form-select" id="rule-proto" onchange="togglePortInput()">
                            <option value="tcp">TCP</option>
                            <option value="udp">UDP</option>
                            <option value="icmp">ICMP</option>
                            <option value="all">Tutti (ALL)</option>
                        </select>
                    </div>
                </div>
                <div class="mb-3">
                    <label class="form-label">Destinazione (CIDR o IP)</label>
                    <input type="text" class="form-control" id="rule-dest" placeholder="0.0.0.0/0 per tutto, o 192.168.1.50">
                    <div class="invalid-feedback">Destinazione non valida. Inserisci un IP, un CIDR o 'any'.</div>
                </div>
                <div class="mb-3" id="port-container">
                    <label class="form-label">Porta (Opzionale)</label>
                    <input type="text" class="form-control" id="rule-port" placeholder="80, 443, 1000:2000">
                    <div class="invalid-feedback">Porta non valida. Inserisci un numero (1-65535) o un intervallo (es. 1000:2000).</div>
                </div>
                <div class="mb-3">
                    <label class="form-label">Descrizione</label>
                    <input type="text" class="form-control" id="rule-desc">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-primary" onclick="createRule()">Aggiungi Regola</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Delete Rule Confirm -->
<div class="modal modal-blur fade" id="modal-delete-rule-confirm" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Conferma Eliminazione Regola</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p>Sei sicuro di voler eliminare la seguente regola?</p>
                <div id="delete-rule-summary" class="mb-3"></div>
                <p class="text-muted">Questa azione non può essere annullata. La regola firewall verrà rimossa permanentemente.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" id="confirm-delete-rule-button" data-bs-dismiss="modal">Sì, elimina</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Revoke Confirm -->
<div class="modal modal-blur fade" id="modal-revoke-confirm" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Conferma Revoca</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p>Sei sicuro di voler revocare l'accesso per il client <strong id="revoke-client-name"></strong>?</p>
                <p class="text-muted">Questa azione non può essere annullata. Il client non potrà più connettersi.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" id="confirm-revoke-button" data-bs-dismiss="modal">Sì, revoca</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Delete Instance -->
<div class="modal modal-blur fade" id="modal-delete-instance" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Conferma Eliminazione Istanza</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                Sei sicuro di voler eliminare questa istanza? Tutti i client e le configurazioni associate verranno rimosse permanentemente. Questa azione non può essere annullata.
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" onclick="deleteInstanceAction()" data-bs-dismiss="modal">Sì, elimina</button>
            </div>
        </div>
    </div>
</div>

<?php
$extra_scripts = ['js/instance.js', 'js/firewall.js']; // Reusing firewall.js logic adapted
require_once 'includes/footer.php';
?>