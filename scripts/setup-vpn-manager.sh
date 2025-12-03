#!/bin/bash

# =================================================================
#            VPN Management System - Main Installer
# =================================================================
# Questo script installa e configura l'intero sistema di gestione
# della VPN, inclusi OpenVPN, il backend API e il frontend web.
# =================================================================

# --- Funzioni di Logging per un output pulito ---
log_info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

log_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

log_error() {
    echo -e "\033[31m[ERROR]\033[0m $1" >&2
}

# --- Controllo Esecuzione come Root ---
if [[ $EUID -ne 0 ]]; then
   log_error "Questo script deve essere eseguito come root. Usa 'sudo bash setup-vpn-manager.sh'"
   exit 1
fi

# --- Inizio Installazione ---
log_info "Avvio dell'installazione del sistema di gestione VPN..."

# --- Fase 1: Aggiornamento del sistema e installazione dipendenze ---
log_info "Fase 1/5: Aggiornamento del sistema e installazione delle dipendenze..."

apt-get update && apt-get upgrade -y

if ! apt-get install -y nginx python3-pip python3-venv nodejs npm curl; then
    log_error "Installazione delle dipendenze di base fallita."
    exit 1
fi

log_success "Dipendenze installate con successo."

# --- Fase 2: Installazione e Configurazione di OpenVPN ---
log_info "Fase 2/5: Installazione e configurazione di OpenVPN..."

# Tenta di rilevare l'IP pubblico. Se fallisce, esce.
PUBLIC_IP=$(curl -s https://ifconfig.me)
if [[ -z "$PUBLIC_IP" ]]; then
    log_error "Impossibile determinare l'IP pubblico della macchina."
    exit 1
fi
log_info "IP pubblico rilevato: $PUBLIC_IP"

# Scarica lo script di installazione di OpenVPN
log_info "Download dello script di installazione di OpenVPN..."
curl -O https://raw.githubusercontent.com/angristan/openvpn-install/master/openvpn-install.sh
if [[ $? -ne 0 ]]; then
    log_error "Download dello script 'openvpn-install.sh' fallito."
    exit 1
fi
chmod +x openvpn-install.sh

# Esegue lo script in modalità non interattiva
# NOTA: questo crea un primo utente chiamato 'test-client'
log_info "Esecuzione dello script di installazione di OpenVPN in modalità non interattiva..."
AUTO_INSTALL=y \
ENDPOINT="$PUBLIC_IP" \
APPROVE_INSTALL=y \
APPROVE_IP=y \
PORT_CHOICE=1 # Default: 1194
PROTOCOL_CHOICE=1 # Default: UDP
DNS_CHOICE=1 # Default: Current system resolvers
COMPRESSION_CHOICE=2 # Default: No
CLIENT="test-client" \
PASS=1 \
./openvpn-install.sh

if [[ ! -f /etc/openvpn/server/server.conf ]]; then
    log_error "L'installazione di OpenVPN sembra essere fallita (file di configurazione non trovato)."
    exit 1
fi

log_success "OpenVPN installato e configurato con successo. Un primo client 'test-client.ovpn' è stato creato in /root/."

# --- Configurazione opzionale per Split-Tunneling ---
declare -a split_tunnel_routes=()
log_info "Configurazione Split-Tunneling (opzionale)..."

while true; do
    read -p "Vuoi aggiungere una rete privata da instradare via VPN? (es. 192.168.1.0 255.255.255.0). Lascia vuoto per terminare: " route_input
    
    # Se l'input è vuoto, esci dal loop
    if [[ -z "$route_input" ]]; then
        break
    fi

    # Semplice validazione per assicurarsi che ci sia uno spazio tra rete e maschera
    if [[ "$route_input" != *" "* ]]; then
        log_error "Formato non valido. Assicurati di inserire INDIRIZZO RETE <spazio> SUBNET MASK."
        continue
    fi

    split_tunnel_routes+=("$route_input")
    log_info "Aggiunta rotta: $route_input"
done

# Se sono state aggiunte rotte, modifica la configurazione del server
if [[ ${#split_tunnel_routes[@]} -gt 0 ]]; then
    log_info "Applicazione della configurazione split-tunneling..."
    
    # Commenta il redirect-gateway di default
    sed -i 's|^push "redirect-gateway def1.*|# &|' /etc/openvpn/server/server.conf
    if [[ $? -ne 0 ]]; then
        log_error "Modifica di server.conf per lo split-tunneling fallita."
        exit 1
    fi
    
    # Aggiunge le nuove rotte
    for route in "${split_tunnel_routes[@]}"; do
        echo "push \"route $route\"" >> /etc/openvpn/server/server.conf
    done
    
    # Riavvia OpenVPN per applicare le modifiche
    log_info "Riavvio di OpenVPN per applicare la nuova configurazione..."
    systemctl restart openvpn-server@server.service
    log_success "Split-tunneling configurato con le rotte specificate."
else
    log_info "Nessuna rotta specificata. Verrà utilizzato il full-tunneling di default (tutto il traffico attraverso la VPN)."
fi

# Sposta lo script di openvpn in una posizione accessibile dal backend
mv ./openvpn-install.sh /usr/local/bin/openvpn-install.sh

# --- Fase 3: Deploy del Backend API (FastAPI) ---
log_info "Fase 3/5: Deploy del backend API..."

# Creazione directory e ambiente virtuale
log_info "Creazione ambiente per il backend..."
mkdir -p /opt/vpn-manager/backend
python3 -m venv /opt/vpn-manager-env

# Copia i file del backend
# Assumiamo che lo script venga eseguito dalla root del repo scompattato
log_info "Copia dei file del backend..."
cp -r ../backend/* /opt/vpn-manager/backend/

# Installa le dipendenze
log_info "Installazione delle dipendenze Python..."
/opt/vpn-manager-env/bin/pip install -r /opt/vpn-manager/backend/requirements.txt
if [[ $? -ne 0 ]]; then
    log_error "Installazione delle dipendenze Python fallita."
    exit 1
fi

# Creazione e avvio del servizio systemd
log_info "Impostazione del servizio di systemd per il backend..."
cp /opt/vpn-manager/backend/vpn-manager.service /etc/systemd/system/

# Genera una API key sicura e la inserisce nel file .env e la esporta per il frontend
API_KEY=$(cat /proc/sys/kernel/random/uuid)
echo "API_KEY=$API_KEY" > /opt/vpn-manager/backend/.env
# La esportiamo in un file per poterla usare dopo nel frontend
echo "export REACT_APP_API_KEY=$API_KEY" > /root/api_key.env

log_info "API Key generata: $API_KEY"

systemctl daemon-reload
systemctl enable vpn-manager.service
systemctl start vpn-manager.service

# Verifica che il servizio sia attivo
if ! systemctl is-active --quiet vpn-manager.service; then
    log_error "Il servizio del backend non è riuscito a partire. Controlla i log con 'journalctl -u vpn-manager.service'"
    exit 1
fi

log_success "Backend API deployato e in esecuzione."

# --- Fase 4: Deploy del Frontend (React) ---
log_info "Fase 4/5: Deploy del frontend..."

# Creazione directory
log_info "Copia dei file del frontend..."
mkdir -p /opt/vpn-manager/frontend
cp -r ../frontend/* /opt/vpn-manager/frontend/

# Installa le dipendenze e builda il progetto
log_info "Installazione delle dipendenze Node.js e build del frontend..."
cd /opt/vpn-manager/frontend

# Carica la REACT_APP_API_KEY generata in precedenza per il processo di build
source /root/api_key.env
npm install
npm run build

if [[ $? -ne 0 ]]; then
    log_error "Build del frontend fallita."
    cd - > /dev/null # Torna alla directory precedente
    exit 1
fi

cd - > /dev/null # Torna alla directory precedente
log_success "Frontend deployato e buildato con successo."

# --- Fase 5: Configurazione di Nginx ---
log_info "Fase 5/5: Configurazione di Nginx..."

# Copia il file di configurazione Nginx
log_info "Copia del file di configurazione Nginx..."
cp ../nginx/vpn-dashboard.conf /etc/nginx/sites-available/
if [[ $? -ne 0 ]]; then
    log_error "Copia del file di configurazione Nginx fallita."
    exit 1
fi

# Rimuove il sito Nginx di default e abilita il nostro
log_info "Abilitazione della configurazione Nginx..."
rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/vpn-dashboard.conf /etc/nginx/sites-enabled/
if [[ $? -ne 0 ]]; then
    log_error "Abilitazione della configurazione Nginx fallita."
    exit 1
fi

# Testa la configurazione Nginx
log_info "Test della configurazione Nginx..."
nginx -t
if [[ $? -ne 0 ]]; then
    log_error "Test della configurazione Nginx fallito. Controlla i file di configurazione."
    exit 1
fi

# Riavvia Nginx
log_info "Riavvio del servizio Nginx..."
systemctl restart nginx
if [[ $? -ne 0 ]]; then
    log_error "Riavvio del servizio Nginx fallito."
    exit 1
fi

log_success "Nginx configurato e riavviato con successo."

log_success "Installazione completata!"
echo "--------------------------------------------------"
echo "Ora puoi accedere all'interfaccia web all'indirizzo:"
echo -e "\033[1;36mhttp://$PUBLIC_IP\033[0m"
echo ""
echo "La chiave API per la dashboard (necessaria se la UI la richiede manualmente) è:"
echo -e "\033[1;33m$API_KEY\033[0m"
echo ""
echo "Un client OpenVPN di test ('test-client.ovpn') è stato generato in /root/."
echo "Scaricalo con 'sudo cat /root/test-client.ovpn' per connetterti."
echo "--------------------------------------------------"
