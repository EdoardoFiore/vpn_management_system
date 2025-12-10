import subprocess
import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

def get_network_interfaces() -> List[Dict[str, str]]:
    """
    Returns a list of network interfaces with their IP addresses, MAC, and status.
    Each interface is represented as a dict with: name, ip, netmask, cidr, mac_address, link_status.
    """
    interfaces = []
    
    try:
        # Use 'ip -o link show' to get link status and MAC addresses
        link_result = subprocess.run(
            ["/usr/sbin/ip", "-o", "link", "show"],
            capture_output=True,
            text=True,
            check=True
        )
        link_info = {}
        for line in link_result.stdout.splitlines():
            match = re.match(r"\d+: (\w+): <(.*?)>.*?link/ether ([\w:]+)", line)
            if match:
                name = match.group(1)
                flags = match.group(2)
                mac_address = match.group(3)
                link_status = "UP" if "UP" in flags else ("DOWN" if "DOWN" in flags else "UNKNOWN")
                link_info[name] = {"mac_address": mac_address, "link_status": link_status}
        
        # Use 'ip -o addr show' to get IP addresses
        addr_result = subprocess.run(
            ["/usr/sbin/ip", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            check=True
        )
        
        processed_interfaces = {} # Use dict to easily update interface details

        for line in addr_result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            
            interface_name = parts[1].rstrip(':')
            
            # Skip loopback and common virtual/internal interfaces
            if interface_name.startswith(('lo', 'tun', 'tap', 'docker', 'veth', 'br-', 'lxc', 'bond')):
                continue
            
            # Only process inet (IPv4) addresses for now
            if 'inet' not in parts[2]:
                continue
            if parts[2] == 'inet6': # Explicitly skip IPv6
                continue
            
            ip_cidr = parts[3]
            ip_parts = ip_cidr.split('/')
            ip_address = ip_parts[0]
            cidr = ip_parts[1] if len(ip_parts) > 1 else '24' # Default CIDR if not specified
            netmask = _cidr_to_netmask(int(cidr))
            
            if interface_name not in processed_interfaces:
                processed_interfaces[interface_name] = {
                    "name": interface_name,
                    "ip": None, # Default to None, will be set by first IPv4 found
                    "netmask": None,
                    "cidr": None,
                    "mac_address": link_info.get(interface_name, {}).get("mac_address"),
                    "link_status": link_info.get(interface_name, {}).get("link_status", "UNKNOWN"),
                    "configured_ips": [] # To hold multiple IPs if an interface has them
                }
            
            # Add this IP config to the interface
            processed_interfaces[interface_name]["configured_ips"].append({
                "ip": ip_address,
                "netmask": netmask,
                "cidr": cidr
            })
            
            # Set the primary IP/netmask/cidr for display if not already set
            if not processed_interfaces[interface_name]["ip"]:
                processed_interfaces[interface_name]["ip"] = ip_address
                processed_interfaces[interface_name]["netmask"] = netmask
                processed_interfaces[interface_name]["cidr"] = cidr

        # Convert the processed_interfaces dict to a list for output
        interfaces = list(processed_interfaces.values())
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get network interfaces: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting network interfaces: {e}")
    
    return interfaces

def _cidr_to_netmask(cidr: int) -> str:
    """Convert CIDR notation to dotted decimal netmask."""
    mask = (0xFFFFFFFF >> (32 - cidr)) << (32 - cidr)
    return f"{(mask >> 24) & 0xFF}.{(mask >> 16) & 0xFF}.{(mask >> 8) & 0xFF}.{mask & 0xFF}"

def get_interface_by_name(name: str) -> Optional[Dict[str, str]]:
    """Get a specific interface by name."""
    interfaces = get_network_interfaces()
    for iface in interfaces:
        if iface['name'] == name:
            return iface
    return None

def get_netplan_config_files() -> List[str]:
    """Lists all .yaml files in /etc/netplan/."""
    try:
        result = subprocess.run(
            ["find", "/etc/netplan/", "-name", "*.yaml"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to list netplan config files: {e}")
        return []

def read_netplan_config(file_path: str) -> Optional[Dict]:
    """Reads and parses a YAML netplan configuration file."""
    try:
        import yaml
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Netplan config file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading or parsing netplan config {file_path}: {e}")
        return None

def write_netplan_config(file_path: str, config_data: Dict) -> bool:
    """Writes a dictionary as a YAML netplan configuration file."""
    try:
        import yaml
        with open(file_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"Error writing netplan config to {file_path}: {e}")
        return False

def apply_netplan_config() -> (bool, Optional[str]):
    """Applies the netplan configuration."""
    try:
        subprocess.run(["/usr/sbin/netplan", "apply"], check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"netplan apply error (exit code {e.returncode}): {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg


