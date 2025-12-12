import logging
import uuid
from typing import List, Dict, Optional
from sqlmodel import Session, select

from database import engine
from models import MachineFirewallRule
import iptables_manager

logger = logging.getLogger(__name__)

class MachineFirewallManager:
    def __init__(self):
        # We don't load into memory anymore, we query DB.
        # But we might want to apply rules on init.
        # The startup event calls apply_all_rules, so we can skip here or keep safety check.
        pass

    def get_all_rules(self) -> List[Dict]:
        with Session(engine) as session:
            rules = session.exec(select(MachineFirewallRule).order_by(MachineFirewallRule.order)).all()
            result = []
            for r in rules:
                d = r.dict()
                d['id'] = str(d['id'])
                result.append(d)
            return result

    def add_rule(self, rule_data: Dict) -> Dict:
        with Session(engine) as session:
            if not rule_data.get("id"):
                rule_data["id"] = uuid.uuid4()
            
            # Determine order
                # Order calculation: We want the new rule to be at the END of the list.
                # If we use global ordering, we must ensure it's > max(all_rules).
                # The user reported "rule goes in second position", which suggests reordering logic might be flawed 
                # or we are calculating max wrong. 
                # Let's ensure strict increasing order.
                existing = session.exec(select(MachineFirewallRule)).all()
                if existing:
                    max_order = max(r.order for r in existing)
                else:
                    max_order = -1
                rule_data["order"] = max_order + 1
            
            # Alias 'table' -> 'table_name' for model if needed, but model handles alias
            # Pydantic input dict might have 'table'. Model expects 'table_name' OR alias.
            # SQLModel/Pydantic should parse 'table' into 'table_name' if alias is set.
            
            rule = MachineFirewallRule(**rule_data)
            session.add(rule)
            session.commit()
            session.refresh(rule)
            
            self.apply_all_rules()
            res = rule.dict()
            res['id'] = str(res['id'])
            return res

    def delete_rule(self, rule_id: str):
        with Session(engine) as session:
            rule = session.get(MachineFirewallRule, uuid.UUID(rule_id))
            if not rule: raise ValueError("Rule not found")
            
            session.delete(rule)
            session.commit()
            
            # Reorder
            # Reorder all rules to close the gap
            # This is crucial: if we have gaps, max() logic works, but normalized list is cleaner.
            rules = session.exec(select(MachineFirewallRule).order_by(MachineFirewallRule.order)).all()
            for i, r in enumerate(rules):
                r.order = i
                session.add(r)
            session.commit()
            session.commit()
            
            self.apply_all_rules()

    def update_rule(self, rule_id: str, rule_data: Dict) -> Dict:
        with Session(engine) as session:
            rule = session.get(MachineFirewallRule, uuid.UUID(rule_id))
            if not rule: raise ValueError("Rule not found")
            
            # Update fields manually or via loop
            for k, v in rule_data.items():
                if k != "id" and hasattr(rule, k):
                    setattr(rule, k, v)
                elif k == "table": # Handle alias manually if Pydantic doesn't
                    rule.table_name = v
            
            session.add(rule)
            session.commit()
            session.refresh(rule)
            self.apply_all_rules()
            res = rule.dict()
            res['id'] = str(res['id'])
            return res

    def update_rule_order(self, orders: List[Dict]):
        with Session(engine) as session:
            for item in orders:
                rule = session.get(MachineFirewallRule, uuid.UUID(item["id"]))
                if rule:
                    rule.order = item["order"]
                    session.add(rule)
            session.commit()
            self.apply_all_rules()

    def apply_all_rules(self):
        logger.info("Applying Machine Firewall Rules (SQLModel)...")
        
        # 1. Clean Chains
        fw_chains = {
            "INPUT": iptables_manager.FW_INPUT_CHAIN,
            "OUTPUT": iptables_manager.FW_OUTPUT_CHAIN,
            "FORWARD": iptables_manager.FW_FORWARD_CHAIN
        }
        for chain in fw_chains.values():
            iptables_manager._create_or_flush_chain(chain)
            
        iptables_manager._ensure_jump_rule("INPUT", fw_chains["INPUT"], "filter", 2)
        iptables_manager._ensure_jump_rule("OUTPUT", fw_chains["OUTPUT"], "filter", 2)
        iptables_manager._ensure_jump_rule("FORWARD", fw_chains["FORWARD"], "filter", 2)

        # 2. Apply Rules
        with Session(engine) as session:
            rules = session.exec(select(MachineFirewallRule).order_by(MachineFirewallRule.order)).all()
            
            for rule in rules:
                target_chain = fw_chains.get(rule.chain)
                if not target_chain: continue
                
                # Build args using the helper from iptables_manager, but adapting object
                # iptables_manager expects a specific object or we can manually build.
                # Let's adapt our SQLModel object to what _build_iptables_args expects, 
                # or just use dict.
                # Actually _build_iptables_args expects 'MachineFirewallRule' class from iptables_manager (old).
                # We should update iptables_manager to be more flexible or map it.
                # Easiest: Map fields manually here to a list of args.
                
                # Construct arguments for _run_iptables
                # _run_iptables takes (table, args_list) and prepends 'iptables', '-t table'
                # So we just need the arguments starting from the action (-A).
                
                # Base command logic above constructed a full command list for reference/debugging
                # We need to extract just the args.
                
                # Determine action args
                action_args = ["-A", target_chain]
                
                args = []
                args.extend(action_args)
                
                if rule.protocol: args.extend(["-p", rule.protocol])
                if rule.source: args.extend(["-s", rule.source])
                if rule.destination: args.extend(["-d", rule.destination])
                if rule.in_interface: args.extend(["-i", rule.in_interface])
                if rule.out_interface: args.extend(["-o", rule.out_interface])
                if rule.state: args.extend(["-m", "state", "--state", rule.state])
                
                if rule.port and rule.action not in ["MASQUERADE", "SNAT", "DNAT"]:
                     args.extend(["--dport", str(rule.port)])

                args.extend(["-m", "comment", "--comment", f"ID_{rule.id}"])
                
                if rule.action == "MASQUERADE":
                    args.extend(["-j", "MASQUERADE"])
                elif rule.action == "SNAT":
                    args.extend(["-j", "SNAT", "--to-source", rule.destination])
                else:
                    args.extend(["-j", rule.action])
                
                iptables_manager._run_iptables(rule.table_name, args)

machine_firewall_manager = MachineFirewallManager()