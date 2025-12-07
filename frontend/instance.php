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
    <!-- Available Clients -->
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

    <!-- Connected Clients -->
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

    <!-- Routes Management Section -->
    <div class="col-md-6">
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
</div>

<!-- Modal Revoke Confirm -->
<div class="modal modal-blur fade" id="modal-revoke-confirm" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-sm modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-body">
                <div class="modal-title">Sei sicuro?</div>
                <div>Vuoi revocare il certificato per <strong id="revoke-client-name"></strong>? Questa azione è
                    irreversibile.</div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-link link-secondary me-auto"
                    data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" id="confirm-revoke-button" data-bs-dismiss="modal">Sì,
                    revoca</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Delete Instance -->
<div class="modal modal-blur fade" id="modal-delete-instance" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-sm modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-body">
                <div class="modal-title text-danger">Eliminare Istanza?</div>
                <div>Vuoi davvero eliminare questa istanza VPN? Tutti i client perderanno la connessione.</div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-link link-secondary me-auto"
                    data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" onclick="deleteInstanceAction()"
                    data-bs-dismiss="modal">Elimina definitivamente</button>
            </div>
        </div>
    </div>
</div>

<?php
$extra_scripts = ['js/instance.js'];
require_once 'includes/footer.php';
?>