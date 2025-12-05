import subprocess
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def get_network_interfaces() -> List[Dict[str, str]]:
    """
    Returns a list of network interfaces with their IP addresses.
    Each interface is represented as a dict with: name, ip, netmask, status.
    """
    interfaces = []
    
    try:
        # Use 'ip addr show' to get interface information
        result = subprocess.run(
            ["/usr/sbin/ip", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            check=True
        )
        
        seen_interfaces = set()
        
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            
            # Format: index: interface_name inet/inet6 ip/cidr ...
            interface_name = parts[1].rstrip(':')
            
            # Skip loopback and virtual interfaces (tun, tap, docker, etc.)
            if interface_name.startswith(('lo', 'tun', 'tap', 'docker', 'veth', 'br-')):
                continue
            
            # Only process inet (IPv4) addresses
            if 'inet' not in parts[2]:
                continue
            
            if parts[2] == 'inet6':
                continue
            
            # Extract IP and netmask
            ip_cidr = parts[3]
            ip_parts = ip_cidr.split('/')
            ip_address = ip_parts[0]
            cidr = ip_parts[1] if len(ip_parts) > 1 else '24'
            
            # Convert CIDR to netmask
            netmask = _cidr_to_netmask(int(cidr))
            
            # Check if interface is UP
            status = "up" if "UP" in line else "down"
            
            # Only add unique interfaces (avoid duplicates from multiple IPs)
            if interface_name not in seen_interfaces:
                interfaces.append({
                    "name": interface_name,
                    "ip": ip_address,
                    "netmask": netmask,
                    "cidr": cidr,
                    "status": status
                })
                seen_interfaces.add(interface_name)
        
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
