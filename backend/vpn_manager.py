import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Percorsi e Costanti (Configurabili tramite .env) ---
OPENVPN_SCRIPT_PATH = os.getenv("OPENVPN_SCRIPT_PATH", "/usr/local/bin/openvpn-install.sh")
INDEX_FILE_PATH = os.getenv("INDEX_FILE_PATH", "/etc/openvpn/easy-rsa/pki/index.txt")
STATUS_LOG_PATH = os.getenv("STATUS_LOG_PATH", "/var/log/openvpn/status.log")
CLIENT_CONFIG_DIR = os.getenv("CLIENT_CONFIG_DIR", "/root")
EASYRSA_DIR = "/etc/openvpn/easy-rsa"
OPENVPN_DIR = "/etc/openvpn"
IPP_FILE = f"{OPENVPN_DIR}/ipp.txt"

# --- Funzioni di Basso Livello ---

def _run_command(command, input_str=None, env_vars=None):
    """Esegue un comando di shell e restituisce output e codice di uscita.
    Accetta un input_str opzionale per fornire input allo stdin del processo.
    Accetta un dict env_vars opzionale per le variabili d'ambiente aggiuntive.
    Se env_vars è None, usa le variabili di default per openvpn-install.sh.
    Se env_vars è un dict vuoto, non aggiunge variabili d'ambiente.
    """
    if env_vars is None:
        # Default env vars for openvpn-install.sh
        effective_env = dict(os.environ, AUTO_INSTALL='y', APPROVE_INSTALL='y', PASS='1')
    elif env_vars == {}:
        # No extra env vars
        effective_env = os.environ
    else:
        # Custom env vars
        effective_env = dict(os.environ, **env_vars)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            input=input_str,
            env=effective_env
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
                if not client_name.startswith("server"): # Escludi il certificato del server
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
    output, exit_code = _run_command(command) # env_vars=None uses default AUTO_INSTALL etc.

    if exit_code != 0:
        return None, f"Errore durante la creazione del client: {output}"

    # Lo script crea il file in CLIENT_CONFIG_DIR
    config_path = os.path.join(CLIENT_CONFIG_DIR, f"{client_name}.ovpn")
    if os.path.exists(config_path):
        return True, None # Indicate success, no content returned here
    else:
        return False, f"File di configurazione .ovpn non trovato in {CLIENT_CONFIG_DIR} dopo la creazione."

def get_client_config(client_name: str):
    """
    Restituisce il contenuto di un file di configurazione .ovpn esistente.
    """
    config_path = os.path.join(CLIENT_CONFIG_DIR, f"{client_name}.ovpn")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config_content = f.read()
        return config_content, None
    else:
        return None, f"File di configurazione per il client '{client_name}' non trovato."

def revoke_client(client_name: str):
    """
    Revoca un client OpenVPN esistente usando lo script esterno sudo-enabled.
    """
    # Il percorso dello script esterno di revoca
    revoke_script_path = "/opt/vpn-manager/scripts/revoke-client.sh"
    
    # Eseguiamo lo script esterno. Lo script stesso gestirà i permessi di root.
    command = f"{revoke_script_path} {client_name}"
    
    # Chiamiamo _run_command con env_vars={} per non passare AUTO_INSTALL, ecc.
    output, exit_code = _run_command(command, env_vars={})
    
    if exit_code != 0:
        return False, f"Errore durante la revoca: {output}"

    return True, f"Client '{client_name}' revocato con successo."
