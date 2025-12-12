<?php
// index.php
require_once 'includes/header.php';
?>

<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>Istanze OpenVPN</h2>
    <div class="d-flex align-items-center gap-2">
        <span class="text-muted small me-2" id="connection-status"></span>
        <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#modal-create-instance">
            <i class="ti ti-plus icon"></i> Nuova Istanza
        </button>
    </div>
</div>

<div id="notification-container"></div>

<div class="row">
    <!-- Main Column: Instances -->
    <div class="col-lg-8">
        <h3 class="mb-3">Istanze Attive</h3>
        <div class="row row-cards" id="instances-container">
            <!-- Instances will be loaded here by JS -->
            <div class="col-12 text-center p-5">
                <div class="spinner-border text-primary" role="status"></div>
            </div>
        </div>
    </div>

    <!-- Sidebar: Stats -->
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Top Users (Sessione)</h3>
            </div>
            <div class="card-body" id="top-clients-container">
                <div class="text-center p-3">
                    <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
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
                        <input type="text" class="form-control" name="name" id="instanceNameInput"
                            placeholder="Es: vpn-ufficio" required>
                        <div class="invalid-feedback">Il nome può contenere solo lettere, numeri e trattini.</div>
                        <small class="form-hint">Solo lettere, numeri e trattini.</small>
                    </div>
                    <div class="row">
                        <div class="col-lg-6">
                            <div class="mb-3">
                                <label class="form-label">Porta UDP</label>
                                <input type="number" class="form-control" name="port"
                                    placeholder="Es: 51820 (Default), 51821-51830" required>
                            </div>
                        </div>
                        <div class="col-lg-6">
                            <div class="mb-3">
                                <label class="form-label">Subnet VPN</label>
                                <input type="text" class="form-control" name="subnet" placeholder="10.8.0.0/24"
                                    required>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Modalità Tunnel</label>
                        <select class="form-select" name="tunnel_mode" id="tunnel-mode-select"
                            onchange="toggleRouteConfig()">
                            <option value="full">Full Tunnel (Tutto il traffico)</option>
                            <option value="split">Split Tunnel (Solo reti specifiche)</option>
                        </select>
                    </div>

                    <!-- DNS Configuration (Full Tunnel Only) -->
                    <div class="mb-3">
                        <label class="form-label">DNS Servers</label>
                        <input type="text" class="form-control" name="dns_servers" placeholder="Es: 1.1.1.1, 8.8.8.8">
                        <small class="form-hint">Lascia vuoto per usare i default (Google). Visibile solo in Full
                            Tunnel.</small>
                    </div>

                    <!-- Routes Configuration (Split Tunnel Only) -->
                    <div id="routes-config" style="display: none;">
                        <label class="form-label">Rotte Personalizzate</label>
                        <div id="routes-container"></div>
                        <button type="button" class="btn btn-outline-primary btn-sm mt-2" onclick="addRoute()">
                            <i class="ti ti-plus"></i> Aggiungi Rotta
                        </button>
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

<?php
$extra_scripts = ['js/dashboard.js'];
require_once 'includes/footer.php';
?>