import os
import subprocess
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
import instance_manager

load_dotenv()
logger = logging.getLogger(__name__)

# --- Percorsi e Costanti ---
EASYRSA_DIR = os.getenv("EASYRSA_DIR", "/etc/openvpn/easy-rsa")
CLIENT_CONFIG_DIR = os.getenv("CLIENT_CONFIG_DIR", "/root")

# --- Funzioni Helper ---

def _run_command(command, env_vars=None):
    """Esegue un comando shell."""
    effective_env = dict(os.environ, **(env_vars or {}))
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            env=effective_env
        )
        return result.stdout.strip(), 0
    except subprocess.CalledProcessError as e:
        return e.stderr.strip(), e.returncode

def _read_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return ""

# --- Gestione Client ---

def list_clients(instance_id: str) -> List[Dict]:
    """
    Restituisce la lista dei client per una specifica istanza.
    Nota: Easy-RSA è condiviso, quindi 'get_all_clients_from_index' restituisce TUTTI i client.
    Tuttavia, lo stato di connessione è specifico per istanza.
    """
    instance = instance_manager.get_instance(instance_id)
    if not instance:
        raise ValueError("Instance not found")

    all_clients = _get_all_clients_from_pki()
    connected_clients = _get_connected_clients(instance.name)

    # Filtriamo i client? Per ora mostriamo tutti i certificati validi.
    # In un sistema multi-tenant reale, dovremmo associare i client alle istanze (es. via DB o prefisso nome).
    # Per ora, assumiamo che tutti i client siano visibili su tutte le istanze, 
    # ma lo stato "connected" dipenderà dall'istanza specifica.
    
    # TODO: Implementare un filtro per mostrare solo i client "appartenenti" a questa istanza se necessario.
    # Per ora, restituiamo tutti.

    for client in all_clients:
        if client["name"] in connected_clients:
            client["status"] = "connected"
            client.update(connected_clients[client["name"]])
        else:
            client["status"] = "disconnected"
            
    return all_clients

def _get_all_clients_from_pki():
    clients = []
    index_path = os.path.join(EASYRSA_DIR, "pki/index.txt")
    if not os.path.exists(index_path):
        return clients

    with open(index_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if parts[0] == "V":
                client_name = parts[-1].split("=")[-1]
                if not client_name.startswith("server"):
                    clients.append({"name": client_name})
    return clients

def _get_connected_clients(instance_name: str):
    connected_clients = {}
    status_log_path = f"/var/log/openvpn/status_{instance_name}.log"
    
    if not os.path.exists(status_log_path):
        return connected_clients

    try:
        with open(status_log_path, "r") as f:
            lines = f.readlines()
            
        client_section_start = -1
        for i, line in enumerate(lines):
            if "ROUTING TABLE" in line:
                client_section_start = i + 1
                break
        
        if client_section_start != -1:
            for line in lines[client_section_start:]:
                if "CLIENT_LIST" not in line:
                    continue
                parts = line.strip().split(',')
                # CLIENT_LIST,Common Name,Real Address,Virtual Address,Bytes Received,Bytes Sent,Connected Since
                if len(parts) > 6:
                    client_name = parts[1]
                    connected_since_str = parts[6]
                    try:
                        connected_since_dt = datetime.strptime(connected_since_str, "%a %b %d %H:%M:%S %Y")
                        connected_since = connected_since_dt.isoformat()
                    except ValueError:
                        connected_since = connected_since_str

                    connected_clients[client_name] = {
                        "virtual_ip": parts[3],
                        "real_ip": parts[2].split(":")[0],
                        "connected_since": connected_since
                    }
    except Exception as e:
        logger.error(f"Error reading status log for {instance_name}: {e}")

    return connected_clients

def create_client(instance_id: str, client_name: str) -> Tuple[bool, Optional[str]]:
    instance = instance_manager.get_instance(instance_id)
    if not instance:
        return False, "Instance not found"

    # 1. Check if client exists
    existing_clients = _get_all_clients_from_pki()
    if any(c["name"] == client_name for c in existing_clients):
        return False, f"Client '{client_name}' already exists."

    # 2. Create Certificate
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa --batch build-client-full {client_name} nopass"
    out, code = _run_command(cmd, env_vars={"EASYRSA_CERT_EXPIRE": "3650"})
    if code != 0:
        return False, f"Easy-RSA Error: {out}"

    # 3. Generate .ovpn content
    try:
        ovpn_content = _generate_ovpn_content(instance, client_name)
    except Exception as e:
        return False, f"Error generating config: {e}"

    # 4. Save .ovpn file
    config_path = os.path.join(CLIENT_CONFIG_DIR, f"{client_name}.ovpn")
    with open(config_path, "w") as f:
        f.write(ovpn_content)

    return True, None

def get_client_config(client_name: str) -> Tuple[Optional[str], Optional[str]]:
    config_path = os.path.join(CLIENT_CONFIG_DIR, f"{client_name}.ovpn")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return f.read(), None
    return None, "Config not found"

def revoke_client(instance_id: str, client_name: str) -> Tuple[bool, str]:
    instance = instance_manager.get_instance(instance_id)
    if not instance:
        return False, "Instance not found"

    # 1. Revoke
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa --batch revoke {client_name}"
    out, code = _run_command(cmd)
    if code != 0 and "already revoked" not in out:
        return False, f"Revoke Error: {out}"

    # 2. Gen CRL
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa gen-crl"
    out, code = _run_command(cmd, env_vars={"EASYRSA_CRL_DAYS": "3650"})
    if code != 0:
        return False, f"CRL Gen Error: {out}"

    # 3. Copy CRL (Assuming shared CRL path in config)
    # Note: If instances have different CRL paths, we need to handle that.
    # For now, we assume standard location or we copy to where instances expect it.
    # Our instance_manager uses /etc/openvpn/easy-rsa/pki/crl.pem directly in config?
    # Let's check instance_manager.py... it uses os.getenv("CRL_PATH", ...).
    # If OpenVPN reads directly from PKI, we don't need to copy.
    # But usually permissions are an issue.
    # Let's copy to /etc/openvpn/crl.pem as a common place, or update all instances.
    
    # For this implementation, let's assume we copy to /etc/openvpn/crl.pem and all instances use it.
    # Or better, we restart the specific instance to reload CRL if it's configured to read it.
    
    # Restart Service
    service_name = f"openvpn-server@server_{instance.name}"
    subprocess.run(["systemctl", "restart", service_name], check=False)

    return True, f"Client {client_name} revoked."

def _generate_ovpn_content(instance: instance_manager.Instance, client_name: str) -> str:
    # Get Public IP
    public_ip = _get_public_ip()
    
    # Read Certs
    ca = _read_file(os.path.join(EASYRSA_DIR, "pki/ca.crt"))
    cert = _read_file(os.path.join(EASYRSA_DIR, f"pki/issued/{client_name}.crt"))
    key = _read_file(os.path.join(EASYRSA_DIR, f"pki/private/{client_name}.key"))
    
    # Extract cert body
    if "-----BEGIN CERTIFICATE-----" in cert:
        cert = cert[cert.find("-----BEGIN CERTIFICATE-----") : cert.find("-----END CERTIFICATE-----") + 25]

    # TLS Crypt/Auth
    tls_crypt = ""
    tls_auth = ""
    
    # Check for tls-crypt key
    tls_crypt_path = "/etc/openvpn/tls-crypt.key"
    if os.path.exists(tls_crypt_path):
        tls_crypt = _read_file(tls_crypt_path)
    
    # Template
    config = f"""client
dev tun
proto {instance.protocol}
remote {public_ip} {instance.port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
auth SHA512
cipher AES-256-GCM
ignore-unknown-option block-outside-dns
block-outside-dns
verb 3
<ca>
{ca}
</ca>
<cert>
{cert}
</cert>
<key>
{key}
</key>
"""
    if tls_crypt:
        config += f"<tls-crypt>\n{tls_crypt}\n</tls-crypt>\n"
    
    return config

def _get_public_ip():
    try:
        return subprocess.check_output(["curl", "-s", "https://ifconfig.me"]).decode().strip()
    except:
        return "YOUR_SERVER_IP"

