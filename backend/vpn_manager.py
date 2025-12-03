import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Percorsi e Costanti ---
OPENVPN_SCRIPT_PATH = os.getenv("OPENVPN_SCRIPT_PATH", "/root/openvpn-install.sh")
EASYRSA_PKI_PATH = "/etc/openvpn/server/easy-rsa/pki/"
INDEX_FILE_PATH = os.path.join(EASYRSA_PKI_PATH, "index.txt")
STATUS_LOG_PATH = "/var/log/openvpn/status.log"

# --- Funzioni di Basso Livello ---

def _run_command(command):
    """Esegue un comando di shell e restituisce output e codice di uscita."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            env=dict(os.environ, AUTO_INSTALL='y', APPROVE_INSTALL='y', PASS='1')
        )
        return result.stdout.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stderr.strip(), e.returncode

def get_all_clients_from_index():
    """
    Legge il file index.txt di Easy-RSA per ottenere tutti i client validi (non revocati).
    Restituisce una lista di dizionari con 'name' e 'status'.
    """
    clients = []
    if not os.path.exists(INDEX_FILE_PATH):
        return clients

    with open(INDEX_FILE_PATH, "r") as f:
        for line in f:
            parts = line.strip().split()
            if parts[0] == "V":  # 'V' sta per Valido
                # Il nome del client si trova dopo l'ID univoco
                client_name = parts[-1].split("=")[-1]
                if client_name != "server": # Escludi il certificato del server
                    clients.append({"name": client_name, "status": "disconnected"})
    return clients

def get_connected_clients_from_log():
    """
    Legge il file di log dello stato di OpenVPN per ottenere i client connessi.
    Restituisce un dizionario con i client connessi e i loro dettagli.
    """
    connected_clients = {}
    if not os.path.exists(STATUS_LOG_PATH):
        return connected_clients

    with open(STATUS_LOG_PATH, "r") as f:
        lines = f.readlines()

    # La sezione dei client connessi inizia dopo "ROUTING TABLE"
    try:
        client_section_start = lines.index("ROUTING TABLE\n") + 1
        for line in lines[client_section_start:]:
            if "CLIENT_LIST" not in line:
                continue
            
            parts = line.strip().split(',')
            # Formato: CLIENT_LIST,Common Name,Real Address,Virtual Address,Bytes Received,Bytes Sent,Connected Since
            client_name = parts[1]
            connected_since_str = parts[6]
            connected_since_dt = datetime.strptime(connected_since_str, "%a %b %d %H:%M:%S %Y")
            
            connected_clients[client_name] = {
                "virtual_ip": parts[3],
                "real_ip": parts[2].split(":")[0],
                "connected_since": connected_since_dt.isoformat()
            }
    except ValueError:
        # Se "ROUTING TABLE" non è trovato, non ci sono client o il log è vuoto
        pass

    return connected_clients

# --- Funzioni Principali Esposte all'API ---

def list_clients():
    """
    Combina le informazioni dai file di indice e di log per dare uno stato completo.
    """
    all_clients = get_all_clients_from_index()
    connected_clients = get_connected_clients_from_log()

    for client in all_clients:
        if client["name"] in connected_clients:
            client["status"] = "connected"
            client.update(connected_clients[client["name"]])

    return all_clients

def create_client(client_name: str):
    """
    Crea un nuovo client OpenVPN e restituisce il contenuto del file .ovpn.
    """
    command = f"CLIENT='{client_name}' {OPENVPN_SCRIPT_PATH}"
    output, exit_code = _run_command(command)

    if exit_code != 0:
        return None, f"Errore durante la creazione del client: {output}"

    # Lo script crea il file in /root/client_name.ovpn
    config_path = f"/root/{client_name}.ovpn"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config_content = f.read()
        
        os.remove(config_path) # Pulisci il file dopo averlo letto
        return config_content, None
    else:
        return None, "File di configurazione .ovpn non trovato dopo la creazione."

def revoke_client(client_name: str):
    """
    Revoca un client OpenVPN esistente.
    """
    # Lo script di angristan richiede di passare il numero del client da revocare.
    # Prima otteniamo la lista dei client per trovare il numero corretto.
    
    clients_from_index = [c["name"] for c in get_all_clients_from_index()]
    if client_name not in clients_from_index:
        return False, f"Client '{client_name}' non trovato."

    try:
        # L'indice per lo script è 1-based
        client_index = clients_from_index.index(client_name) + 1
    except ValueError:
        return False, f"Client '{client_name}' non trovato."

    command = f"MENU_OPTION='2' CLIENT_TO_REVOKE='{client_index}' {OPENVPN_SCRIPT_PATH}"
    output, exit_code = _run_command(command)

    if exit_code != 0:
        return False, f"Errore durante la revoca del client: {output}"

    return True, f"Client '{client_name}' revocato con successo."
