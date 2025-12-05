import json
import os
import subprocess
import logging
import re
from typing import List, Optional, Dict
from pydantic import BaseModel
import iptables_manager

logger = logging.getLogger(__name__)

DATA_FILE = "/opt/vpn-manager/backend/data/instances.json"
OPENVPN_CONFIG_DIR = "/etc/openvpn"
DEFAULT_CONFIG_FILE = os.path.join(OPENVPN_CONFIG_DIR, "server.conf")
IPTABLES_SAVE_SCRIPT = "/opt/vpn-manager/scripts/save-iptables.sh"

class Instance(BaseModel):
    id: str
    name: str
    port: int
    protocol: str
    subnet: str  # e.g., "10.8.0.0/24"
    tun_interface: str # e.g., "tun0", "tun1"
    tunnel_mode: str = "full"  # "full" or "split"
    routes: List[Dict[str, str]] = []  # List of {"network": "192.168.1.0/24", "interface": "eth1"}
    status: str = "stopped" # stopped, running

def _save_iptables_rules():
    """Save current iptables rules to persist across reboots."""
    if os.path.exists(IPTABLES_SAVE_SCRIPT):
        try:
            subprocess.run(["bash", IPTABLES_SAVE_SCRIPT], check=True)
            logger.info("iptables rules saved successfully")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to save iptables rules: {e}")
    else:
        logger.warning(f"iptables save script not found: {IPTABLES_SAVE_SCRIPT}")

def _load_instances() -> List[Instance]:
    instances = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                instances = [Instance(**item) for item in data]
        except json.JSONDecodeError:
            pass
    
    # Try to import default instance if not present
    default_instance = _import_default_instance()
    if default_instance:
        # Check if already in instances (by id or port)
        if not any(i.id == default_instance.id for i in instances) and \
           not any(i.port == default_instance.port for i in instances):
            instances.insert(0, default_instance)
            _save_instances(instances)
            
    return instances

def _save_instances(instances: List[Instance]):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump([inst.dict() for inst in instances], f, indent=4)

def _import_default_instance() -> Optional[Instance]:
    """
    Parses /etc/openvpn/server.conf to create a default Instance object.
    """
    if not os.path.exists(DEFAULT_CONFIG_FILE):
        return None

    try:
        with open(DEFAULT_CONFIG_FILE, "r") as f:
            content = f.read()
        
        port_match = re.search(r'^port\s+(\d+)', content, re.MULTILINE)
        proto_match = re.search(r'^proto\s+(\w+)', content, re.MULTILINE)
        dev_match = re.search(r'^dev\s+(\w+)', content, re.MULTILINE)
        server_match = re.search(r'^server\s+([\d\.]+)\s+([\d\.]+)', content, re.MULTILINE)

        if port_match and proto_match and dev_match and server_match:
            port = int(port_match.group(1))
            protocol = proto_match.group(1)
            tun_interface = dev_match.group(1)
            network = server_match.group(1)
            netmask = server_match.group(2)
            
            # Convert netmask to CIDR (simple lookup or calculation)
            cidr = 24 # Default fallback
            if netmask == "255.255.255.0": cidr = 24
            elif netmask == "255.255.0.0": cidr = 16
            elif netmask == "255.0.0.0": cidr = 8
            # TODO: Add more robust netmask to CIDR conversion if needed

            subnet = f"{network}/{cidr}"

            return Instance(
                id="default",
                name="Default",
                port=port,
                protocol=protocol,
                subnet=subnet,
                tun_interface=tun_interface,
                tunnel_mode="full",
                routes=[],
                status="stopped"
            )
    except Exception as e:
        logger.error(f"Failed to parse default config: {e}")
        return None
    return None

def get_all_instances() -> List[Instance]:
    instances = _load_instances()
    # Update status based on systemd
    for inst in instances:
        if _is_service_active(inst):
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

def _get_service_name(instance: Instance) -> str:
    # systemd openvpn instances use openvpn@<config-name>
    # where config-name is the filename without .conf
    if instance.id == "default":
        return "openvpn@server"
    return f"openvpn@server_{instance.name}"

def _is_service_active(instance: Instance) -> bool:
    service_name = _get_service_name(instance)
    try:
        subprocess.run(["/usr/bin/systemctl", "is-active", "--quiet", service_name], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_instance(name: str, port: int, subnet: str, protocol: str = "udp", 
                   tunnel_mode: str = "full", routes: List[Dict[str, str]] = None) -> Instance:
    """
    Creates a new OpenVPN instance.
    """
    instances = get_all_instances()
    if any(inst.name == name for inst in instances):
        raise ValueError(f"Instance with name '{name}' already exists.")
    if any(inst.port == port for inst in instances):
        raise ValueError(f"Port {port} is already in use.")

    # Determine next available TUN interface
    used_tuns = []
    for inst in instances:
        match = re.search(r'tun(\d+)', inst.tun_interface)
        if match:
            used_tuns.append(int(match.group(1)))
            
    next_tun_id = 0
    while next_tun_id in used_tuns:
        next_tun_id += 1
    tun_interface = f"tun{next_tun_id}"

    instance_id = name.lower().replace(" ", "_")

    if routes is None:
        routes = []

    new_instance = Instance(
        id=instance_id,
        name=name,
        port=port,
        protocol=protocol,
        subnet=subnet,
        tun_interface=tun_interface,
        tunnel_mode=tunnel_mode,
        routes=routes,
        status="stopped"
    )

    # Generate Config
    _generate_openvpn_config(new_instance)

    # Enable and Start Service
    service_name = _get_service_name(new_instance)
    try:
        subprocess.run(["/usr/bin/systemctl", "enable", service_name], check=True)
        subprocess.run(["/usr/bin/systemctl", "start", service_name], check=True)
        new_instance.status = "running"
    except subprocess.CalledProcessError as e:
        # Clean up if start fails
        try:
             os.remove(os.path.join(OPENVPN_CONFIG_DIR, f"server_{name}.conf"))
        except: pass
        raise RuntimeError(f"Failed to start OpenVPN service: {e}")

    # Apply iptables for VPN subnet on default WAN interface
    iptables_manager.add_openvpn_rules(port, protocol, tun_interface, subnet)
    
    # Apply iptables for custom routes to LAN interfaces
    for route in new_instance.routes:
        route_network = route.get('network')
        route_interface = route.get('interface')
        if route_network and route_interface:
            iptables_manager.add_forwarding_rule(subnet, route_network)
    
    # Persist iptables rules
    _save_iptables_rules()

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
    service_name = _get_service_name(inst)
    subprocess.run(["/usr/bin/systemctl", "stop", service_name], check=False)
    subprocess.run(["/usr/bin/systemctl", "disable", service_name], check=False)

    # Remove iptables
    iptables_manager.remove_openvpn_rules(inst.port, inst.protocol, inst.tun_interface, inst.subnet)
    
    # Remove custom route forwarding rules  
    for route in inst.routes:
        route_network = route.get('network')
        if route_network:
            iptables_manager.remove_forwarding_rule(inst.subnet, route_network)
    
    # Persist iptables rules
    _save_iptables_rules()

    # Remove Config
    config_filename = "server.conf" if inst.id == "default" else f"server_{inst.name}.conf"
    config_path = os.path.join(OPENVPN_CONFIG_DIR, config_filename)
    if os.path.exists(config_path):
        os.remove(config_path)

    # Remove from registry
    instances = [i for i in instances if i.id != instance_id]
    _save_instances(instances)

def _generate_openvpn_config(instance: Instance):
    """
    Generates a server configuration file based on a template or defaults.
    """
    logger.info(f"Generating config for instance '{instance.name}'")
    
    ca_path = os.getenv("CA_PATH", "/etc/openvpn/easy-rsa/pki/ca.crt")
    cert_path = os.getenv("CERT_PATH", "/etc/openvpn/easy-rsa/pki/issued/server.crt")
    key_path = os.getenv("KEY_PATH", "/etc/openvpn/easy-rsa/pki/private/server.key")
    dh_path = os.getenv("DH_PATH", "/etc/openvpn/easy-rsa/pki/dh.pem")
    crl_path = os.getenv("CRL_PATH", "/etc/openvpn/easy-rsa/pki/crl.pem")
    tls_crypt_path = os.getenv("TLS_CRYPT_PATH", "/etc/openvpn/tls-crypt.key")
    
    # Handle subnet mask
    network = instance.subnet.split('/')[0]
    cidr = instance.subnet.split('/')[1] if '/' in instance.subnet else '24'
    
    # Simple CIDR to Netmask conversion
    netmask = "255.255.255.0"
    if cidr == '8': netmask = "255.0.0.0"
    elif cidr == '16': netmask = "255.255.0.0"
    elif cidr == '24': netmask = "255.255.255.0"
    
    # Ensure log directory exists
    log_dir = "/var/log/openvpn"
    os.makedirs(log_dir, exist_ok=True)
    
    # Ensure client-config-dir exists
    ccd_dir = f"/etc/openvpn/ccd/{instance.name}"
    os.makedirs(ccd_dir, exist_ok=True)
    
    # Base config
    config_lines = [
        f"port {instance.port}",
        f"proto {instance.protocol}",
        f"dev {instance.tun_interface}",
        f"ca {ca_path}",
        f"cert {cert_path}",
        f"key {key_path}",
        f"dh {dh_path}",
        "topology subnet",
        f"server {network} {netmask}",
        f"ifconfig-pool-persist ipp_{instance.name}.txt",
        "",
        "# Security",
        "user nobody",
        "group nogroup",
        "persist-key",
        "persist-tun",
        "",
        "# Keepalive and timeouts",
        "keepalive 10 120",
        "",
        "# Cryptography",
        "cipher AES-256-GCM",
        "auth SHA256",
        "tls-server",
        "tls-version-min 1.2",
        f"tls-cipher TLS-ECDHE-RSA-WITH-AES-128-GCM-SHA256:TLS-ECDHE-RSA-WITH-AES-256-GCM-SHA384",
    ]
    
    # Add tls-crypt if available
    if os.path.exists(tls_crypt_path):
        config_lines.append(f"tls-crypt {tls_crypt_path}")
    
    # Client configuration directory
    config_lines.extend([
        "",
        "# Client-specific configurations",
        f"client-config-dir {ccd_dir}",
    ])
    
    # Add routing based on tunnel mode
    config_lines.append("")
    config_lines.append("# Routing configuration")
    
    if instance.tunnel_mode == "full":
        config_lines.append('push "redirect-gateway def1 bypass-dhcp"')
        config_lines.append('push "dhcp-option DNS 8.8.8.8"')
        config_lines.append('push "dhcp-option DNS 8.8.4.4"')
    elif instance.tunnel_mode == "split":
        # Add custom routes
        for route in instance.routes:
            route_network = route.get('network', '')
            if route_network:
                # Convert CIDR to network + netmask for push route command
                if '/' in route_network:
                    net_parts = route_network.split('/')
                    route_net = net_parts[0]
                    route_cidr = net_parts[1]
                    # Convert CIDR to netmask
                    route_mask = "255.255.255.0"
                    if route_cidr == '8': route_mask = "255.0.0.0"
                    elif route_cidr == '16': route_mask = "255.255.0.0"
                    elif route_cidr == '24': route_mask = "255.255.255.0"
                    config_lines.append(f'push "route {route_net} {route_mask}"')
                else:
                    config_lines.append(f'push "route {route_network} 255.255.255.0"')
    
    # Logging and monitoring
    config_lines.extend([
        "",
        "# Logging",
        f"status {log_dir}/status_{instance.name}.log",
        "verb 3",
    ])
    
    # Certificate revocation list
    config_lines.extend([
        "",
        "# Certificate revocation",
        f"crl-verify {crl_path}",
        "",
        "# Notify clients on restart",
        "explicit-exit-notify 1"
    ])
    
    config_content = "\n".join(config_lines) + "\n"
    
    # Ensure directory exists
    os.makedirs(OPENVPN_CONFIG_DIR, exist_ok=True)
    
    config_path = os.path.join(OPENVPN_CONFIG_DIR, f"server_{instance.name}.conf")
    logger.info(f"Writing config to: {config_path}")
    
    try:
        with open(config_path, "w") as f:
            f.write(config_content)
        logger.info(f"Config file created successfully: {config_path}")
        # Set proper permissions
        os.chmod(config_path, 0o644)
        
        # Ensure CRL has correct permissions
        if os.path.exists(crl_path):
            os.chmod(crl_path, 0o644)
            logger.info(f"Set CRL permissions: {crl_path}")
            
    except Exception as e:
        logger.error(f"Failed to write config file {config_path}: {e}")
        raise


