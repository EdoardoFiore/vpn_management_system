import os
import logging
import ipaddress
from typing import Optional, List

logger = logging.getLogger(__name__)

# Directory where CCD files are stored (OpenVPN Client Config Directory)
# Structure: /etc/openvpn/ccd/<instance_name>/<client_name>
CCD_BASE_DIR = "/etc/openvpn/ccd"

def _get_ccd_dir(instance_name: str) -> str:
    return os.path.join(CCD_BASE_DIR, instance_name)

def _get_ccd_path(instance_name: str, client_name: str) -> str:
    return os.path.join(_get_ccd_dir(instance_name), client_name)

def get_assigned_ip(instance_name: str, client_name: str) -> Optional[str]:
    """Reads the CCD file to find the assigned static IP."""
    path = _get_ccd_path(instance_name, client_name)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                content = f.read()
                # format: ifconfig-push <ip> <netmask>
                parts = content.strip().split()
                if len(parts) >= 2 and parts[0] == "ifconfig-push":
                    return parts[1]
        except Exception as e:
            logger.error(f"Error reading CCD file for {client_name}: {e}")
    return None

def allocate_static_ip(instance_name: str, subnet: str, client_name: str) -> Optional[str]:
    """
    Allocates the next available static IP from the subnet and writes it to the CCD file.
    Returns the allocated IP or None if subnet is full.
    """
    ccd_dir = _get_ccd_dir(instance_name)
    os.makedirs(ccd_dir, exist_ok=True)
    
    # 1. Parse Subnet
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        logger.error(f"Invalid subnet: {subnet}")
        return None

    # 2. Find used IPs
    used_ips = set()
    used_ips.add(str(network.network_address)) # .0
    used_ips.add(str(network.broadcast_address)) # .255 (or similar)
    # OpenVPN server usually takes the first usable IP (.1)
    # We assume server uses the first IP of the network. 
    # TODO: Pass server IP explicitly if different.
    server_ip = list(network.hosts())[0]
    used_ips.add(str(server_ip))

    # Scan existing CCD files
    if os.path.exists(ccd_dir):
        for fname in os.listdir(ccd_dir):
            ip = get_assigned_ip(instance_name, fname)
            if ip:
                used_ips.add(ip)

    # 3. Find next free IP
    # We skip the first one (.1) as it is likely the server
    for ip in network.hosts():
        ip_str = str(ip)
        if ip_str not in used_ips:
            # Found one!
            netmask = str(network.netmask)
            
            # Write CCD
            content = f"ifconfig-push {ip_str} {netmask}\n"
            ccd_path = _get_ccd_path(instance_name, client_name)
            try:
                with open(ccd_path, "w") as f:
                    f.write(content)
                logger.info(f"Allocated static IP {ip_str} to {client_name} in {instance_name}")
                return ip_str
            except Exception as e:
                logger.error(f"Failed to write CCD file for {client_name}: {e}")
                return None
    
    logger.error(f"No available IPs in subnet {subnet} for instance {instance_name}")
    return None

def release_static_ip(instance_name: str, client_name: str):
    """Removes the CCD file, effectively releasing the IP."""
    path = _get_ccd_path(instance_name, client_name)
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Released static IP for {client_name} in {instance_name}")
        except Exception as e:
            logger.error(f"Failed to remove CCD file for {client_name}: {e}")
