import subprocess
import logging

logger = logging.getLogger(__name__)

def _run_iptables(args):
    """Run an iptables command."""
    command = f"iptables {args}"
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"iptables error: {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg

def add_openvpn_rules(port: int, proto: str, tun_interface: str, subnet: str, outgoing_interface: str = "ens18"):
    """
    Adds iptables rules for a new OpenVPN instance.
    """
    # 1. Allow incoming traffic on the VPN port
    _run_iptables(f"-I INPUT -p {proto} --dport {port} -j ACCEPT")

    # 2. Allow traffic from TUN interface
    _run_iptables(f"-I INPUT -i {tun_interface} -j ACCEPT")
    _run_iptables(f"-I FORWARD -i {tun_interface} -j ACCEPT")

    # 3. Allow forwarding from TUN to WAN
    _run_iptables(f"-I FORWARD -i {tun_interface} -o {outgoing_interface} -m state --state RELATED,ESTABLISHED -j ACCEPT")
    _run_iptables(f"-I FORWARD -i {outgoing_interface} -o {tun_interface} -m state --state RELATED,ESTABLISHED -j ACCEPT")

    # 4. Masquerade (NAT) traffic from VPN subnet
    _run_iptables(f"-t nat -I POSTROUTING -s {subnet} -o {outgoing_interface} -j MASQUERADE")

    # 5. Allow OUTPUT on TUN
    _run_iptables(f"-I OUTPUT -o {tun_interface} -j ACCEPT")

    return True

def remove_openvpn_rules(port: int, proto: str, tun_interface: str, subnet: str, outgoing_interface: str = "ens18"):
    """
    Removes iptables rules for an OpenVPN instance.
    Note: We use -D instead of -I/-A. We ignore errors if rules don't exist.
    """
    _run_iptables(f"-D INPUT -p {proto} --dport {port} -j ACCEPT")
    _run_iptables(f"-D INPUT -i {tun_interface} -j ACCEPT")
    _run_iptables(f"-D FORWARD -i {tun_interface} -j ACCEPT")
    _run_iptables(f"-D FORWARD -i {tun_interface} -o {outgoing_interface} -m state --state RELATED,ESTABLISHED -j ACCEPT")
    _run_iptables(f"-D FORWARD -i {outgoing_interface} -o {tun_interface} -m state --state RELATED,ESTABLISHED -j ACCEPT")
    _run_iptables(f"-t nat -D POSTROUTING -s {subnet} -o {outgoing_interface} -j MASQUERADE")
    _run_iptables(f"-D OUTPUT -o {tun_interface} -j ACCEPT")

    return True

def add_forwarding_rule(source_subnet: str, dest_network: str):
    """
    Adds a forwarding rule to allow traffic from a VPN subnet to a specific destination network.
    """
    # Example: iptables -A FORWARD -s 10.8.0.0/24 -d 192.168.1.0/24 -j ACCEPT
    return _run_iptables(f"-I FORWARD -s {source_subnet} -d {dest_network} -j ACCEPT")

def remove_forwarding_rule(source_subnet: str, dest_network: str):
    return _run_iptables(f"-D FORWARD -s {source_subnet} -d {dest_network} -j ACCEPT")
