#!/bin/bash

# =================================================================
#            VPN Management System - WireGuard Installer
# =================================================================
# Questo script installa e configura l'intero sistema di gestione
# VPN basato su WireGuard, Backend API e Frontend web.
# =================================================================

# --- Funzioni di Logging ---
log_info() {
  echo -e "\033[34m[INFO]\033[0m $1"
}

log_success() {
  echo -e "\033[32m[SUCCESS]\033[0m $1"
}

log_error() {
  echo -e "\033[31m[ERROR]\033[0m $1" >&2
}

# --- Funzioni Grafiche ---
print_banner() {
  echo -e "\033[1;36m"
  cat << "EOF"
 _    _ ______ _   _   __  __
| |  | || ___ \ \ | | |  \/  |
| |  | || |_/ /  \| | | .  . | __ _ _ __   __ _  __ _  ___ _ __
| |  | ||  __/| . ` | | |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
\  \/  /| |   | |\  | | |  | | (_| | | | | (_| | (_| |  __/ |
 \____/ \_|   \_| \_/ \_|  |_/\__,_|_| |_|\__,_|\__, |\___|_|
                                                 __/ |
                                                |___/
   (WireGuard Edition)
EOF
  echo -e "\033[0m"
}

# --- Controllo Root ---
if [[ $EUID -ne 0 ]]; then
  log_error "Questo script deve essere eseguito come root. Usa 'sudo bash setup-vpn-manager.sh'"
  exit 1
fi

print_banner
echo ""
log_info "Benvenuto nel programma di installazione automatico (WireGuard)."
echo ""
echo -n "Inizio installazione in "
for i in 3 2 1; do
  echo -n "$i... "
  sleep 1
done
echo ""

# --- Fase 1: Aggiornamento e Dipendenze ---
log_info "Fase 1/5: Aggiornamento sistema e installazione WireGuard..."

apt-get update

# 1. Installazione pacchetti base e WireGuard
log_info "Installazione WireGuard e strumenti di base..."
if ! apt-get install -y wireguard wireguard-tools iptables iptables-persistent curl git; then
    log_error "Errore nell'installazione dei pacchetti base. Uscita."
    exit 1
fi

# 2. Installazione Stack Web (Nginx, PHP, Utils)
log_info "Installazione Nginx e PHP..."
# Installiamo apache2-utils esplicitamente per htpasswd
if ! apt-get install -y nginx apache2-utils php-fpm php-curl; then
    log_info "Tentativo installazione PHP con versione specifica (fallback)..."
    # Fallback per Ubuntu 24.04 (php8.3) o precedenti
    apt-get install -y nginx apache2-utils php8.3-fpm php8.3-curl || apt-get install -y php8.1-fpm php8.1-curl
fi

# 3. Installazione Python e Venv
log_info "Installazione Python e Venv..."
# Aggiungiamo python3-full per garantire ensurepip e venv
if ! apt-get install -y python3-pip python3-venv sqlite3 python3-full; then
     log_error "Errore nell'installazione di Python/Venv."
     exit 1
fi

# Verifica modulo Kernel (opzionale su kernel recenti)
modprobe wireguard
if [[ $? -ne 0 ]]; then
    log_error "Impossibile caricare il modulo kernel WireGuard. Verifica che sia supportato dal tuo kernel."
    # Non usciamo, potrebbe essere built-in
fi

log_success "Dipendenze installate."

# --- Fase 2: Configurazione Base WireGuard ---
log_info "Fase 2/5: Preparazione ambiente WireGuard..."

# Creazione directory configurazione con permessi stretti
mkdir -p /etc/wireguard
chmod 700 /etc/wireguard

# IP Pubblico (solo per info)
PUBLIC_IP=$(curl -s https://ifconfig.me)
log_info "IP Pubblico rilevato: $PUBLIC_IP"

# Abilitazione IP Forwarding
log_info "Abilitazione IP Forwarding..."
bash ./enable-ip-forwarding.sh

log_success "Ambiente WireGuard pronto."

# --- Fase 3: Deploy Backend ---
log_info "Fase 3/5: Deploy del Backend API..."

mkdir -p /opt/vpn-manager/backend
mkdir -p /opt/vpn-manager/backend/data
mkdir -p /opt/vpn-manager/scripts

# Creazione Venv
if [[ ! -d "/opt/vpn-manager-env" ]]; then
    log_info "Creazione virtual environment Python..."
    python3 -m venv /opt/vpn-manager-env
fi

# Copia file
log_info "Copia file backend..."
cp -r ../backend/* /opt/vpn-manager/backend/
cp -r ../scripts/* /opt/vpn-manager/scripts/

# Installazione dipendenze Python
log_info "Installazione requirements..."
/opt/vpn-manager-env/bin/pip install -r /opt/vpn-manager/backend/requirements.txt

# Generazione API Key
API_KEY_GENERATED=$(cat /proc/sys/kernel/random/uuid)
ENV_FILE="/opt/vpn-manager/backend/.env"
echo "API_KEY=$API_KEY_GENERATED" > "$ENV_FILE"
# Rimuoviamo vecchie variabili OpenVPN dal .env se presenti
echo "WIREGUARD_CONFIG_DIR=/etc/wireguard" >> "$ENV_FILE"

API_KEY="$API_KEY_GENERATED"

# Configurazione Servizio Backend
log_info "Configurazione servizio systemd..."
cat > /etc/systemd/system/vpn-manager.service <<'EOF'
[Unit]
Description=VPN Manager Backend (FastAPI/WireGuard)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vpn-manager/backend
Environment="PATH=/opt/vpn-manager-env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/opt/vpn-manager-env/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Configurazione Persistenza IPTables
chmod +x /opt/vpn-manager/scripts/save-iptables.sh
chmod +x /opt/vpn-manager/scripts/restore-iptables.sh
cp /opt/vpn-manager/scripts/iptables-vpn.service /etc/systemd/system/
# Fix content of service file to point to correct scripts if needed (scripts names match)

systemctl daemon-reload
systemctl enable iptables-vpn.service
systemctl enable vpn-manager.service
systemctl restart vpn-manager.service

log_success "Backend deployato."

# --- Fase 4: Deploy Frontend ---
log_info "Fase 4/5: Deploy Frontend..."

mkdir -p /opt/vpn-manager/frontend
cp -r ../frontend/* /opt/vpn-manager/frontend/

# Configurazione API Key nel frontend
sed -i "s|define('API_KEY', 'mysecretkey');|define('API_KEY', '$API_KEY');|" /opt/vpn-manager/frontend/config.php

# Permessi
chown -R www-data:www-data /opt/vpn-manager/frontend
chmod -R 755 /opt/vpn-manager/frontend

log_success "Frontend deployato."

# --- Fase 5: Nginx ---
log_info "Fase 5/5: Configurazione Nginx..."

mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled
cp ../nginx/vpn-dashboard.conf /etc/nginx/sites-available/
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/vpn-dashboard.conf /etc/nginx/sites-enabled/

# Nginx Basic Auth
HTPASSWD_FILE="/etc/nginx/.htpasswd"
if [[ ! -f "$HTPASSWD_FILE" ]]; then
    log_info "Configurazione utente web..."
    read -rp "Inserisci username per la dashboard: " NGINX_USER
    if [[ -z "$NGINX_USER" ]]; then NGINX_USER="admin"; fi
    htpasswd -Bc "$HTPASSWD_FILE" "$NGINX_USER"
    chmod 644 "$HTPASSWD_FILE"
fi

systemctl restart nginx

log_success "Installazione Completata!"
echo "--------------------------------------------------"
echo "Dashboard: http://$PUBLIC_IP"
echo "API Key:   $API_KEY"
echo "--------------------------------------------------"
echo "NOTA: Il sistema è ora configurato per WireGuard."
echo "Per creare la prima istanza VPN, usa l'interfaccia web."