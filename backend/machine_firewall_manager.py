import uuid
import logging
from typing import List, Dict, Optional

# The refactored iptables_manager is now the source of truth and handles all file I/O and rule application.
from . import iptables_manager as manager
from .iptables_manager import MachineFirewallRule

logger = logging.getLogger(__name__)


def get_all_rules() -> List[Dict]:
    """Returns all machine firewall rules, sorted by order."""
    rules = manager.get_all_rules()
    rules.sort(key=lambda r: r.order)
    return [r.to_dict() for r in rules]


def add_rule(rule_data: Dict) -> Dict:
    """Adds a new machine firewall rule."""
    rules = manager.get_all_rules()
    
    if not rule_data.get("id"):
        rule_data["id"] = str(uuid.uuid4())
    
    # Assign a default order if not provided
    if rule_data.get("order") is None:
        rule_data["order"] = len(rules) if rules else 0
        
    new_rule = MachineFirewallRule.from_dict(rule_data)
    rules.append(new_rule)
    
    success, error = manager.save_all_rules(rules)
    if not success:
        raise Exception(f"Failed to save and apply new rule: {error}")

    logger.info(f"Added new machine firewall rule: {new_rule.id}")
    return new_rule.to_dict()


def delete_rule(rule_id: str):
    """Deletes a machine firewall rule by ID."""
    rules = manager.get_all_rules()
    original_len = len(rules)
    
    rules = [r for r in rules if r.id != rule_id]
    
    if len(rules) == original_len:
        logger.warning(f"Attempted to delete non-existent rule: {rule_id}")
        raise ValueError("Rule not found")
        
    # Re-calculate order to be consecutive
    rules.sort(key=lambda r: r.order)
    for i, rule in enumerate(rules):
        rule.order = i
        
    success, error = manager.save_all_rules(rules)
    if not success:
        raise Exception(f"Failed to save and apply rules after deleting rule: {error}")

    logger.info(f"Deleted machine firewall rule: {rule_id}")


def update_rule(rule_id: str, rule_data: Dict) -> Dict:
    """Updates an existing machine firewall rule."""
    rules = manager.get_all_rules()
    rule_to_update = next((r for r in rules if r.id == rule_id), None)

    if not rule_to_update:
        raise ValueError("Rule not found for update")

    # Update rule attributes from the provided data
    for key, value in rule_data.items():
        if hasattr(rule_to_update, key):
            setattr(rule_to_update, key, value)

    success, error = manager.save_all_rules(rules)
    if not success:
        raise Exception(f"Failed to save and apply rules after updating rule: {error}")
    
    logger.info(f"Updated machine firewall rule: {rule_id}")
    return rule_to_update.to_dict()


def update_rule_order(orders: List[Dict]):
    """
    Updates the order of rules based on a list of {"id": "...", "order": N} objects.
    """
    rules = manager.get_all_rules()
    id_to_order_map = {item["id"]: item["order"] for item in orders}
    
    for rule in rules:
        if rule.id in id_to_order_map:
            rule.order = id_to_order_map[rule.id]
            
    success, error = manager.save_all_rules(rules)
    if not success:
        raise Exception(f"Failed to save and apply reordered rules: {error}")
            
    logger.info("Updated order of machine firewall rules.")
