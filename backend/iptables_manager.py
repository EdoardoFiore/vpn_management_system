import subprocess
import logging
import uuid
from typing import List, Union, Optional

logger = logging.getLogger(__name__)

def _get_default_interface():
    """Detects the default network interface."""
    try:
        # Using `ip -o -4 route show default` is more reliable for default gateway interface
        result = subprocess.run(["/usr/sbin/ip", "-o", "-4", "route", "show", "default"], capture_output=True, text=True, check=True)
        if result.stdout:
            parts = result.stdout.split()
            if "dev" in parts:
                return parts[parts.index("dev") + 1]
    except Exception as e:
        logger.warning(f"Could not detect default interface using 'ip route': {e}")
    
    # Fallback to older `route` command if `ip` fails or is not available in expected way
    try:
        result = subprocess.run(["/sbin/route"], capture_output=True, text=True, check=False) # check=False because route can fail on some systems
        for line in result.stdout.splitlines():
            if "default" in line:
                parts = line.split()
                if len(parts) > 7: # Interface name is typically 8th word
                    return parts[7]
    except Exception as e:
        logger.warning(f"Could not detect default interface using 'route': {e}")

    logger.warning("Falling back to 'eth0' as default interface.")
    return "eth0" # Fallback

DEFAULT_INTERFACE = _get_default_interface()

class MachineFirewallRule:
    def __init__(self, id: str, chain: str, action: str,
                 protocol: Optional[str] = None,
                 source: Optional[str] = None, destination: Optional[str] = None,
                 port: Optional[Union[int, str]] = None, in_interface: Optional[str] = None,
                 out_interface: Optional[str] = None, state: Optional[str] = None,
                 comment: Optional[str] = None, table: str = "filter", order: int = 0):
        self.id = id if id else str(uuid.uuid4())
        self.chain = chain.upper()  # e.g., "INPUT", "OUTPUT", "FORWARD", "PREROUTING", "POSTROUTING"
        self.action = action.upper()  # e.g., "ACCEPT", "DROP", "REJECT", "MASQUERADE", "SNAT", "DNAT"
        self.protocol = protocol.lower() if protocol else None # e.g., "tcp", "udp", "icmp", "all"
        self.source = source # e.g., "192.168.1.0/24"
        self.destination = destination # e.g., "8.8.8.8"
        self.port = str(port) if port else None # e.g., 80, "22:23"
        self.in_interface = in_interface # e.g., "eth0", "tun+"
        self.out_interface = out_interface # e.g., "eth0", "tun+"
        self.state = state # e.g., "NEW,ESTABLISHED,RELATED"
        self.comment = comment # For iptables -m comment --comment "..."
        self.table = table.lower() # "filter", "nat", "mangle", "raw"
        self.order = order # For UI reordering

    def to_dict(self):
        return {
            "id": self.id,
            "chain": self.chain,
            "action": self.action,
            "protocol": self.protocol,
            "source": self.source,
            "destination": self.destination,
            "port": self.port,
            "in_interface": self.in_interface,
            "out_interface": self.out_interface,
            "state": self.state,
            "comment": self.comment,
            "table": self.table,
            "order": self.order
        }

    @staticmethod
    def from_dict(data: dict):
        return MachineFirewallRule(**data)

def _run_iptables(table: str, args: List[str]):
    """Run an iptables command."""
    command = ["/usr/sbin/iptables"]
    if table != "filter": # Default table is filter, only add -t if different
        command.extend(["-t", table])
    command.extend(args)

    try:
        full_command_str = ' '.join(command)
        logger.debug(f"Executing iptables command: {full_command_str}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        full_command_str = ' '.join(command)
        error_msg = f"iptables error (exit code {e.returncode}) on command '{full_command_str}': {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg

def _run_iptables_save():
    """Saves current iptables rules."""
    try:
        subprocess.run(["/usr/sbin/iptables-save"], check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"iptables-save error: {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg

def _build_iptables_args_from_rule(rule: MachineFirewallRule, operation: str = "-A") -> List[str]:
    """
    Builds a list of iptables arguments from a MachineFirewallRule object.
    operation can be -A (append), -D (delete), -I (insert)
    """
    args = [operation, rule.chain]

    if rule.in_interface:
        args.extend(["-i", rule.in_interface])
    if rule.out_interface:
        args.extend(["-o", rule.out_interface])
    if rule.source:
        args.extend(["-s", rule.source])
    if rule.destination:
        args.extend(["-d", rule.destination])

    if rule.protocol:
        args.extend(["-p", rule.protocol])
        if rule.port:
            # For MASQUERADE/SNAT/DNAT, port applies to --to-ports, not -dport
            if rule.action in ["MASQUERADE", "SNAT", "DNAT"]:
                # Special handling for NAT actions which have different port arguments
                pass # Ports for NAT actions are handled directly in add/delete functions if needed
            else:
                if ':' in rule.port: # Port range
                    args.extend(["--dport", rule.port])
                else: # Single port
                    args.extend(["--dport", rule.port])
    
    if rule.state:
        args.extend(["-m", "state", "--state", rule.state])
    
    # Add comment for identification, crucial for managing rules
    # Use -m comment --comment "UUID"
    args.extend(["-m", "comment", "--comment", f"ID_{rule.id}"])

    if rule.action == "MASQUERADE":
        args.append("-j")
        args.append("MASQUERADE")
        # For MASQUERADE, source/destination/port might be part of the POSTROUTING chain criteria,
        # but the actual action is just MASQUERADE.
        # The provided rule attributes should align with the iptables command structure.
    elif rule.action == "SNAT":
        args.append("-j")
        args.append("SNAT")
        if rule.destination: # For SNAT, destination here refers to --to-source
            args.extend(["--to-source", rule.destination]) # Re-using destination field for --to-source
    elif rule.action == "DNAT":
        args.append("-j")
        args.append("DNAT")
        if rule.destination: # For DNAT, destination here refers to --to-destination
            args.extend(["--to-destination", rule.destination]) # Re-using destination field for --to-destination
    else: # Standard actions like ACCEPT, DROP, REJECT
        args.append("-j")
        args.append(rule.action)

    return args

def add_machine_firewall_rule(rule: MachineFirewallRule) -> (bool, Optional[str]):
    """Adds a new generic machine-level iptables rule by inserting it at the top."""
    args = _build_iptables_args_from_rule(rule, operation="-I")
    return _run_iptables(rule.table, args)

def delete_machine_firewall_rule(rule: MachineFirewallRule) -> (bool, Optional[str]):
    """Deletes a generic machine-level iptables rule."""
    args = _build_iptables_args_from_rule(rule, operation="-D")
    return _run_iptables(rule.table, args)

def clear_machine_firewall_rules_by_comment_prefix(table: str = "filter", comment_prefix: str = "ID_"):
    """
    Clears all rules added by this manager (identified by comment_prefix) from a specific table.
    """
    success = True
    error_message = None
    
    try:
        # Use iptables -S which shows full rule specification for easier parsing.
        list_command = ["/usr/sbin/iptables", "-t", table, "-S"]
        logger.debug(f"Executing iptables list command: {' '.join(list_command)}")
        result = subprocess.run(list_command, check=True, capture_output=True, text=True)
        
        lines = result.stdout.splitlines()
        rules_to_delete_args = []

        for line in lines:
            # The comment format can be --comment "ID_..." or --comment ID_...
            # We check for the prefix without quotes to be more robust.
            if f'--comment {comment_prefix}' in line:
                logger.debug(f"Found rule to delete: {line}")

                # To delete a rule, we must specify it exactly as it was created,
                # including the comment. We just switch -A to -D.
                parts = line.split()
                
                if parts and parts[0] == '-A':
                    parts[0] = '-D' # Change -A (Append) to -D (Delete)
                    logger.debug(f"Constructed delete args: {parts}")
                    rules_to_delete_args.append(parts)
                else:
                    logger.warning(f"Could not parse rule for deletion: {line}")

        # Delete rules in reverse order to avoid index shifting issues if rules were ever deleted by line number
        for args in reversed(rules_to_delete_args):
            rule_delete_success, rule_delete_error = _run_iptables(table, args)
            if not rule_delete_success:
                logger.error(f"Failed to delete rule: {' '.join(args)} - {rule_delete_error}")
                success = False
                error_message = rule_delete_error # Keep the first error encountered
        
    except subprocess.CalledProcessError as e:
        if "does not exist" in e.stderr:
            logger.warning(f"Table '{table}' does not exist, skipping rule clearance.")
            return True, None
        logger.error(f"Error listing iptables rules for table {table}: {e.stderr.strip()}")
        return False, e.stderr.strip()
    except Exception as e:
        logger.error(f"Unexpected error in clear_machine_firewall_rules_by_comment_prefix: {e}")
        return False, str(e)

    return success, error_message

def apply_machine_firewall_rules(rules: List[MachineFirewallRule]):
    """
    Clears all manager-added rules and applies the given set of machine-level iptables rules.
    """
    success = True
    error_message = None

    # First, clear all existing rules added by this manager (identified by comment)
    # Iterate over all possible tables where rules might be added.
    tables = ["filter", "nat", "mangle", "raw"]
    for table in tables:
        clear_success, clear_error = clear_machine_firewall_rules_by_comment_prefix(table=table)
        if not clear_success:
            success = False
            error_message = f"Failed to clear rules from table {table}: {clear_error}"
            break # Stop if clearing fails

    if not success:
        return False, error_message

    # Apply new rules, sorted by order, in reverse.
    # By using -I (insert at top) in reverse order, the final list is in the correct order.
    rules.sort(key=lambda r: r.order)

    for rule in reversed(rules):
        rule_add_success, rule_add_error = add_machine_firewall_rule(rule)
        if not rule_add_success:
            logger.error(f"Failed to apply rule {rule.id}: {rule_add_error}")
            success = False
            error_message = rule_add_error
            break # Stop on first failure

    if success:
        logger.info("Successfully applied all machine firewall rules.")
    return success, error_message


def add_openvpn_rules(port: int, proto: str, tun_interface: str, subnet: str, outgoing_interface: str = None):
    """
    Adds iptables rules for a new OpenVPN instance.
    """
    if outgoing_interface is None:
        outgoing_interface = DEFAULT_INTERFACE

    # 1. Allow incoming traffic on the VPN port
    _run_iptables("filter", ["-I", "INPUT", "-p", proto, "--dport", str(port), "-j", "ACCEPT"])

    # 2. Allow traffic from TUN interface
    _run_iptables("filter", ["-I", "INPUT", "-i", tun_interface, "-j", "ACCEPT"])
    _run_iptables("filter", ["-I", "FORWARD", "-i", tun_interface, "-j", "ACCEPT"])

    # 3. Allow forwarding from TUN to WAN
    _run_iptables("filter", ["-I", "FORWARD", "-i", tun_interface, "-o", outgoing_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
    _run_iptables("filter", ["-I", "FORWARD", "-i", outgoing_interface, "-o", tun_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])

    # 4. Masquerade (NAT) traffic from VPN subnet
    _run_iptables("nat", ["-I", "POSTROUTING", "-s", subnet, "-o", outgoing_interface, "-j", "MASQUERADE"])

    # 5. Allow OUTPUT on TUN
    _run_iptables("filter", ["-I", "OUTPUT", "-o", tun_interface, "-j", "ACCEPT"])

    return True

def remove_openvpn_rules(port: int, proto: str, tun_interface: str, subnet: str, outgoing_interface: str = None):
    """
    Removes iptables rules for an OpenVPN instance.
    Note: We use -D instead of -I/-A. We ignore errors if rules don't exist.
    """
    if outgoing_interface is None:
        outgoing_interface = DEFAULT_INTERFACE

    _run_iptables("filter", ["-D", "INPUT", "-p", proto, "--dport", str(port), "-j", "ACCEPT"])
    _run_iptables("filter", ["-D", "INPUT", "-i", tun_interface, "-j", "ACCEPT"])
    _run_iptables("filter", ["-D", "FORWARD", "-i", tun_interface, "-j", "ACCEPT"])
    _run_iptables("filter", ["-D", "FORWARD", "-i", tun_interface, "-o", outgoing_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
    _run_iptables("filter", ["-D", "FORWARD", "-i", outgoing_interface, "-o", tun_interface, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
    _run_iptables("nat", ["-D", "POSTROUTING", "-s", subnet, "-o", outgoing_interface, "-j", "MASQUERADE"])
    _run_iptables("filter", ["-D", "OUTPUT", "-o", tun_interface, "-j", "ACCEPT"])

    return True

def add_forwarding_rule(source_subnet: str, dest_network: str):
    """
    Adds a forwarding rule to allow traffic from a VPN subnet to a specific destination network.
    """
    # Example: iptables -I FORWARD -s 10.8.0.0/24 -d 192.168.1.0/24 -j ACCEPT
    return _run_iptables("filter", ["-I", "FORWARD", "-s", source_subnet, "-d", dest_network, "-j", "ACCEPT"])

def remove_forwarding_rule(source_subnet: str, dest_network: str):
    return _run_iptables("filter", ["-D", "FORWARD", "-s", source_subnet, "-d", dest_network, "-j", "ACCEPT"])
