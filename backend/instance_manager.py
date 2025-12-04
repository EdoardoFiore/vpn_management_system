import json
import os
import subprocess
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel
import iptables_manager

logger = logging.getLogger(__name__)

DATA_FILE = "/opt/vpn-manager/backend/data/instances.json"
OPENVPN_CONFIG_DIR = "/etc/openvpn"

class Instance(BaseModel):
    id: str
    name: str
    port: int
    protocol: str
    subnet: str  # e.g., "10.8.0.0/24"
    tun_interface: str # e.g., "tun0", "tun1"
    status: str = "stopped" # stopped, running

def _load_instances() -> List[Instance]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return [Instance(**item) for item in data]
    except json.JSONDecodeError:
        return []

def _save_instances(instances: List[Instance]):
    with open(DATA_FILE, "w") as f:
        json.dump([inst.dict() for inst in instances], f, indent=4)

def get_all_instances() -> List[Instance]:
    instances = _load_instances()
    # Update status based on systemd
    for inst in instances:
        if _is_service_active(inst.name):
            inst.status = "running"
        else:
            inst.status = "stopped"
    return instances

def get_instance(instance_id: str) -> Optional[Instance]:
    instances = get_all_instances()
    for inst in instances:
        if inst.id == instance_id:
            return inst
    return None

def _is_service_active(instance_name: str) -> bool:
    service_name = f"openvpn-server@server_{instance_name}"
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", service_name], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_instance(name: str, port: int, subnet: str, protocol: str = "udp") -> Instance:
    """
    Creates a new OpenVPN instance.
    1. Validates input.
    2. Generates config file.
    3. Starts service.
    4. Applies iptables.
    5. Saves to registry.
    """
    instances = get_all_instances()
    if any(inst.name == name for inst in instances):
        raise ValueError(f"Instance with name '{name}' already exists.")
    if any(inst.port == port for inst in instances):
        raise ValueError(f"Port {port} is already in use.")

    # Determine next available TUN interface (simple heuristic)
    used_tuns = [int(inst.tun_interface.replace("tun", "")) for inst in instances if inst.tun_interface.startswith("tun")]
    next_tun_id = 0
    while next_tun_id in used_tuns:
        next_tun_id += 1
    tun_interface = f"tun{next_tun_id}"

    instance_id = name.lower().replace(" ", "_") # Simple ID generation

    new_instance = Instance(
        id=instance_id,
        name=name,
        port=port,
        protocol=protocol,
        subnet=subnet,
        tun_interface=tun_interface,
        status="stopped"
    )

    # Generate Config
    _generate_openvpn_config(new_instance)

    # Enable and Start Service
    service_name = f"openvpn-server@server_{name}"
    try:
        subprocess.run(["systemctl", "enable", service_name], check=True)
        subprocess.run(["systemctl", "start", service_name], check=True)
        new_instance.status = "running"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to start OpenVPN service: {e}")

    # Apply iptables
    iptables_manager.add_openvpn_rules(port, protocol, tun_interface, subnet)

    # Save
    instances.append(new_instance)
    _save_instances(instances)

    return new_instance

def delete_instance(instance_id: str):
    instances = _load_instances()
    inst = next((i for i in instances if i.id == instance_id), None)
    if not inst:
        raise ValueError("Instance not found")

    # Stop Service
    service_name = f"openvpn-server@server_{inst.name}"
    subprocess.run(["systemctl", "stop", service_name], check=False)
    subprocess.run(["systemctl", "disable", service_name], check=False)

    # Remove iptables
    iptables_manager.remove_openvpn_rules(inst.port, inst.protocol, inst.tun_interface, inst.subnet)

    # Remove Config
    config_path = os.path.join(OPENVPN_CONFIG_DIR, f"server_{inst.name}.conf")
    if os.path.exists(config_path):
        os.remove(config_path)

    # Remove from registry
    instances = [i for i in instances if i.id != instance_id]
    _save_instances(instances)

def _generate_openvpn_config(instance: Instance):
    """
    Generates a server configuration file based on a template or defaults.
    """
    # This is a simplified config generation. In a real scenario, we might copy a template.
    # We need to ensure we use the shared PKI paths.
    
    # Load paths from env or defaults (assuming shared PKI)
    ca_path = os.getenv("CA_PATH", "/etc/openvpn/easy-rsa/pki/ca.crt")
    cert_path = os.getenv("CERT_PATH", "/etc/openvpn/easy-rsa/pki/issued/server.crt")
    key_path = os.getenv("KEY_PATH", "/etc/openvpn/easy-rsa/pki/private/server.key")
    dh_path = os.getenv("DH_PATH", "/etc/openvpn/easy-rsa/pki/dh.pem")
    crl_path = os.getenv("CRL_PATH", "/etc/openvpn/easy-rsa/pki/crl.pem")
    
    config_content = f"""
port {instance.port}
proto {instance.protocol}
dev {instance.tun_interface}
ca {ca_path}
cert {cert_path}
key {key_path}
dh {dh_path}
topology subnet
server {instance.subnet.split('/')[0]} {instance.subnet.split('/')[1] if '/' in instance.subnet else '255.255.255.0'}
ifconfig-pool-persist ipp_{instance.name}.txt
keepalive 10 120
cipher AES-256-GCM
user nobody
group nogroup
persist-key
persist-tun
status /var/log/openvpn/status_{instance.name}.log
verb 3
crl-verify {crl_path}
explicit-exit-notify 1
"""
    # Note: subnet mask handling above is very basic. Better to use ipaddress module.
    
    config_path = os.path.join(OPENVPN_CONFIG_DIR, f"server_{instance.name}.conf")
    with open(config_path, "w") as f:
        f.write(config_content)
