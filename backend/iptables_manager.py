import os
import json
import subprocess
import logging
import uuid
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# The single source of truth for machine-wide firewall rules
RULES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'machine_rules.json')
APPLY_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'apply_firewall_rules.py')

class MachineFirewallRule:
    """Data model for a single machine firewall rule."""
    def __init__(self, id: str, chain: str, action: str, order: int,
                 protocol: Optional[str] = None,
                 source: Optional[str] = None, destination: Optional[str] = None,
                 port: Optional[Union[int, str]] = None, in_interface: Optional[str] = None,
                 out_interface: Optional[str] = None, state: Optional[str] = None,
                 comment: Optional[str] = None, table: str = "filter"):
        self.id = id if id else str(uuid.uuid4())
        self.chain = chain
        self.action = action
        self.protocol = protocol
        self.source = source
        self.destination = destination
        self.port = str(port) if port else None
        self.in_interface = in_interface
        self.out_interface = out_interface
        self.state = state
        self.comment = comment
        self.table = table
        self.order = order

    def to_dict(self):
        """Serializes the rule object to a dictionary."""
        return self.__dict__

    @property
    def rule(self) -> str:
        """Constructs the iptables rule string from the object's properties."""
        parts = [f"-A {self.chain}"]
        if self.in_interface:
            parts.append(f"-i {self.in_interface}")
        if self.out_interface:
            parts.append(f"-o {self.out_interface}")
        if self.source:
            parts.append(f"-s {self.source}")
        if self.destination:
            parts.append(f"-d {self.destination}")
        if self.protocol:
            parts.append(f"-p {self.protocol}")
            if self.port:
                parts.append(f"--dport {self.port}")
        if self.state:
            parts.append(f"-m state --state {self.state}")
        
        parts.append(f"-j {self.action}")
        return " ".join(parts)

    @staticmethod
    def from_dict(data: dict):
        """Deserializes a dictionary into a rule object."""
        # Ensure all fields are present
        full_data = {
            'id': data.get('id', str(uuid.uuid4())),
            'chain': data.get('chain'),
            'action': data.get('action'),
            'order': data.get('order'),
            'protocol': data.get('protocol'),
            'source': data.get('source'),
            'destination': data.get('destination'),
            'port': data.get('port'),
            'in_interface': data.get('in_interface'),
            'out_interface': data.get('out_interface'),
            'state': data.get('state'),
            'comment': data.get('comment'),
            'table': data.get('table', 'filter')
        }
        return MachineFirewallRule(**full_data)

def _apply_rules():
    """
    Triggers the central script to apply all firewall rules.
    This is the only function that interacts with iptables.
    """
    if os.geteuid() != 0:
        logger.error("Attempted to apply rules without root privileges.")
        return False, "This operation requires root privileges."

    command = ["/usr/bin/python3", APPLY_SCRIPT_PATH]
    try:
        logger.info(f"Executing firewall apply script: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info("Firewall rules applied successfully.")
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to apply firewall rules. Stderr: {e.stderr.strip()}"
        logger.error(error_msg)
        return False, error_msg
    except FileNotFoundError:
        error_msg = f"Error: The script '{APPLY_SCRIPT_PATH}' was not found."
        logger.error(error_msg)
        return False, error_msg

def get_all_rules() -> List[MachineFirewallRule]:
    """Reads all machine firewall rules from the JSON file."""
    try:
        if not os.path.exists(RULES_FILE):
            return []
        with open(RULES_FILE, 'r') as f:
            rules_data = json.load(f)
        return [MachineFirewallRule.from_dict(data) for data in rules_data]
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error reading rules from {RULES_FILE}: {e}")
        return []

def save_all_rules(rules: List[MachineFirewallRule]) -> (bool, Optional[str]):
    """
    Saves the entire list of rules to the JSON file and then applies them.
    This is now the primary way to update the firewall.
    """
    try:
        # Sort rules by order before saving
        rules.sort(key=lambda r: r.order)
        rules_data = [rule.to_dict() for rule in rules]
        with open(RULES_FILE, 'w') as f:
            json.dump(rules_data, f, indent=4)
        
        logger.info(f"Saved {len(rules)} rules to {RULES_FILE}. Now applying changes.")
        
        # After saving, trigger the script to apply the new configuration
        return _apply_rules()

    except IOError as e:
        error_msg = f"Error writing rules to {RULES_FILE}: {e}"
        logger.error(error_msg)
        return False, error_msg

# The following functions are no longer needed as rule application is centralized.
# They are kept here as comments for reference during transition, but should be removed later.
# def add_machine_firewall_rule(...)
# def delete_machine_firewall_rule(...)
# def clear_machine_firewall_rules_by_comment_prefix(...)
# def apply_machine_firewall_rules(...)
# def add_openvpn_rules(...)
# def remove_openvpn_rules(...)
# def add_forwarding_rule(...)
# def remove_forwarding_rule(...)
