<?php include 'includes/header.php'; ?>

<div class="page-header d-print-none">
    <div class="container-xl">
        <div class="row g-2 align-items-center">
            <div class="col">
                <h2 class="page-title">
                    Firewall & Access Control
                </h2>
                <div class="text-muted mt-1">Gestisci gruppi di utenti e regole di accesso.</div>
            </div>
            <div class="col-auto ms-auto d-print-none">
                <div class="btn-list">
                    <a href="#" class="btn btn-primary d-none d-sm-inline-block" data-bs-toggle="modal"
                        data-bs-target="#modal-create-group">
                        <i class="ti ti-plus"></i> Nuovo Gruppo
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="page-body">
    <div class="container-xl">
        <div class="row row-cards">
            <!-- Sidebar: Groups List -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Gruppi</h3>
                    </div>
                    <div class="list-group list-group-flush" id="groups-list">
                        <!-- Loaded via JS -->
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
                            <h3 class="card-title" id="selected-group-title">Membri del Gruppo</h3>
                            <div class="card-actions">
                                <button class="btn btn-sm btn-outline-danger" onclick="deleteCurrentGroup()">Elimina Gruppo</button>
                                <button class="btn btn-sm btn-primary" onclick="openAddMemberModal()">Aggiungi Membro</button>
                            </div>
                        </div>
                        <div class="card-body">
                             <div class="table-responsive">
                                <table class="table table-vcenter card-table">
                                    <thead>
                                        <tr>
                                            <th>Utente</th>
                                            <th>Istanza</th>
                                            <th class="w-1"></th>
                                        </tr>
                                    </thead>
                                    <tbody id="members-table-body">
                                        <!-- Members content -->
                                    </tbody>
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
                                        <th class="w-1">Ordine</th>
                                        <th>Azione</th>
                                        <th>Protocollo</th>
                                        <th>Destinazione</th>
                                        <th>Porta</th>
                                        <th class="w-1"></th>
                                    </tr>
                                </thead>
                                <tbody id="rules-table-body">
                                    <!-- Rules content -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>
                
                <div id="no-group-selected" class="card card-body text-center py-5">
                    <h3 class="text-muted">Seleziona un gruppo per gestirlo.</h3>
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
                    <small class="form-hint">Nota: L'aggiunta assegnerà un IP statico al cliente.</small>
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
                </div>
                <div class="mb-3" id="port-container">
                    <label class="form-label">Porta (Opzionale)</label>
                    <input type="text" class="form-control" id="rule-port" placeholder="80, 443, 1000:2000">
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

<script src="./js/utils.js"></script>
<script src="./js/firewall.js"></script>
<?php include 'includes/footer.php'; ?>
