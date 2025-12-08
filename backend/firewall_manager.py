import json
import os
import subprocess
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel
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
    action: str # ACCEPT, DROP, REJECT
    protocol: str # tcp, udp, icmp, all
    port: Optional[str] = None # single port or range
    destination: str # CIDR or "0.0.0.0/0" (any)
    description: str = ""
    order: int = 0

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
    
    # Validation: Ensure member belongs to group's instance
    # client_identifier is "instance_client". We expect prefix to match group.instance_id
    # But group.instance_id is "server_test", client_id is "server_test_client1"
    # Actually wait. `client_identifier` passed from frontend is usually "instance_client".
    # `subnet_info["instance_name"]` should match `group.instance_id`.
    
    if subnet_info["instance_name"] != group.instance_id:
        raise ValueError(f"Client does not belong to instance {group.instance_id}")

    if client_identifier not in group.members:
        # 1. Allocate Static IP
        instance_name = subnet_info["instance_name"]
        client_base_name = client_identifier.replace(f"{instance_name}_", "")
        
        ip = ip_manager.allocate_static_ip(instance_name, subnet_info["subnet"], client_base_name)
        if not ip:
            raise RuntimeError("Failed to allocate static IP")

        group.members.append(client_identifier)
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
        client_base_name = client_identifier.replace(f"{instance_name}_", "")
        ip_manager.release_static_ip(instance_name, client_base_name)
        
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
            ip_manager.release_static_ip(instance_name, client_name)

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
    """
    logger.info("Applying firewall rules...")
    
    # We need instance manager to resolve instance names from client IDs
    # Since we can't easily import instance_manager (circular), we might need to load instances.json manually here
    # or handle this logic differently.
    # Let's try loading instances.json directly as it is safe.
    instances_data = []
    try:
        with open("/opt/vpn-manager/backend/data/instances.json", "r") as f:
            instances_data = json.load(f)
    except: pass
    
    # Helper to find IP
    def get_client_ip(member_id):
        # formatted_name = instance.name + "_" + client_name
        for inst in instances_data:
            prefix = inst["name"] + "_"
            if member_id.startswith(prefix):
                 client_name_only = member_id[len(prefix):]
                 return ip_manager.get_assigned_ip(inst["name"], client_name_only)
        return None

    # Load all Data
    groups = _load_groups()
    rules = _load_rules()
    
    # 1. Flush/Create Chain
    subprocess.run(["iptables", "-N", CHAIN_NAME], check=False) # Ensure exist
    subprocess.run(["iptables", "-F", CHAIN_NAME], check=True) # Flush
    
    # Ensure Chain is referenced in FORWARD (at top)
    # Check if rule exists
    check = subprocess.run(f"iptables -C FORWARD -j {CHAIN_NAME}", shell=True)
    if check.returncode != 0:
        subprocess.run(f"iptables -I FORWARD 1 -j {CHAIN_NAME}", shell=True)
    
    # 2. Iterate Rules
    # Rules are global or per group?
    # Our data model is per group. But we also have "order".
    # If we want a global ordering (e.g. Block All at very bottom), rules need a global context.
    # Current model: Rule belongs to Group.
    # Execution: For each Group, collect IPs, then apply rules?
    # NO. Rules should be applied in a global list if we want inter-mixing, OR per group.
    # Usually "Group A has these rules".
    
    # Let's process group by group.
    for group in groups:
        group_rules = [r for r in rules if r.group_id == group.id]
        group_rules.sort(key=lambda x: x.order)
        
        member_ips = []
        for member in group.members:
            ip = get_client_ip(member)
            if ip:
                member_ips.append(ip)
        
        if not member_ips:
            continue
            
        # Combine IPs for iptables (comma separated, max items limitation usually)
        # If too many, we need multiple rules or ipset. For MVP, multiple rules loops.
        
        for rule in group_rules:
            # Construct iptables command
            # -s <source_ip>
            
            # Protocol
            proto_arg = f"-p {rule.protocol}"
            if rule.protocol == "all":
                proto_arg = "-p all"
            
            # Port
            port_arg = ""
            if rule.port and rule.protocol in ["tcp", "udp"]:
                port_arg = f"--dport {rule.port}"
            
            # Destination
            dest_arg = ""
            if rule.destination and rule.destination != "0.0.0.0/0":
                dest_arg = f"-d {rule.destination}"
            
            # Action
            target = rule.action.upper() # ACCEPT, DROP, REJECT
            
            # Apply for each IP (inefficient for many users, need IPSet later)
            for ip in member_ips:
                cmd = f"iptables -A {CHAIN_NAME} -s {ip} {proto_arg} {port_arg} {dest_arg} -j {target}"
                try:
                    subprocess.run(cmd, shell=True, check=True)
                except Exception as e:
                    logger.error(f"Failed to apply rule: {cmd} - {e}")

    logger.info("Firewall rules applied.")
