<?php
// machine_settings.php
require_once 'includes/header.php';
?>

<div id="notification-container"></div>

<div class="mb-4">
    <a href="index.php" class="btn btn-ghost-secondary">
        <i class="ti ti-arrow-left icon"></i> Torna alla Dashboard
    </a>
</div>

<div class="d-flex justify-content-between align-items-center mb-3">
    <h2>Impostazioni Macchina</h2>
</div>

<!-- Tabs Navigation -->
<ul class="nav nav-tabs mb-3" data-bs-toggle="tabs">
    <li class="nav-item">
        <a href="#tab-machine-firewall" class="nav-link active" data-bs-toggle="tab">Firewall (Globale)</a>
    </li>
    <li class="nav-item">
        <a href="#tab-network-interfaces" class="nav-link" data-bs-toggle="tab">Interfacce di Rete</a>
    </li>
</ul>

<div class="tab-content">
    
    <!-- Machine Firewall Tab -->
    <div class="tab-pane active show" id="tab-machine-firewall">
        
        <!-- Toolbar -->
        <div class="mb-3 d-flex justify-content-end">
             <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#modal-add-machine-rule">
                <i class="ti ti-plus"></i> Nuova Regola
            </button>
        </div>

        <!-- INPUT Rules -->
        <div class="card mb-3">
            <div class="card-header">
                <h3 class="card-title">Regole INPUT (Ingresso)</h3>
            </div>
            <div class="card-table table-responsive">
                <table class="table table-vcenter table-hover">
                    <thead>
                        <tr>
                            <th class="w-1"></th>
                            <th>Azione</th>
                            <th>Proto</th>
                            <th>Sorgente</th>
                            <th>Destinazione</th>
                            <th>Porta</th>
                            <th>In-If</th>
                            <th>Commento</th>
                            <th class="w-1"></th>
                        </tr>
                    </thead>
                    <tbody id="machine-firewall-rules-input-body" data-chain-group="INPUT">
                         <tr><td colspan="9" class="text-center text-muted">Caricamento...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- OUTPUT Rules -->
        <div class="card mb-3">
            <div class="card-header">
                <h3 class="card-title">Regole OUTPUT (Uscita)</h3>
            </div>
            <div class="card-table table-responsive">
                <table class="table table-vcenter table-hover">
                    <thead>
                        <tr>
                            <th class="w-1"></th>
                            <th>Azione</th>
                            <th>Proto</th>
                            <th>Sorgente</th>
                            <th>Destinazione</th>
                            <th>Porta</th>
                            <th>Out-If</th>
                            <th>Commento</th>
                            <th class="w-1"></th>
                        </tr>
                    </thead>
                    <tbody id="machine-firewall-rules-output-body" data-chain-group="OUTPUT">
                         <tr><td colspan="9" class="text-center text-muted">Caricamento...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- FORWARD Rules -->
        <div class="card mb-3">
            <div class="card-header">
                <h3 class="card-title">Regole FORWARD (Inoltro)</h3>
            </div>
            <div class="card-table table-responsive">
                <table class="table table-vcenter table-hover">
                    <thead>
                        <tr>
                            <th class="w-1"></th>
                            <th>Azione</th>
                            <th>Proto</th>
                            <th>Sorgente</th>
                            <th>Destinazione</th>
                            <th>Porta</th>
                            <th>In-If</th>
                            <th>Out-If</th>
                            <th>Commento</th>
                            <th class="w-1"></th>
                        </tr>
                    </thead>
                    <tbody id="machine-firewall-rules-forward-body" data-chain-group="FORWARD">
                         <tr><td colspan="10" class="text-center text-muted">Caricamento...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- OTHER Rules (NAT, Mangle, etc) -->
        <div class="card mb-3">
             <div class="card-header">
                <h3 class="card-title">Altre Regole (NAT/Mangle/Raw)</h3>
            </div>
            <div class="card-table table-responsive">
                <table class="table table-vcenter table-hover">
                    <thead>
                        <tr>
                            <th class="w-1"></th>
                            <th>Tabella</th>
                            <th>Chain</th>
                            <th>Azione</th>
                            <th>Proto</th>
                            <th>Sorgente</th>
                            <th>Dest.</th>
                            <th>Porta</th>
                            <th>Commento</th>
                            <th class="w-1"></th>
                        </tr>
                    </thead>
                    <tbody id="machine-firewall-rules-other-body" data-chain-group="OTHER">
                         <tr><td colspan="10" class="text-center text-muted">Caricamento...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>
                            
                                <!-- Network Interfaces Tab -->
                                <div class="tab-pane" id="tab-network-interfaces">
                                    <div class="card">
                                        <div class="card-header">
                                            <h3 class="card-title">Interfacce di Rete della Macchina</h3>
                                             <div class="card-actions">
                                                <button class="btn btn-sm btn-primary" onclick="loadNetworkInterfaces()">
                                                    <i class="ti ti-refresh"></i> Aggiorna
                                                </button>
                                            </div>
                                        </div>
                                        <div class="card-body p-0">
                                            <div class="table-responsive">
                                                <table class="table table-vcenter card-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Interfaccia</th>
                                                            <th>MAC</th>
                                                            <th>Link</th>
                                                            <th>IP</th>
                                                            <th>CIDR</th>
                                                            <th>Netmask</th>
                                                            <th class="w-1"></th>
                                                        </tr>
                                                    </thead>
                                                    <tbody id="network-interfaces-table-body">
                                                        <tr><td colspan="7" class="text-center text-muted">Caricamento interfacce...</td></tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Modal Add Machine Firewall Rule -->
                            <div class="modal modal-blur fade" id="modal-add-machine-rule" tabindex="-1" role="dialog" aria-hidden="true">
                                <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Nuova Regola Firewall Globale</h5>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                        </div>
                                        <div class="modal-body">
                                            <form id="addMachineRuleForm">
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Tabella
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Tabella IPTables" data-bs-content="Specifica la tabella iptables. 'filter' è per il filtraggio (default). 'nat' per la traduzione degli indirizzi. 'mangle' per la modifica. 'raw' per escludere connessioni dal tracciamento.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <select class="form-select" name="table">
                                                            <option value="filter">filter</option>
                                                            <option value="nat">nat</option>
                                                            <option value="mangle">mangle</option>
                                                            <option value="raw">raw</option>
                                                        </select>
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Chain
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Chain" data-bs-content="La catena di regole. Es: INPUT (pacchetti per il server), OUTPUT (dal server), FORWARD (da inoltrare), PREROUTING/POSTROUTING (per NAT).">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <select class="form-select" name="chain" required>
                                                            <!-- Options will be populated dynamically by JavaScript -->
                                                        </select>
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Azione
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Azione" data-bs-content="L'azione da intraprendere: ACCEPT (accetta), DROP (scarta), REJECT (rifiuta), MASQUERADE/SNAT/DNAT (per NAT).">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <select class="form-select" name="action">
                                                            <option value="ACCEPT">ACCEPT</option>
                                                            <option value="DROP">DROP</option>
                                                            <option value="REJECT">REJECT</option>
                                                            <option value="MASQUERADE">MASQUERADE</option>
                                                            <option value="SNAT">SNAT</option>
                                                            <option value="DNAT">DNAT</option>
                                                        </select>
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Protocollo
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Protocollo" data-bs-content="Il protocollo di rete. 'tcp' e 'udp' sono i più comuni. 'icmp' per i ping. 'all' per tutti. Se scegli 'tcp' o 'udp', puoi specificare una porta.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <select class="form-select" name="protocol" onchange="toggleMachinePortInput(this.value, 'add')">
                                                            <option value="">all</option>
                                                            <option value="tcp">tcp</option>
                                                            <option value="udp">udp</option>
                                                            <option value="icmp">icmp</option>
                                                        </select>
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Sorgente
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="IP Sorgente" data-bs-content="L'origine del traffico. Può essere un IP (es. 192.168.1.50), un range CIDR (es. 192.168.1.0/24), o lasciato vuoto per 'any'.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <input type="text" class="form-control" name="source" placeholder="any o 192.168.1.0/24">
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label d-flex align-items-center">Destinazione
                                                             <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="IP Destinazione" data-bs-content="La destinazione. Può essere un IP (es. 8.8.8.8), un CIDR (es. 10.0.0.0/8), o vuoto per 'any'. Usato anche per --to-source in SNAT e --to-destination in DNAT.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <input type="text" class="form-control" name="destination" placeholder="any o 8.8.8.8">
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-4 mb-3" id="machine-port-container-add" style="display: none;">
                                                        <label class="form-label d-flex align-items-center">Porta
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Porta/e" data-bs-content="La porta di destinazione. Può essere singola (80), una lista (80,443), o un range (1024:2048). Richiede protocollo TCP o UDP.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <input type="text" class="form-control" name="port" placeholder="80, 443, 1000:2000">
                                                    </div>
                                                    <div class="col-md-4 mb-3">
                                                        <label class="form-label d-flex align-items-center">In-Interface
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Interfaccia di Ingresso" data-bs-content="L'interfaccia di rete in ingresso (es. eth0, tun+). Il '+' è un wildcard. Lascia vuoto per 'any'.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <input type="text" class="form-control" name="in_interface" placeholder="eth0, tun+">
                                                    </div>
                                                    <div class="col-md-4 mb-3">
                                                        <label class="form-label d-flex align-items-center">Out-Interface
                                                            <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Interfaccia di Uscita" data-bs-content="L'interfaccia di rete in uscita (es. eth0, tun+). Il '+' è un wildcard. Lascia vuoto per 'any'.">
                                                                <i class="ti ti-help-circle"></i>
                                                            </span>
                                                        </label>
                                                        <input type="text" class="form-control" name="out_interface" placeholder="eth0, tun+">
                                                    </div>
                                                </div>
                                                <div class="mb-3">
                                                    <label class="form-label d-flex align-items-center">Stato Connessione
                                                        <span class="ms-2" data-bs-toggle="popover" data-bs-trigger="hover" title="Stato Connessione" data-bs-content="Filtra per stato della connessione (richiede -m state). Es: NEW, ESTABLISHED, RELATED. Si possono combinare con virgole.">
                                                            <i class="ti ti-help-circle"></i>
                                                        </span>
                                                    </label>
                                                    <input type="text" class="form-control" name="state" placeholder="NEW,ESTABLISHED,RELATED">
                                                </div>
                                                <div class="mb-3">
                                                    <label class="form-label">Commento</label>
                                                    <input type="text" class="form-control" name="comment" placeholder="Descrizione della regola">
                                                </div>
                                            </form>
                            
                                            <div class="mt-4">
                                                <label class="form-label">Preview Comando IPTables</label>
                                                <pre class="code-block" style="background-color: #f5f7fb; padding: 10px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 13px; color: #333;"><code id="iptables-preview-add">iptables -t filter -A INPUT -j ACCEPT</code></pre>
                                            </div>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                                            <button type="button" class="btn btn-primary" onclick="addMachineFirewallRule()">Aggiungi Regola</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Modal Edit Machine Firewall Rule -->
                            <div class="modal modal-blur fade" id="modal-edit-machine-rule" tabindex="-1" role="dialog" aria-hidden="true">
                                <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Modifica Regola Firewall Globale</h5>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                        </div>
                                        <div class="modal-body">
                                            <form id="editMachineRuleForm">
                                                <input type="hidden" name="id">
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Tabella</label>
                                                        <select class="form-select" name="table">
                                                            <option value="filter">filter</option>
                                                            <option value="nat">nat</option>
                                                            <option value="mangle">mangle</option>
                                                            <option value="raw">raw</option>
                                                        </select>
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Chain</label>
                                                        <select class="form-select" name="chain" required>
                                                            <!-- Options populated by JS -->
                                                        </select>
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Azione</label>
                                                        <select class="form-select" name="action">
                                                            <option value="ACCEPT">ACCEPT</option>
                                                            <option value="DROP">DROP</option>
                                                            <option value="REJECT">REJECT</option>
                                                            <option value="MASQUERADE">MASQUERADE</option>
                                                            <option value="SNAT">SNAT</option>
                                                            <option value="DNAT">DNAT</option>
                                                        </select>
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Protocollo</label>
                                                        <select class="form-select" name="protocol" onchange="toggleMachinePortInput(this.value, 'edit')">
                                                            <option value="">all</option>
                                                            <option value="tcp">tcp</option>
                                                            <option value="udp">udp</option>
                                                            <option value="icmp">icmp</option>
                                                        </select>
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Sorgente</label>
                                                        <input type="text" class="form-control" name="source" placeholder="any o 192.168.1.0/24">
                                                    </div>
                                                    <div class="col-md-6 mb-3">
                                                        <label class="form-label">Destinazione</label>
                                                        <input type="text" class="form-control" name="destination" placeholder="any o 8.8.8.8">
                                                    </div>
                                                </div>
                                                <div class="row">
                                                    <div class="col-md-4 mb-3" id="machine-port-container-edit" style="display: none;">
                                                        <label class="form-label">Porta</label>
                                                        <input type="text" class="form-control" name="port" placeholder="80, 443, 1000:2000">
                                                    </div>
                                                    <div class="col-md-4 mb-3">
                                                        <label class="form-label">In-Interface</label>
                                                        <input type="text" class="form-control" name="in_interface" placeholder="eth0, tun+">
                                                    </div>
                                                    <div class="col-md-4 mb-3">
                                                        <label class="form-label">Out-Interface</label>
                                                        <input type="text" class="form-control" name="out_interface" placeholder="eth0, tun+">
                                                    </div>
                                                </div>
                                                <div class="mb-3">
                                                    <label class="form-label">Stato Connessione</label>
                                                    <input type="text" class="form-control" name="state" placeholder="NEW,ESTABLISHED,RELATED">
                                                </div>
                                                <div class="mb-3">
                                                    <label class="form-label">Commento</label>
                                                    <input type="text" class="form-control" name="comment" placeholder="Descrizione della regola">
                                                </div>
                                            </form>
                            
                                            <div class="mt-4">
                                                <label class="form-label">Preview Comando IPTables</label>
                                                <pre class="code-block" style="background-color: #f5f7fb; padding: 10px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 13px; color: #333;"><code id="iptables-preview-edit"></code></pre>
                                            </div>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                                            <button type="button" class="btn btn-primary" onclick="updateMachineFirewallRule()">Salva Modifiche</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Modal Confirm Delete Machine Rule -->
                            <div class="modal modal-blur fade" id="modal-confirm-delete-machine-rule" tabindex="-1" role="dialog" aria-hidden="true">
                                <div class="modal-dialog modal-dialog-centered" role="document">
                                    <div class="modal-content">
                                        <div class="modal-header">
                                            <h5 class="modal-title">Conferma Eliminazione Regola Firewall</h5>
                                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                        </div>
            <div class="modal-body">
                <p>Sei sicuro di voler eliminare la seguente regola firewall globale?</p>
                <div id="delete-machine-rule-summary" class="mb-3"></div>
                <p class="text-muted">Questa azione non può essere annullata. La regola verrà rimossa.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-danger" id="confirm-delete-machine-rule-button" data-bs-dismiss="modal">Sì, elimina</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal Edit Network Interface -->
<div class="modal modal-blur fade" id="modal-edit-network-interface" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="edit-interface-title">Configura Interfaccia: <span id="edit-interface-name"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <form id="editNetworkInterfaceForm">
                    <input type="hidden" name="interface_name" id="edit-interface-hidden-name">
                    <div class="mb-3">
                        <label class="form-label">MAC Address:</label>
                        <span id="edit-interface-mac" class="form-control-plaintext"></span>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Link Status:</label>
                        <span id="edit-interface-link-status" class="form-control-plaintext"></span>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Metodo di Configurazione IP</label>
                        <select class="form-select" name="ip_method" id="edit-interface-ip-method" onchange="toggleIpConfigFields(this.value)">
                            <option value="dhcp">DHCP</option>
                            <option value="static">Statico</option>
                            <option value="none">Nessuno</option>
                        </select>
                    </div>

                    <div id="static-ip-fields" style="display: none;">
                        <div class="mb-3">
                            <label class="form-label">Indirizzi IP (CIDR)</label>
                            <div id="static-ip-addresses-container">
                                <!-- Dynamic IP fields will be added here -->
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="addIpAddressField()">
                                <i class="ti ti-plus"></i> Aggiungi IP
                            </button>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Gateway</label>
                            <input type="text" class="form-control" name="gateway" id="edit-interface-gateway" placeholder="E.g., 192.168.1.1">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Server DNS (separati da virgola)</label>
                            <input type="text" class="form-control" name="nameservers" id="edit-interface-nameservers" placeholder="E.g., 8.8.8.8, 8.8.4.4">
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                <button type="button" class="btn btn-primary" onclick="saveNetworkInterfaceConfig()">Salva e Applica</button>
            </div>
        </div>
    </div>
</div>


<?php
$extra_scripts = ['js/machine_settings.js'];
require_once 'includes/footer.php';
?>