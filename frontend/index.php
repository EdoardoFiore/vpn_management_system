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

                            <!-- Routes Management Section -->
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-header">
                                        <h3 class="card-title">Rotte Personalizzate</h3>
                                        <div class="card-actions">
                                            <button class="btn btn-sm btn-primary" onclick="toggleRouteEdit()">
                                                <i class="ti ti-edit"></i> Modifica
                                            </button>
                                        </div>
                                    </div>
                                    <div class="card-body">
                                        <!-- View Mode -->
                                        <div id="routes-view-mode">
                                            <div class="mb-2">
                                                <strong>Modalità Tunnel:</strong>
                                                <span id="tunnel-mode-display" class="badge bg-info ms-2"></span>
                                            </div>
                                            <div id="routes-list">
                                                <!-- Routes will be populated here -->
                                            </div>
                                        </div>

                                        <!-- Edit Mode -->
                                        <div id="routes-edit-mode" style="display: none;">
                                            <div class="mb-3">
                                                <label class="form-label">DNS Servers (Opzionale)</label>
                                                <input type="text" class="form-control" id="dns-servers-edit" placeholder="Es: 192.168.178.242, 8.8.8.8">
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Modalità Tunnel</label>
                                                <select class="form-select" id="tunnel-mode-edit"
                                                    onchange="toggleRouteConfigEdit()">
                                                    <option value="full">Full Tunnel</option>
                                                    <option value="split">Split Tunnel</option>
                                                </select>
                                            </div>
                                            <div id="routes-edit-container"></div>
                                            <button type="button" class="btn btn-sm btn-outline-primary mb-3"
                                                onclick="addRouteEdit()">
                                                <i class="ti ti-plus"></i> Aggiungi Rotta
                                            </button>
                                            <div class="mt-3">
                                                <button class="btn btn-success" onclick="saveRoutes()">
                                                    <i class="ti ti-check"></i> Salva
                                                </button>
                                                <button class="btn btn-secondary" onclick="cancelRouteEdit()">
                                                    <i class="ti ti-x"></i> Annulla
                                                </button>
                                            </div>
                                        </div>
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
                                    <label class="form-label">DNS Servers (Opzionale)</label>
                                    <input type="text" class="form-control" name="dns_servers" placeholder="Es: 192.168.178.242, 8.8.8.8">
                                    <small class="form-hint">Lascia vuoto per usare i default (Google DNS per Full Tunnel).</small>
                                </div>
                            </div>
                            <div class="col-md-12">
                                <div class="mb-3">
                                    <label class="form-label">Modalità Tunnel</label>
                                    <select class="form-select" name="tunnel_mode" id="tunnel-mode-select"
                                        onchange="toggleRouteConfig()">
                                        <option value="full">Full Tunnel (tutto il traffico via VPN)</option>
                                        <option value="split">Split Tunnel (solo rotte specifiche)</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Split Tunnel Routes Configuration -->
                        <div id="routes-config" style="display: none;">
                            <div class="mb-3">
                                <label class="form-label">Rotte Personalizzate</label>
                                <div id="routes-container"></div>
                                <button type="button" class="btn btn-sm btn-outline-primary" onclick="addRoute()">
                                    <i class="ti ti-plus"></i> Aggiungi Rotta
                                </button>
                                <small class="form-hint d-block mt-2">Specifica le subnet da rendere accessibili via VPN
                                    (es: 192.168.1.0/24)</small>
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
    <script src="js/app.js"></script>
    <script>
        // Any tiny initialization if strictly needed, otherwise empty
    </script>
</body>

</html>