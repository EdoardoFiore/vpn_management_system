import logging
import subprocess
from typing import List, Dict, Optional
from sqlmodel import Session, select
import uuid

from database import engine
from models import Group, GroupMember, FirewallRule, Client, Instance
import iptables_manager
import instance_manager
import ip_manager

logger = logging.getLogger(__name__)

# --- Group Mgmt ---

def create_group(name: str, instance_id: str, description: str = "") -> Group:
    # Resolve instance name to ID if needed (frontend sends name usually)
    # Actually, let's assume frontend sends ID or Name. 
    # vpn_manager logic handled ID. Let's strictly use ID or resolve.
    with Session(engine) as session:
        # Check if instance exists by ID
        inst = session.get(Instance, instance_id)
        if not inst:
            # Try by name
            inst = session.exec(select(Instance).where(Instance.name == instance_id)).first()
            if not inst:
                raise ValueError("Instance not found")
            instance_id = inst.id

        group_id = f"{instance_id}_{name.lower().replace(' ', '_')}"
        
        if session.get(Group, group_id):
            raise ValueError("Group exists")
            
        group = Group(id=group_id, instance_id=instance_id, name=name, description=description)
        session.add(group)
        session.commit()
        session.refresh(group)
        return group

def delete_group(group_id: str):
    with Session(engine) as session:
        group = session.get(Group, group_id)
        if group:
            session.delete(group) # Cascades should handle rules/members if configured, or manual delete
            # SQLModel relationships don't auto-cascade delete in DB unless defined in SA args.
            # Manually clean for safety.
            session.exec(select(GroupMember).where(GroupMember.group_id == group_id)).delete() # This might need delete() method
            # ... actually session.delete(obj) is cleaner.
            # Let's trust cascade or do manual query.
            # For simplicity:
            # Delete members links
            members = session.exec(select(GroupMember).where(GroupMember.group_id == group_id)).all()
            for m in members: session.delete(m)
            # Delete rules
            rules = session.exec(select(FirewallRule).where(FirewallRule.group_id == group_id)).all()
            for r in rules: session.delete(r)
            
            session.delete(group)
            session.commit()
            apply_firewall_rules()

def get_groups(instance_id: Optional[str] = None) -> List[Group]:
    with Session(engine) as session:
        if instance_id:
            return session.exec(select(Group).where(Group.instance_id == instance_id)).all()
        return session.exec(select(Group)).all()

def add_member_to_group(group_id: str, client_identifier: str, subnet_info: Dict[str, str]):
    # client_identifier e.g. "instance_clientname" or just "clientname"?
    # The frontend passes `client.name`.
    # subnet_info has instance_name.
    
    with Session(engine) as session:
        group = session.get(Group, group_id)
        if not group: raise ValueError("Group not found")
        
        # Resolve client
        # client_identifier might be "inst_client" or "client".
        # We need to find the Client object.
        # Use subnet_info['instance_name'] to help.
        
        inst_name = subnet_info.get("instance_name")
        # Resolve instance
        inst = session.exec(select(Instance).where(Instance.name == inst_name)).first()
        if not inst: inst = session.get(Instance, inst_name) # Try ID
        
        if not inst or inst.id != group.instance_id:
             raise ValueError("Instance mismatch")

        # Parse client name
        real_client_name = client_identifier
        prefix = f"{inst.name}_"
        if real_client_name.startswith(prefix):
            real_client_name = real_client_name[len(prefix):]
            
        client = session.exec(select(Client).where(Client.instance_id == inst.id, Client.name == real_client_name)).first()
        if not client:
            raise ValueError("Client not found")
            
        # Check if already member
        if session.get(GroupMember, (group_id, client.id)):
            return # Already member
            
        link = GroupMember(group_id=group_id, client_id=client.id)
        session.add(link)
        session.commit()
        apply_firewall_rules()

def remove_member_from_group(group_id: str, client_identifier: str, instance_name: str):
    with Session(engine) as session:
        # Resolve Client (similar logic)
        inst = session.exec(select(Instance).where(Instance.name == instance_name)).first()
        if not inst: inst = session.get(Instance, instance_name)
        
        real_client_name = client_identifier
        prefix = f"{inst.name}_"
        if real_client_name.startswith(prefix):
            real_client_name = real_client_name[len(prefix):]

        client = session.exec(select(Client).where(Client.instance_id == inst.id, Client.name == real_client_name)).first()
        if not client: return 

        link = session.get(GroupMember, (group_id, client.id))
        if link:
            session.delete(link)
            session.commit()
            apply_firewall_rules()

# --- Rules Mgmt ---

def add_rule(rule_data: dict) -> FirewallRule:
    with Session(engine) as session:
        rule = FirewallRule(**rule_data)
        session.add(rule)
        session.commit()
        session.refresh(rule)
        apply_firewall_rules()
        return rule

def delete_rule(rule_id: str):
    with Session(engine) as session:
        # rule_id is str, but model uses UUID. SQLModel converts automatically usually.
        # But session.get expects the exact type.
        rule = session.get(FirewallRule, uuid.UUID(rule_id))
        if rule:
            session.delete(rule)
            session.commit()
            apply_firewall_rules()

def update_rule(rule_id: str, group_id: str, action: str, protocol: str, destination: str, port: str = None, description: str = ""):
    with Session(engine) as session:
        rule = session.get(FirewallRule, uuid.UUID(rule_id))
        if not rule: raise ValueError("Rule not found")
        
        rule.action = action
        rule.protocol = protocol
        rule.destination = destination
        rule.port = port
        rule.description = description
        
        session.add(rule)
        session.commit()
        session.refresh(rule)
        apply_firewall_rules()
        return rule

def update_rule_order(orders: List[Dict]):
    with Session(engine) as session:
        for item in orders:
            rule = session.get(FirewallRule, uuid.UUID(item["id"]))
            if rule:
                rule.order = item["order"]
                session.add(rule)
        session.commit()
        apply_firewall_rules()

def get_rules(group_id: Optional[str] = None) -> List[FirewallRule]:
    with Session(engine) as session:
        if group_id:
            return session.exec(select(FirewallRule).where(FirewallRule.group_id == group_id)).all()
        return session.exec(select(FirewallRule)).all()

# --- Application ---

def _run_iptables(cmd: List[str]):
    try:
        subprocess.run(cmd, check=False, capture_output=True)
    except: pass

def apply_firewall_rules():
    logger.info("Applying Firewall Rules (SQLModel)...")
    
    with Session(engine) as session:
        instances = session.exec(select(Instance)).all()
        groups = session.exec(select(Group)).all()
        
        main_chain = "VPN_MAIN_FWD"
        instance_chains = [f"VI_{i.id}" for i in instances]
        group_chains = [f"VIG_{g.id}" for g in groups]
        
        iptables_manager._create_or_flush_chain(main_chain)
        for chain in instance_chains + group_chains:
            iptables_manager._create_or_flush_chain(chain)
            
        # Populate
        
        # 1. Groups
        for group in groups:
            chain = f"VIG_{group.id}"
            rules = session.exec(select(FirewallRule).where(FirewallRule.group_id == group.id).order_by(FirewallRule.order)).all()
            
            # Apply in order (append)
            # WAIT: iptables_manager usually does -I for reverse.
            # Here we are rebuilding the chain from scratch (flush). 
            # So -A (Append) in correct order 0..N is best.
            
            for rule in rules:
                cmd = ["iptables", "-A", chain]
                if rule.protocol != "all": cmd.extend(["-p", rule.protocol])
                if rule.destination and rule.destination != "0.0.0.0/0": cmd.extend(["-d", rule.destination])
                if rule.port and rule.protocol in ["tcp", "udp"]: cmd.extend(["--dport", rule.port])
                cmd.extend(["-j", rule.action.upper()])
                
                _run_iptables(cmd)
            
            _run_iptables(["iptables", "-A", chain, "-j", "RETURN"])

        # 2. Instances
        for inst in instances:
            chain = f"VI_{inst.id}"
            
            # Jumps from Main
            _run_iptables(["iptables", "-A", main_chain, "-s", inst.subnet, "-j", chain])
            _run_iptables(["iptables", "-A", main_chain, "-d", inst.subnet, "-j", chain])
            
            # Established
            _run_iptables(["iptables", "-A", chain, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
            
            # Forwarding Logic (VPN <-> VPN traffic or VPN <-> LAN)
            # If split tunnel, allow configured routes
            if inst.routes:
                for r in inst.routes:
                    if 'network' in r:
                        _run_iptables(["iptables", "-A", chain, "-s", inst.subnet, "-d", r['network'], "-j", "ACCEPT"])

            # Jumps to Groups
            # Get members via DB relationship
            # member.client.allocated_ip
            for group in inst.groups:
                g_chain = f"VIG_{group.id}"
                # Get IPs of members
                # Join GroupMember and Client
                member_ips = session.exec(
                    select(Client.allocated_ip)
                    .join(GroupMember)
                    .where(GroupMember.group_id == group.id)
                ).all()
                
                for ip in member_ips:
                    _run_iptables(["iptables", "-A", chain, "-s", ip, "-j", g_chain])
            
            # Default Policy
            if inst.firewall_default_policy == "ACCEPT":
                _run_iptables(["iptables", "-A", chain, "-j", "ACCEPT"])
            else:
                _run_iptables(["iptables", "-A", chain, "-j", "DROP"]) # or REJECT