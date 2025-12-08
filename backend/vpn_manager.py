import os
import subprocess
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
import instance_manager
import firewall_manager

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
    I client sono filtrati in base all'istanza specifica usando il prefisso del nome.
    """
    instance = instance_manager.get_instance(instance_id)
    if not instance:
        raise ValueError("Instance not found")

    # Get clients associated with this instance
    instance_client_names = instance_manager.get_instance_clients(instance_id)
    
    all_clients_from_pki = _get_all_clients_from_pki()
    connected_clients = get_connected_clients(instance.name)

    # Filter to only show clients belonging to this instance
    filtered_clients = []
    for client in all_clients_from_pki:
        client_name = client["name"]
        # Check if this client belongs to this instance
        if client_name in instance_client_names:
            if client_name in connected_clients:
                client["status"] = "connected"
                client.update(connected_clients[client_name])
            else:
                client["status"] = "disconnected"
            filtered_clients.append(client)
            
    return filtered_clients

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

def get_connected_clients(instance_name: str):
    connected_clients = {}
    status_log_path = f"/var/log/openvpn/status_{instance_name}.log"
    
    if not os.path.exists(status_log_path):
        return connected_clients

    try:
        with open(status_log_path, "r") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if line.startswith("CLIENT_LIST,"):
                parts = line.split(',')
                # status-version 2 format:
                # CLIENT_LIST,Common Name,Real Address,Virtual Address,Bytes Received,Bytes Sent,Connected Since,...
                if len(parts) > 7:
                    client_name = parts[1]
                    real_address = parts[2]
                    virtual_address = parts[3]
                    # Index 7 is "Connected Since" in the user's log version (due to IPv6 field at 4)
                    connected_since = parts[7]
                    bytes_received = parts[5]
                    bytes_sent = parts[6]

                    # Handle case where real address has port
                    if ":" in real_address:
                        real_address = real_address.split(":")[0]

                    connected_clients[client_name] = {
                        "virtual_ip": virtual_address,
                        "real_ip": real_address,
                        "connected_since": connected_since,
                        "bytes_received": bytes_received,
                        "bytes_sent": bytes_sent
                    }
    except Exception as e:
        logger.error(f"Error reading status log for {instance_name}: {e}")

    return connected_clients

def create_client(instance_id: str, client_name: str) -> Tuple[bool, Optional[str]]:
    instance = instance_manager.get_instance(instance_id)
    if not instance:
        return False, "Instance not found"

    # Use instance-specific prefix for client name
    prefixed_client_name = f"{instance.name}_{client_name}"
    
    # 1. Check if client exists
    existing_clients = _get_all_clients_from_pki()
    if any(c["name"] == prefixed_client_name for c in existing_clients):
        return False, f"Client '{client_name}' already exists for this instance."

    # 2. Create Certificate
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa --batch build-client-full {prefixed_client_name} nopass"
    out, code = _run_command(cmd, env_vars={"EASYRSA_CERT_EXPIRE": "3650"})
    if code != 0:
        return False, f"Easy-RSA Error: {out}"

    # 3. Generate .ovpn content
    try:
        ovpn_content = _generate_ovpn_content(instance, prefixed_client_name)
    except Exception as e:
        return False, f"Error generating config: {e}"

    # 4. Save .ovpn file (using original client name for file)
    config_path = os.path.join(CLIENT_CONFIG_DIR, f"{prefixed_client_name}.ovpn")
    with open(config_path, "w") as f:
        f.write(ovpn_content)
    
    # 5. Add client to instance's client list
    try:
        instance_manager.add_client_to_instance(instance_id, prefixed_client_name)
    except Exception as e:
        logger.error(f"Failed to add client to instance: {e}")
        # Certificate already created, so we continue

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

    # 1. Revoke (client_name is already prefixed)
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa --batch revoke {client_name}"
    out, code = _run_command(cmd)
    if code != 0 and "already revoked" not in out:
        return False, f"Revoke Error: {out}"

    # 2. Gen CRL
    cmd = f"cd {EASYRSA_DIR} && ./easyrsa gen-crl"
    out, code = _run_command(cmd, env_vars={"EASYRSA_CRL_DAYS": "3650"})
    if code != 0:
        return False, f"CRL Gen Error: {out}"

    # Copy CRL to OpenVPN directory
    try:
        crl_src = os.path.join(EASYRSA_DIR, "pki/crl.pem")
        crl_dest = "/etc/openvpn/crl.pem"
        subprocess.run(["cp", crl_src, crl_dest], check=True)
        os.chmod(crl_dest, 0o644)
    except Exception as e:
         return False, f"Error copying CRL: {e}"
    
    # 3. Remove client from instance's client list
    try:
        instance_manager.remove_client_from_instance(instance_id, client_name)
    except Exception as e:
        logger.error(f"Failed to remove client from instance: {e}")
        
    # 4. Remove from firewall groups
    try:
        firewall_manager.remove_client_from_all_groups(instance.name, client_name)
    except Exception as e:
        logger.error(f"Failed to remove client from firewall groups: {e}")
    
    # 5. Restart Service to reload CRL
    service_name = f"openvpn@server_{instance.name}"
    subprocess.run(["/usr/bin/systemctl", "restart", service_name], check=False)

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

