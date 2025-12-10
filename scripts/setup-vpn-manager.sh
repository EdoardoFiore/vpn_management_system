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

# Funzione per cercare un file in una lista di percorsi, con fallback find
find_file_in_paths() {
  local filename="$1"
  shift
  local paths=("$@")
  local found_path=""

  # Cerca nei percorsi predefiniti
  for p in "${paths[@]}"; do
    if [[ -f "$p" ]]; then
      found_path="$p"
      break
    fi
  done

  # Se non trovato, prova con find
  if [[ -z "$found_path" ]]; then
    log_info "File '$filename' non trovato nei percorsi standard. Tentativo di ricerca dinamica..."
    found_path=$(find / -xdev -type f -name "$filename" 2>/dev/null | head -n 1)
  fi
  echo "$found_path"
}

# Funzione per cercare una directory in una lista di percorsi, con fallback find
find_dir_in_paths() {
  local dirname="$1"
  shift
  local paths=("$@")
  local found_path=""

  # Cerca nei percorsi predefiniti
  for p in "${paths[@]}"; do
    if [[ -d "$p" ]]; then
      found_path="$p"
      break
    fi
  done

  # Se non trovato, prova con find
  if [[ -z "$found_path" ]]; then
    log_info "Directory '$dirname' non trovata nei percorsi standard. Tentativo di ricerca dinamica..."
    found_path=$(find / -xdev -type d -name "$dirname" 2>/dev/null | head -n 1)
  fi
  echo "$found_path"
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
EOF
  echo -e "\033[0m"
}

# --- Controllo Esecuzione come Root ---
if [[ $EUID -ne 0 ]]; then
  log_error "Questo script deve essere eseguito come root. Usa 'sudo bash setup-vpn-manager.sh'"
  exit 1
fi

print_banner
echo ""
log_info "Benvenuto nel programma di installazione automatico."
echo ""
echo -n "Inizio installazione in "
for i in 3 2 1; do
  echo -n "$i... "
  sleep 1
done
echo ""

# --- Inizio Installazione ---
log_info "Avvio dell'installazione del sistema di gestione VPN..."

# --- Fase 1: Aggiornamento del sistema e installazione dipendenze ---
log_info "Fase 1/5: Aggiornamento del sistema e installazione delle dipendenze..."

apt-get update && apt-get upgrade -y

log_info "Aggiunta del repository PPA per PHP 8.1..."
apt-get install -y software-properties-common apt-transport-https
add-apt-repository ppa:ondrej/php -y
apt-get update

if ! apt-get install -y nginx python3-pip python3-venv php8.1-fpm php8.1-curl curl apache2-utils; then
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
export AUTO_INSTALL=y
export APPROVE_INSTALL=y
export APPROVE_IP=y
export IPV6_SUPPORT=n
export PORT_CHOICE=1
export PROTOCOL_CHOICE=1
export DNS=9
export COMPRESSION_ENABLED=n
export CUSTOMIZE_ENC=n
export CLIENT=test-client
export PASS=1

./openvpn-install.sh

if [[ ! -f /etc/openvpn/server.conf ]]; then
  log_error "L'installazione di OpenVPN sembra essere fallita (file di configurazione non trovato)."
  exit 1
fi

log_success "OpenVPN installato e configurato con successo. Un primo client 'test-client.ovpn' è stato creato in /root/."

# La configurazione avanzata (es. Split Tunneling) può essere gestita tramite la Dashboard Web.
log_info "OpenVPN è pronto. Le configurazioni avanzate possono essere effettuate via Web UI."

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

# Copia i file degli script e rendi revoke-client.sh ed create-client.sh eseguibili
log_info "Copia dei file degli script..."
mkdir -p /opt/vpn-manager/scripts
cp -r ../scripts/* /opt/vpn-manager/scripts/
chmod +x /opt/vpn-manager/scripts/revoke-client.sh
chmod +x /opt/vpn-manager/scripts/create-client.sh

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

# Genera una API key sicura e la inserisce nel file .env
API_KEY_GENERATED=$(cat /proc/sys/kernel/random/uuid)
ENV_FILE="/opt/vpn-manager/backend/.env"

# --- Ricerca dinamica dei percorsi ---
log_info "Ricerca dinamica dei percorsi critici di OpenVPN e Easy-RSA..."

# OPENVPN_DIR: Cercare /etc/openvpn o dove si trova server.conf
OPENVPN_DIR=$(find_dir_in_paths "openvpn" "/etc/openvpn" "/usr/local/etc/openvpn")
if [[ -z "$OPENVPN_DIR" ]]; then
    log_error "Impossibile trovare la directory di configurazione OpenVPN. Si prega di installare OpenVPN o specificare manualmente il percorso."
fi
log_info "OpenVPN directory trovata: $OPENVPN_DIR"

# EASYRSA_DIR: Cercare easy-rsa
EASYRSA_DIR=$(find_dir_in_paths "easy-rsa" "/etc/openvpn/easy-rsa" "/usr/share/easy-rsa" "/usr/local/share/easy-rsa" "$OPENVPN_DIR/easy-rsa")
if [[ -z "$EASYRSA_DIR" ]]; then
    log_error "Impossibile trovare la directory Easy-RSA. Si prega di installare Easy-RSA o specificare manualmente il percorso."
fi
log_info "Easy-RSA directory trovata: $EASYRSA_DIR"

# OPENVPN_SCRIPT_PATH: Dove abbiamo spostato lo script di installazione
OPENVPN_SCRIPT_PATH="/usr/local/bin/openvpn-install.sh"
if [[ ! -f "$OPENVPN_SCRIPT_PATH" ]]; then
    log_error "Script openvpn-install.sh non trovato in $OPENVPN_SCRIPT_PATH. Assicurarsi che la Fase 2 sia stata eseguita correttamente."
fi
log_info "openvpn-install.sh path: $OPENVPN_SCRIPT_PATH"

# INDEX_FILE_PATH: Derivato da EASYRSA_DIR
INDEX_FILE_PATH="$EASYRSA_DIR/pki/index.txt"
if [[ ! -f "$INDEX_FILE_PATH" ]]; then
    log_error "File index.txt di Easy-RSA non trovato in $INDEX_FILE_PATH. Assicurarsi che Easy-RSA sia configurato correttamente."
fi
log_info "index.txt path: $INDEX_FILE_PATH"

# STATUS_LOG_PATH: Cercare un file status.log (potrebbe variare) o usare default
STATUS_LOG_PATH=$(find_file_in_paths "status.log" "/var/log/openvpn/status.log" "$OPENVPN_DIR/log/status.log")
# Se non trova il log, usa un default comune (potrebbe essere necessario aggiustare)
if [[ -z "$STATUS_LOG_PATH" ]]; then
    log_info "File status.log di OpenVPN non trovato. Utilizzo del default: /var/log/openvpn/status.log"
    STATUS_LOG_PATH="/var/log/openvpn/status.log"
fi
log_info "status.log path: $STATUS_LOG_PATH"

# CLIENT_CONFIG_DIR: Nostra decisione, rimane /root
CLIENT_CONFIG_DIR="/root"
log_info "Client config directory: $CLIENT_CONFIG_DIR"

# IPP_FILE: Derivato da OPENVPN_DIR
IPP_FILE="$OPENVPN_DIR/ipp.txt"
# Non è un errore critico se ipp.txt non esiste subito, verrà creato da OpenVPN
log_info "IPP file path: $IPP_FILE"

# --- Scrittura nel file .env ---
echo "API_KEY=$API_KEY_GENERATED" > "$ENV_FILE"
echo "OPENVPN_SCRIPT_PATH=$OPENVPN_SCRIPT_PATH" >> "$ENV_FILE"
echo "INDEX_FILE_PATH=$INDEX_FILE_PATH" >> "$ENV_FILE"
echo "STATUS_LOG_PATH=$STATUS_LOG_PATH" >> "$ENV_FILE"
echo "CLIENT_CONFIG_DIR=$CLIENT_CONFIG_DIR" >> "$ENV_FILE"
echo "EASYRSA_DIR=$EASYRSA_DIR" >> "$ENV_FILE"
echo "OPENVPN_DIR=$OPENVPN_DIR" >> "$ENV_FILE"
echo "IPP_FILE=$IPP_FILE" >> "$ENV_FILE"

log_info "API Key e variabili di configurazione generate e configurate nel .env del backend."

# Assegna la chiave generata ad API_KEY per il resto dello script (es. per il frontend PHP)
API_KEY="$API_KEY_GENERATED"


log_info "Creazione della sistemd unit per il backend..."
cat > /etc/systemd/system/vpn-manager.service <<'EOF'
[Unit]
Description=VPN Manager Backend (FastAPI/Uvicorn)
After=network.target openvpn.service

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

log_info "Abilitazione IP forwarding per OpenVPN..."
bash /opt/vpn-manager/scripts/enable-ip-forwarding.sh

log_info "Configurazione iptables persistence..."
chmod +x /opt/vpn-manager/scripts/save-iptables.sh
chmod +x /opt/vpn-manager/scripts/restore-iptables.sh
cp /opt/vpn-manager/scripts/iptables-openvpn.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable iptables-openvpn.service

systemctl daemon-reload
systemctl enable vpn-manager.service
systemctl start vpn-manager.service

log_info "Copia dei file del frontend..."
mkdir -p /opt/vpn-manager/frontend
cp -r ../frontend/* /opt/vpn-manager/frontend/

# Inserisce la stessa API Key nel file di configurazione PHP del frontend
sed -i "s|define('API_KEY', 'mysecretkey');|define('API_KEY', '$API_KEY');|" /opt/vpn-manager/frontend/config.php

systemctl daemon-reload
systemctl enable vpn-manager.service
systemctl start vpn-manager.service

# Verifica che il servizio sia attivo
if ! systemctl is-active --quiet vpn-manager.service; then
  log_error "Il servizio del backend non è riuscito a partire. Controlla i log con 'journalctl -u vpn-manager.service'"
  exit 1
fi

log_success "Backend API deployato e in esecuzione."

# --- Fase 4: Deploy del Frontend (PHP) ---
log_info "Fase 4/5: Deploy del frontend..."

# Assicurarsi che i permessi siano corretti per il server web (es. www-data)
chown -R www-data:www-data /opt/vpn-manager/frontend
chmod -R 755 /opt/vpn-manager/frontend

# Rimuovere il file api_key.env non più necessario
rm -f /root/api_key.env

log_success "Frontend PHP deployato con successo."

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

# --- Configurazione Nginx Basic Auth ---
log_info "Fase 5/5: Configurazione Nginx Basic Auth..."

echo -e "\033[1;35m"
cat << "EOF"
 _   _  _____  _____  _____    
| | | |/  ___||  ___|| ___ \    
| | | |\ `--. | |__  | |_/ /  
| | | | `--. \|  __| |    /   
| |_| |/\__/ /| |___ | |\ \  
 \___/ \____/ \____/ \_| \_|   
EOF
echo -e "\033[0m"

HTPASSWD_FILE="/etc/nginx/.htpasswd"

while true; do
    read -rp "Inserisci il nome utente per accedere alla dashboard web: " NGINX_USER

    if [[ -z "$NGINX_USER" ]]; then
        log_error "Il nome utente non può essere vuoto."
        continue
    fi

    # La password verrà richiesta da htpasswd stesso
    # Usiamo -c per creare/sovrascrivere il file la prima volta
    htpasswd -Bc "$HTPASSWD_FILE" "$NGINX_USER"

    if [[ $? -eq 0 ]]; then
        log_success "Utente Nginx Basic Auth '$NGINX_USER' creato con successo."
        break
    else
        log_error "Creazione utente fallita (probabile mismatch password). Riprova."
        echo "Premi INVIO per riprovare, o Ctrl+C per annullare (Attenzione: l'installazione è quasi finita)."
        read
    fi
done

chmod 644 "$HTPASSWD_FILE" # Assicurati che Nginx possa leggere il file

# Riavvia Nginx per applicare le modifiche all'autenticazione (htpasswd e nginx.conf)
log_info "Riavvio di Nginx per applicare le modifiche all'autenticazione..."
systemctl restart nginx
if [[ $? -ne 0 ]]; then
    log_error "Riavvio del servizio Nginx fallito dopo la configurazione auth."
    exit 1
fi
log_success "Nginx riavviato con successo per la configurazione Basic Auth."

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
