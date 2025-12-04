#!/bin/bash
# /scripts/create-client.sh
# Questo script crea un nuovo client OpenVPN usando Easy-RSA e genera il file .ovpn.
# Richiede privilegi di root.

CLIENT_NAME="$1"

if [[ -z "$CLIENT_NAME" ]]; then
    echo "Usage: $0 <client_name>" >&2
    exit 1
fi

# Validazione del nome client - permette alfanumerici, underscore, trattini e punti
if ! [[ "$CLIENT_NAME" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "Nome client non valido. Usare solo lettere, numeri, trattini (-), underscore (_) e punti (.)." >&2
    exit 1
fi

EASYRSA_DIR="/etc/openvpn/easy-rsa"
OPENVPN_DIR="/etc/openvpn"
CLIENT_CONFIG_DIR="/root" # Abbiamo deciso di usare sempre /root per i file generati

log_error() {
  echo "[ERROR] $1" >&2
  exit 1
}

# Controlla se il client esiste già nel database Easy-RSA
# Utilizziamo grep -F per una ricerca di stringa fissa e evitiamo interpretazioni regex del punto
CLIENTEXISTS=$(tail -n +2 "$EASYRSA_DIR/pki/index.txt" | grep -F -c "/CN=$CLIENT_NAME")
if [[ $CLIENTEXISTS == '1' ]]; then
    echo "Un client con il nome '$CLIENT_NAME' esiste già." >&2
    exit 1
fi

# 1. Crea il certificato del client usando Easy-RSA
if ! cd "$EASYRSA_DIR"; then
    log_error "Impossibile accedere alla directory Easy-RSA."
fi

# Creiamo sempre un client senza password per semplicità nell'API
if ! EASYRSA_CERT_EXPIRE=3650 ./easyrsa --batch build-client-full "$CLIENT_NAME" nopass; then
    log_error "Errore durante la creazione del certificato Easy-RSA per $CLIENT_NAME."
fi

# 2. Genera il file .ovpn
# Assicurati che CLIENT_CONFIG_DIR esista
mkdir -p "$CLIENT_CONFIG_DIR"

# Determina se usiamo tls-auth o tls-crypt
TLS_SIG=""
if grep -qs "^tls-crypt" "$OPENVPN_DIR/server.conf"; then
    TLS_SIG="tls-crypt"
elif grep -qs "^tls-auth" "$OPENVPN_DIR/server.conf"; then
    TLS_SIG="tls-auth"
fi

OVPN_FILE="$CLIENT_CONFIG_DIR/$CLIENT_NAME.ovpn"
cp "$OPENVPN_DIR/client-template.txt" "$OVPN_FILE" || log_error "Errore durante la copia del template client."

{
    echo "<ca>"
    cat "$EASYRSA_DIR/pki/ca.crt"
    echo "</ca>"

    echo "<cert>"
    awk '/BEGIN/,/END CERTIFICATE/' "$EASYRSA_DIR/pki/issued/$CLIENT_NAME.crt"
    echo "</cert>"

    echo "<key>"
    cat "$EASYRSA_DIR/pki/private/$CLIENT_NAME.key"
    echo "</key>"

    case $TLS_SIG in
    "tls-crypt")
        echo "<tls-crypt>"
        cat "$OPENVPN_DIR/tls-crypt.key"
        echo "</tls-crypt>"
        ;;
    "tls-auth")
        echo "key-direction 1"
        echo "<tls-auth>"
        cat "$OPENVPN_DIR/tls-auth.key"
        echo "</tls-auth>"
        ;;
    esac
} >>"$OVPN_FILE" || log_error "Errore durante l'aggiunta delle chiavi al file OVPN."

echo "Client $CLIENT_NAME creato con successo. File: $OVPN_FILE"
exit 0
