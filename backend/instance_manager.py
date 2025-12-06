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
    dns_servers: List[str] = [] # List of DNS servers to push
    clients: List[str] = []  # List of client names associated with this instance
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

            # Extract tun interface - default config uses "dev tun" which becomes tun0
            tun_match = re.search(r'^dev\s+(\S+)', content, re.MULTILINE)
            tun_interface = "tun0"  # Default value
            if tun_match:
                tun_dev = tun_match.group(1)
                # If it's just "tun" without a number, it becomes tun0
                if tun_dev == "tun":
                    tun_interface = "tun0"
                else:
                    tun_interface = tun_dev
            
            logger.info(f"Default instance using TUN interface: {tun_interface}")
            
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
                   tunnel_mode: str = "full", routes: List[Dict[str, str]] = None, dns_servers: List[str] = None) -> Instance:
    """
    Creates a new OpenVPN instance.
    """
    logger.info(f"=== Starting instance creation: name={name}, port={port}, subnet={subnet}")
    
    instances = get_all_instances()
    if any(inst.name == name for inst in instances):
        logger.error(f"Instance with name '{name}' already exists")
        raise ValueError(f"Instance with name '{name}' already exists.")
    if any(inst.port == port for inst in instances):
        logger.error(f"Port {port} is already in use")
        raise ValueError(f"Port {port} is already in use.")

    logger.info("Validation passed, determining TUN interface...")
    
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
    
    logger.info(f"Assigned TUN interface: {tun_interface}")

    instance_id = name.lower().replace(" ", "_")
    
    if routes is None:
        routes = []
    if dns_servers is None:
        dns_servers = []
    
    logger.info(f"Creating Instance object with id={instance_id}")

    new_instance = Instance(
        id=instance_id,
        name=name,
        port=port,
        protocol=protocol,
        subnet=subnet,
        tun_interface=tun_interface,
        tunnel_mode=tunnel_mode,
        routes=routes,
        dns_servers=dns_servers,
        status="stopped"
    )
    
    logger.info("Instance object created, generating OpenVPN config...")

    # Generate Config
    try:
        _generate_openvpn_config(new_instance)
        logger.info("Config generation completed successfully")
    except Exception as e:
        logger.error(f"Config generation failed: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate config: {e}")

    # Enable and Start Service
    service_name = _get_service_name(new_instance)
    try:
        logger.info(f"Enabling and starting systemd service: {service_name}")
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
    config_path = os.path.join(OPENVPN_CONFIG_DIR, f"server_{inst.name}.conf")
    if os.path.exists(config_path):
        os.remove(config_path)

    # Remove from registry
    instances = [i for i in instances if i.id != instance_id]
    _save_instances(instances)

def update_instance_routes(instance_id: str, tunnel_mode: str, routes: List[Dict[str, str]], dns_servers: List[str] = None) -> Instance:
    """
    Updates the routes and DNS for an existing instance.
    Regenerates config and restarts the service.
    """
    logger.info(f"Updating routes for instance '{instance_id}'")
    
    instances = get_all_instances()
    instance = None
    for inst in instances:
        if inst.id == instance_id:
            instance = inst
            break
    
    if not instance:
        raise ValueError(f"Instance '{instance_id}' not found")
    
    # Update routes, tunnel mode, and DNS servers
    old_routes = instance.routes.copy() or [] # Ensure it's not None
    instance.tunnel_mode = tunnel_mode
    
    # If switching to Full Tunnel, clear custom routes to ensure data consistency
    if tunnel_mode == "full":
        instance.routes = []
    else:
        instance.routes = routes

    if dns_servers is not None:
        instance.dns_servers = dns_servers
    
    logger.info(f"Updated instance {instance_id}: Mode={tunnel_mode}, Routes={len(instance.routes)}, DNS={len(instance.dns_servers)}")
    
    # Regenerate config file
    try:
        _generate_openvpn_config(instance)
        logger.info("Config regenerated successfully")
    except Exception as e:
        logger.error(f"Failed to regenerate config:  {e}")
        raise RuntimeError(f"Failed to regenerate config: {e}")
    
    # Update iptables rules for routes
    # Remove old route forwarding rules
    for route in old_routes:
        route_network = route.get('network')
        if route_network:
            iptables_manager.remove_forwarding_rule(instance.subnet, route_network)
    
    # Add new route forwarding rules
    for route in routes:
        route_network = route.get('network')
        route_interface = route.get('interface')
        if route_network and route_interface:
            iptables_manager.add_forwarding_rule(instance.subnet, route_network)
    
    # Persist iptables
    _save_iptables_rules()
    
    # Restart OpenVPN service to apply changes
    service_name = _get_service_name(instance)
    try:
        logger.info(f"Restarting service: {service_name}")
        subprocess.run(["/usr/bin/systemctl", "restart", service_name], check=True)
        logger.info("Service restarted successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart service: {e}")
        raise RuntimeError(f"Failed to restart OpenVPN service: {e}")
    
    # Save updated instance
    _save_instances(instances)
    
    return instance

def _generate_openvpn_config(instance: Instance):
    """
    Generates a server configuration file based on a template or defaults.
    """
    logger.info(f"Generating config for instance '{instance.name}'")
    
    # Use relative paths like the default server.conf
    # Files are in /etc/openvpn/ directly
    ca_path = "ca.crt"
    
    # Find the actual server cert/key names (they have random names from Angristan script)
    server_cert = None
    server_key = None
    try:
        for f in os.listdir("/etc/openvpn"):
            if f.startswith("server_") and f.endswith(".crt"):
                server_cert = f
            if f.startswith("server_") and f.endswith(".key"):
                server_key = f
        
        if not server_cert or not server_key:
            logger.warning("Server cert/key not found with server_ prefix, using generic names")
            server_cert = "server.crt"
            server_key = "server.key"
    except Exception as e:
        logger.warning(f"Error finding server cert/key: {e}")
        server_cert = "server.crt"
        server_key = "server.key"
    
    cert_path = server_cert
    key_path = server_key
    crl_path = "crl.pem"
    tls_crypt_path = "tls-crypt.key"
    
    logger.info(f"Using certificates: ca={ca_path}, cert={cert_path}, key={key_path}")
    
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
    
    # Base config (matching Angristan style)
    config_lines = [
        f"port {instance.port}",
        f"proto {instance.protocol}",
        f"dev {instance.tun_interface}",
        f"ca {ca_path}",
        f"cert {cert_path}",
        f"key {key_path}",
        "dh none",  # Use ECDH like Angristan
        "ecdh-curve prime256v1",
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
        "cipher AES-128-GCM",  # Match Angristan default
        "auth SHA256",
        "ncp-ciphers AES-128-GCM",
        "tls-server",
        "tls-version-min 1.2",
        "tls-cipher TLS-ECDHE-ECDSA-WITH-AES-128-GCM-SHA256",
    ]
    
    # Add tls-crypt if available
    if os.path.exists(f"/etc/openvpn/{tls_crypt_path}"):
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
    
    # DNS Configuration
    if instance.dns_servers and len(instance.dns_servers) > 0:
        for dns in instance.dns_servers:
            config_lines.append(f'push "dhcp-option DNS {dns.strip()}"')
    elif instance.tunnel_mode == "full":
        # Fallback to Google DNS only for Full Tunnel if no custom DNS provided
        config_lines.append('push "dhcp-option DNS 8.8.8.8"')
        config_lines.append('push "dhcp-option DNS 8.8.4.4"')

    if instance.tunnel_mode == "split":
        # Add custom routes
        if instance.routes and len(instance.routes) > 0:
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
                        elif route_cidr == '32': route_mask = "255.255.255.255"
                        config_lines.append(f'push "route {route_net} {route_mask}"')
                    else:
                        config_lines.append(f'push "route {route_network} 255.255.255.0"')
        else:
            logger.warning(f"Split tunnel mode enabled but no routes defined for instance '{instance.name}'")
    
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
    ])
    
    config_content = "\n".join(config_lines) + "\n"
    
    # Ensure directory exists
    os.makedirs(OPENVPN_CONFIG_DIR, exist_ok=True)
    
    # Determine config filename
    conf_filename = f"server_{instance.name}.conf"
    if instance.id == "default":
        conf_filename = "server.conf"

    config_path = os.path.join(OPENVPN_CONFIG_DIR, conf_filename)
    logger.info(f"Writing config to: {config_path}")
    
    try:
        with open(config_path, "w") as f:
            f.write(config_content)
        logger.info(f"Config file created successfully: {config_path}")
        # Set proper permissions
        os.chmod(config_path, 0o644)
        
        # Ensure CRL has correct permissions (using absolute path)
        crl_absolute = f"/etc/openvpn/{crl_path}"
        if os.path.exists(crl_absolute):
            os.chmod(crl_absolute, 0o644)
            logger.info(f"Set CRL permissions: {crl_absolute}")
            
    except Exception as e:
        logger.error(f"Failed to write config file {config_path}: {e}")
        raise

def add_client_to_instance(instance_id: str, client_name: str):
    """Add a client to an instance's client list."""
    instances = _load_instances()
    for inst in instances:
        if inst.id == instance_id:
            if client_name not in inst.clients:
                inst.clients.append(client_name)
                _save_instances(instances)
                logger.info(f"Added client '{client_name}' to instance '{instance_id}'")
            return
    raise ValueError(f"Instance '{instance_id}' not found")

def remove_client_from_instance(instance_id: str, client_name: str):
    """Remove a client from an instance's client list."""
    instances = _load_instances()
    for inst in instances:
        if inst.id == instance_id:
            if client_name in inst.clients:
                inst.clients.remove(client_name)
                _save_instances(instances)
                logger.info(f"Removed client '{client_name}' from instance '{instance_id}'")
            return
    raise ValueError(f"Instance '{instance_id}' not found")

def get_instance_clients(instance_id: str) -> List[str]:
    """Get list of clients associated with an instance."""
    instance = get_instance(instance_id)
    if not instance:
        raise ValueError(f"Instance '{instance_id}' not found")
    return instance.clients



