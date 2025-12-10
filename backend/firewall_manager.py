import json
import os
import re
import subprocess
import logging
from typing import List, Dict, Optional
from ipaddress import ip_network, AddressValueError
from pydantic import BaseModel, validator
import ip_manager
import instance_manager

logger = logging.getLogger(__name__)

DATA_DIR = "/opt/vpn-manager/backend/data"
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
RULES_FILE = os.path.join(DATA_DIR, "rules.json")

# IPTables Chain Name
CHAIN_NAME = "VPN_sys_FORWARD"

class Group(BaseModel):
    id: str
    instance_id: str
    name: str
    description: str = ""
    members: List[str] = [] # List of "instance_name_client_name"

class Rule(BaseModel):
    id: str
    group_id: str
    action: str 
    protocol: str
    port: Optional[str] = None
    destination: str
    description: str = ""
    order: int = 0

    @validator('destination')
    def validate_destination(cls, v):
        """Validate that the destination is a valid IP, CIDR, or 'any'."""
        if v.lower() == 'any':
            return '0.0.0.0/0'
        try:
            ip_network(v, strict=False)
            return v
        except (AddressValueError, ValueError):
            raise ValueError(f"'{v}' is not a valid IP address or CIDR network.")

    @validator('port')
    def validate_port(cls, v, values):
        """Validate that the port is a single number or a valid range."""
        # Treat empty string as None, then proceed.
        if v is None or v.strip() == '':
            return None

        protocol = values.get('protocol')
        if protocol not in ['tcp', 'udp']:
            raise ValueError(f"La porta non è applicabile per il protocollo '{protocol}'.")

        port_range_regex = r"^\d{1,5}(:\d{1,5})?$"
        if not re.fullmatch(port_range_regex, str(v)):
            raise ValueError("La porta deve essere un numero singolo o un intervallo come '1000:2000'.")

        parts = str(v).split(':')
        start_port = int(parts[0])
        
        if not (1 <= start_port <= 65535):
            raise ValueError(f"La porta '{start_port}' è fuori dal range valido (1-65535).")

        if len(parts) == 2:
            end_port = int(parts[1])
            if not (1 <= end_port <= 65535):
                raise ValueError(f"La porta finale '{end_port}' è fuori dal range valido (1-65535).")
            if start_port >= end_port:
                raise ValueError("Nell'intervallo di porte, la porta iniziale deve essere minore di quella finale.")
        
        return str(v)

def _load_groups() -> List[Group]:
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r") as f:
                return [Group(**g) for g in json.load(f)]
    # ... error handling ...
        except Exception: return []
    return []

def _save_groups(groups: List[Group]):
    os.makedirs(os.path.dirname(GROUPS_FILE), exist_ok=True)
    with open(GROUPS_FILE, "w") as f:
        json.dump([g.dict() for g in groups], f, indent=4)

def _load_rules() -> List[Rule]:
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r") as f:
                return [Rule(**r) for r in json.load(f)]
        except Exception: return []
    return []

def _save_rules(rules: List[Rule]):
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    with open(RULES_FILE, "w") as f:
        json.dump([r.dict() for r in rules], f, indent=4)

# --- Group Management ---

def create_group(name: str, instance_id: str, description: str = "") -> Group:
    groups = _load_groups()
    group_id = f"{instance_id}_{name.lower().replace(' ', '_')}"
    if any(g.id == group_id for g in groups):
        raise ValueError("Group already exists for this instance")
    
    group = Group(id=group_id, instance_id=instance_id, name=name, description=description)
    groups.append(group)
    _save_groups(groups)
    return group

def delete_group(group_id: str):
    groups = _load_groups()
    groups = [g for g in groups if g.id != group_id]
    _save_groups(groups)
    # Also delete associated rules
    rules = _load_rules()
    rules = [r for r in rules if r.group_id != group_id]
    _save_rules(rules)
    apply_firewall_rules()

def add_member_to_group(group_id: str, client_identifier: str, subnet_info: Dict[str, str]):
    """
    client_identifier: e.g., "server_client1"
    subnet_info: {"instance_name": "server", "subnet": "10.8.0.0/24"}
    """
    groups = _load_groups()
    group = next((g for g in groups if g.id == group_id), None)
    if not group:
        raise ValueError("Group not found")

    instance_name = subnet_info["instance_name"]
    
    # Sanitize the client_identifier to prevent duplicate prefixes, e.g. "inst_inst_client"
    correct_identifier = client_identifier
    prefix_to_check = f"{instance_name}_"
    while correct_identifier.startswith(prefix_to_check + instance_name):
        correct_identifier = correct_identifier[len(prefix_to_check):]
    
    if instance_name != group.instance_id:
        raise ValueError(f"Client does not belong to instance {group.instance_id}")

    if correct_identifier not in group.members:
        # 1. Allocate Static IP. 
        # The client name used for the CCD file MUST be the full, correct identifier
        # that matches the client's Common Name (CN) in its certificate.
        ip = ip_manager.allocate_static_ip(instance_name, subnet_info["subnet"], correct_identifier)
        if not ip:
            raise RuntimeError(f"Failed to allocate static IP for {correct_identifier}")

        group.members.append(correct_identifier)
        _save_groups(groups)
        apply_firewall_rules()
    
    return True

def remove_member_from_group(group_id: str, client_identifier: str, instance_name: str):
    groups = _load_groups()
    group = next((g for g in groups if g.id == group_id), None)
    if not group:
        raise ValueError("Group not found")

    if client_identifier in group.members:
        group.members.remove(client_identifier)
        _save_groups(groups)
        
        # Release Static IP
        ip_manager.release_static_ip(instance_name, client_identifier)
        
        apply_firewall_rules()

def remove_client_from_all_groups(instance_name: str, client_name: str):
    """
    Removes a client from all groups they might be part of.
    """
    client_identifier = f"{instance_name}_{client_name}"
    groups = _load_groups()
    modified = False
    
    for group in groups:
        if client_identifier in group.members:
            group.members.remove(client_identifier)
            modified = True
            # Release Static IP
            ip_manager.release_static_ip(instance_name, client_identifier)

    if modified:
        _save_groups(groups)
        apply_firewall_rules()

def get_groups(instance_id: Optional[str] = None) -> List[Group]:
    groups = _load_groups()
    if instance_id:
        return [g for g in groups if g.instance_id == instance_id]
    return groups

# --- Rule Management ---

import uuid

def add_rule(rule_data: dict) -> Rule:
    rules = _load_rules()
    
    # Generate ID if missing
    if "id" not in rule_data or not rule_data["id"]:
        rule_data["id"] = str(uuid.uuid4())

    # Calculate order if not provided or None
    if "order" not in rule_data or rule_data["order"] is None:
        max_order = max([r.order for r in rules if r.group_id == rule_data["group_id"]], default=-1)
        rule_data["order"] = max_order + 1
        
    rule = Rule(**rule_data)
    rules.append(rule)
    
    # Sort by order
    rules.sort(key=lambda x: x.order)
    
    _save_rules(rules)
    apply_firewall_rules()
    return rule

def delete_rule(rule_id: str):
    rules = _load_rules()
    rules = [r for r in rules if r.id != rule_id]
    _save_rules(rules)
    apply_firewall_rules()

def update_rule_order(rule_orders: List[Dict[str, int]]):
    """
    Update order of multiple rules.
    rule_orders: [{"id": "rule1", "order": 0}, ...]
    """
    rules = _load_rules()
    
    for item in rule_orders:
        rule = next((r for r in rules if r.id == item["id"]), None)
        if rule:
            rule.order = item["order"]
            
    rules.sort(key=lambda x: x.order)
    _save_rules(rules)
    apply_firewall_rules()

def update_rule(rule_id: str, group_id: str, action: str, protocol: str, destination: str, port: Optional[str] = None, description: str = "") -> Rule:
    rules = _load_rules()
    rule_to_update = next((r for r in rules if r.id == rule_id and r.group_id == group_id), None)

    if not rule_to_update:
        raise ValueError(f"Rule with ID {rule_id} not found in group {group_id}")

    # Update fields
    rule_to_update.action = action
    rule_to_update.protocol = protocol
    rule_to_update.destination = destination
    rule_to_update.port = port
    rule_to_update.description = description
    
    # Re-validate the updated rule (especially port based on protocol)
    try:
        updated_rule_data = rule_to_update.dict()
        validated_rule = Rule(**updated_rule_data) # This will run validators
    except ValueError as e:
        raise ValueError(f"Invalid rule data after update: {e}")

    _save_rules(rules)
    apply_firewall_rules()
    return validated_rule

def get_rules(group_id: Optional[str] = None) -> List[Rule]:
    rules = _load_rules()
    if group_id:
        return [r for r in rules if r.group_id == group_id]
    return rules

# --- IPTables Application ---

def _run_iptables(cmd: List[str], check=False, suppress_errors=False):
    """Helper to run iptables commands, with optional error suppression."""
    try:
        # Using shell=False and list of args is safer
        result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        if result.returncode != 0 and not suppress_errors:
            logger.warning(f"iptables command failed: {' '.join(cmd)}\n  Error: {result.stderr.strip()}")
        return result
    except Exception as e:
        if not suppress_errors:
            logger.error(f"Exception running iptables command: {' '.join(cmd)}\n  Error: {e}")
        return None

def apply_firewall_rules():
    """
    Re-generates all VPN firewall rules using a hierarchical chain structure.
    VPN_MAIN_FWD -> VI_{instance_id} -> VIG_{group_id}
    """
    logger.info("--- Starting Firewall Rules Application ---")

    # 1. Load all configurations
    instances = instance_manager.get_all_instances()
    groups = _load_groups()
    rules = _load_rules()
    
    # 2. Define all chain names
    main_chain = "VPN_MAIN_FWD"
    instance_chains = [f"VI_{inst.id}" for inst in instances]
    group_chains = [f"VIG_{g.id}" for g in groups]
    all_chains = [main_chain] + instance_chains + group_chains

    # 3. Reset all managed chains
    logger.info("Flushing and deleting existing managed chains...")
    for chain in all_chains:
        _run_iptables(["iptables", "-F", chain], suppress_errors=True)
    for chain in all_chains:
        _run_iptables(["iptables", "-X", chain], suppress_errors=True)

    # 4. Re-create all chains
    logger.info("Creating new chains...")
    for chain in all_chains:
        _run_iptables(["iptables", "-N", chain], suppress_errors=True)
        
    # 5. Ensure main jump from FORWARD chain exists and is at the top
    # Check if rule exists
    res = _run_iptables(["iptables", "-C", "FORWARD", "-j", main_chain], suppress_errors=True)
    if res and res.returncode != 0:
        _run_iptables(["iptables", "-I", "FORWARD", "1", "-j", main_chain])
        logger.info(f"Inserted jump from FORWARD to '{main_chain}'.")

    # 6. Populate chains
    logger.info("Populating iptables chains...")
    
    # Helper to get client IP (same as before, but defined locally)
    def get_client_ip(member_id, instances_data):
        for inst in instances_data:
            if member_id.startswith(f"{inst.name}_"):
                ip = ip_manager.get_assigned_ip(inst.name, member_id)
                if ip:
                    return ip
        return None

    # Create a member-to-IP map for efficiency
    member_ip_map = {}
    all_members = {member for group in groups for member in group.members}
    for member_id in all_members:
        ip = get_client_ip(member_id, instances)
        if ip:
            member_ip_map[member_id] = ip
        else:
             logger.warning(f"Could not resolve IP for member '{member_id}'. They will not be included in firewall rules.")

    # Populate group chains (deepest level)
    for group in groups:
        group_chain_name = f"VIG_{group.id}"
        group_rules = sorted([r for r in rules if r.group_id == group.id], key=lambda x: x.order)
        
        # Insert rules in reverse order with -I to maintain the correct sequence
        for rule in reversed(group_rules):
            # A member's packet only reaches this chain if it's from that member.
            # So, we only need to specify destination, proto, port.
            proto_arg = f"-p {rule.protocol}" if rule.protocol != "all" else ""
            port_arg = f"--dport {rule.port}" if rule.port and rule.protocol in ["tcp", "udp"] else ""
            dest_arg = f"-d {rule.destination}" if rule.destination and rule.destination != "0.0.0.0/0" else ""
            
            cmd = ["iptables", "-I", group_chain_name] # Use -I to insert at the top
            if proto_arg: cmd.extend(proto_arg.split())
            if port_arg: cmd.extend(port_arg.split())
            if dest_arg: cmd.extend(dest_arg.split())
            cmd.extend(["-j", rule.action.upper()])
            
            _run_iptables(cmd)
            logger.info(f"  [RULE] Chain {group_chain_name}: {' '.join(cmd)}")
        
        # Add a final RETURN to send non-matching packets back to the instance chain
        _run_iptables(["iptables", "-A", group_chain_name, "-j", "RETURN"])

    # Populate instance and main chains
    for instance in instances:
        instance_chain_name = f"VI_{instance.id}"
        
        # Add jumps from MAIN to INSTANCE chain
        _run_iptables(["iptables", "-A", main_chain, "-s", instance.subnet, "-j", instance_chain_name])
        logger.info(f"[JUMP] Chain {main_chain}: -s {instance.subnet} -j {instance_chain_name}")

        # Find groups belonging to this instance
        instance_groups = [g for g in groups if g.instance_id == instance.id]
        
        # Add jumps from INSTANCE to GROUP chains
        for group in instance_groups:
            group_chain_name = f"VIG_{group.id}"
            for member_id in group.members:
                if member_id in member_ip_map:
                    ip = member_ip_map[member_id]
                    _run_iptables(["iptables", "-A", instance_chain_name, "-s", ip, "-j", group_chain_name])
                    logger.info(f"  [JUMP] Chain {instance_chain_name}: -s {ip} -j {group_chain_name}")
        
        # Add instance default policy at the end of the instance chain
        default_policy = instance.firewall_default_policy.upper()
        if default_policy not in ["ACCEPT", "DROP", "REJECT"]:
            default_policy = "ACCEPT" # Safe default
        _run_iptables(["iptables", "-A", instance_chain_name, "-j", default_policy])
        logger.info(f"  [POLICY] Chain {instance_chain_name}: Default policy set to {default_policy}")

    logger.info("--- Firewall Rules Application Finished ---")
