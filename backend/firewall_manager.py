import json
import os
import re
import subprocess
import logging
from typing import List, Dict, Optional
from ipaddress import ip_network, AddressValueError
from pydantic import BaseModel, validator
import ip_manager

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

def get_rules(group_id: Optional[str] = None) -> List[Rule]:
    rules = _load_rules()
    if group_id:
        return [r for r in rules if r.group_id == group_id]
    return rules

# --- IPTables Application ---

def _get_group_ips(group_id: str) -> List[str]:
    """Retrieve all static IPs assigned to members of this group."""
    groups = _load_groups()
    group = next((g for g in groups if g.id == group_id), None)
    if not group: 
        return []
    
    ips = []
    # Members are "instance_clientname"
    # We need to find their instance and read CCD
    # Optimization: We could store instance info in Group, but for now we parse name
    for member in group.members:
        # Heuristic to split instance_name from client_name
        # member: "server_test_client" -> instance: "server_test", client: "client" ??
        # Or "server_Default_edoardo" -> instance: "server_Default" ??
        # The naming convention is instance.name + "_" + client_name.
        # But instance name can have underscores.
        # Ideally, we should store structured member info.
        # For now, we accept a limitation or need a lookup function.
        # Let's rely on `ip_manager` which needs explicit instance name.
        # We need to fetch ALL instances to match prefixes.
        # Circular dependency avoidance: We will inject instances? Or better, store {instance, client} in members.
        # For this MVP, let's assume we can scan CCDs or try to match against known instances.
        
        # Better: Group members should be stored as objects/dicts: {"instance": "foo", "client": "bar"}
        # But for backward compat with simple list in model:
        # Let's assume we can lookup ip_manager using a helper if strictly needed.
        # Or better yet, just iterate all CCDs for known instances?
        
        # Let's try to pass instances in `apply_firewall_rules`?
        pass # To be implemented inside apply_firewall_rules logic
    return []

def apply_firewall_rules():
    """
    Re-generates the VPN_sys_FORWARD chain based on current groups and rules.
    This version is more robust and provides detailed logging.
    """
    logger.info("Applying firewall rules...")
    
    # Load instances configuration with proper error handling
    instances_data = []
    instances_file = "/opt/vpn-manager/backend/data/instances.json"
    try:
        with open(instances_file, "r") as f:
            instances_data = json.load(f)
        # Sort instances by name length (desc) to avoid prefix conflicts (e.g., "vpn" vs "vpn_dev")
        instances_data.sort(key=lambda x: len(x.get("name", "")), reverse=True)
        logger.info(f"Successfully loaded {len(instances_data)} instance definitions.")
    except FileNotFoundError:
        logger.error(f"CRITICAL: Could not find instances file at {instances_file}. Cannot apply any client-specific rules.")
        return
    except json.JSONDecodeError:
        logger.error(f"CRITICAL: Could not parse instances file at {instances_file}. File might be corrupt.")
        return
    except Exception as e:
        logger.error(f"CRITICAL: An unexpected error occurred loading {instances_file}: {e}")
        return

    # Helper function to find a client's IP
    def get_client_ip(member_id):
        logger.debug(f"Attempting to find IP for member '{member_id}'")
        for inst in instances_data:
            instance_name = inst.get("name")
            if not instance_name:
                continue
            
            prefix = f"{instance_name}_"
            if member_id.startswith(prefix):
                 client_name_only = member_id[len(prefix):]
                 logger.debug(f"Match found. Instance: '{instance_name}', Client: '{client_name_only}'")
                 # Pass the full member_id, as it matches the CCD file name (e.g., instance_client)
                 ip = ip_manager.get_assigned_ip(instance_name, member_id)
                 if ip:
                     logger.info(f"Found IP {ip} for client '{member_id}' in instance '{instance_name}'.")
                     return ip
                 else:
                     logger.warning(f"Could not find assigned IP for client '{member_id}' in instance '{instance_name}'. CCD file might be missing or empty.")
                 return None # Important: return after first match
        
        logger.warning(f"No matching instance found for member_id '{member_id}'.")
        return None

    # Load all groups and rules
    groups = _load_groups()
    rules = _load_rules()
    
    # 1. Flush/Create Chain
    try:
        subprocess.run(["iptables", "-N", CHAIN_NAME], check=False, capture_output=True) # Ensure chain exists, ignore error if it does
        subprocess.run(["iptables", "-F", CHAIN_NAME], check=True) # Flush existing rules
        logger.info(f"Chain '{CHAIN_NAME}' created/flushed successfully.")
    except Exception as e:
        logger.error(f"Failed to create or flush iptables chain '{CHAIN_NAME}': {e}")
        return
    
    # 2. Ensure Chain is referenced in FORWARD chain (at the top)
    check_cmd = f"iptables -C FORWARD -j {CHAIN_NAME}"
    if subprocess.run(check_cmd, shell=True, capture_output=True).returncode != 0:
        insert_cmd = f"iptables -I FORWARD 1 -j {CHAIN_NAME}"
        try:
            subprocess.run(insert_cmd, shell=True, check=True)
            logger.info(f"Inserted jump from FORWARD to '{CHAIN_NAME}'.")
        except Exception as e:
            logger.error(f"Failed to insert jump rule into FORWARD chain: {e}")
            return

    # 3. Iterate through groups and apply their rules
    for group in groups:
        logger.debug(f"Processing group '{group.name}' (ID: {group.id})")
        group_rules = sorted([r for r in rules if r.group_id == group.id], key=lambda x: x.order)
        
        if not group_rules:
            logger.debug(f"No rules found for group '{group.name}'. Skipping.")
            continue
            
        member_ips = []
        for member in group.members:
            ip = get_client_ip(member)
            if ip:
                member_ips.append(ip)
        
        if not member_ips:
            logger.warning(f"Group '{group.name}' has no members with assigned IPs. Skipping rule application for this group.")
            continue
            
        logger.info(f"Applying {len(group_rules)} rules for {len(member_ips)} members in group '{group.name}'.")

        for rule in group_rules:
            # Construct iptables command arguments
            proto_arg = f"-p {rule.protocol}" if rule.protocol != "all" else ""
            port_arg = f"--dport {rule.port}" if rule.port and rule.protocol in ["tcp", "udp"] else ""
            dest_arg = f"-d {rule.destination}" if rule.destination and rule.destination != "0.0.0.0/0" else ""
            target = rule.action.upper()
            
            # Apply the rule for each member IP
            for ip in member_ips:
                cmd_parts = ["iptables", "-A", CHAIN_NAME, "-s", ip]
                if proto_arg: cmd_parts.extend(proto_arg.split())
                if port_arg: cmd_parts.extend(port_arg.split())
                if dest_arg: cmd_parts.extend(dest_arg.split())
                cmd_parts.extend(["-j", target])
                
                cmd_str = " ".join(cmd_parts)
                logger.info(f"Executing: {cmd_str}")
                
                try:
                    subprocess.run(cmd_parts, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to apply rule: {cmd_str}\n  Error: {e.stderr.strip()}")
                except Exception as e:
                    logger.error(f"An unexpected error occurred executing rule: {cmd_str}\n  Error: {e}")

    logger.info("Firewall rules application process finished.")
