#!/bin/bash
# /scripts/revoke-client.sh
# Questo script esegue le operazioni di revoca client che richiedono privilegi di root.

CLIENT_NAME="$1"

if [[ -z "$CLIENT_NAME" ]]; then
    echo "Usage: $0 <client_name>" >&2
    exit 1
fi

EASYRSA_DIR="/etc/openvpn/easy-rsa"
OPENVPN_DIR="/etc/openvpn"
IPP_FILE="${OPENVPN_DIR}/ipp.txt"

log_error() {
  echo "[ERROR] $1" >&2
  exit 1
}

# 1. Revoca certificato Easy-RSA
# Utilizza l'opzione --batch per evitare domande interattive
if ! cd "$EASYRSA_DIR" || ! ./easyrsa --batch revoke "$CLIENT_NAME"; then
    # Controlla se l'errore è dovuto al client già revocato
    if grep -q "already revoked" <<< "$?"; then # Cerca nel codice di uscita del comando precedente
        echo "Client $CLIENT_NAME già revocato."
    else
        log_error "Errore durante la revoca del certificato Easy-RSA per $CLIENT_NAME."
    fi
fi

# 2. Genera la nuova Certificate Revocation List (CRL)
if ! EASYRSA_CRL_DAYS=3650 ./easyrsa gen-crl; then
    log_error "Errore durante la generazione della CRL."
fi

# 3. Copia la nuova CRL nella directory di OpenVPN
if ! cp "$EASYRSA_DIR/pki/crl.pem" "$OPENVPN_DIR/crl.pem"; then
    log_error "Errore durante la copia della CRL."
fi
if ! chmod 644 "$OPENVPN_DIR/crl.pem"; then
    log_error "Errore durante la modifica dei permessi della CRL."
fi

# 4. Cancella eventuali file .ovpn generati precedentemente per questo client
# Cerca in /home/ e in /root/
find /home/ -maxdepth 2 -name "${CLIENT_NAME}.ovpn" -delete 2>/dev/null
rm -f "/root/${CLIENT_NAME}.ovpn" 2>/dev/null

# 5. Rimuove il client da ipp.txt (se esiste e se il client ha un IP fisso)
if [ -f "$IPP_FILE" ]; then
    sed -i "/^${CLIENT_NAME},.*/d" "$IPP_FILE"
fi

# 6. Riavvia il servizio OpenVPN per applicare la nuova CRL
if ! systemctl restart openvpn.service; then
    log_error "Errore durante il riavvio del servizio OpenVPN."
fi

echo "Client $CLIENT_NAME revocato con successo e CRL aggiornata."
exit 0