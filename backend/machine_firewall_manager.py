import json
import os
import uuid
import logging
from typing import List, Dict, Optional, Union

# Assuming iptables_manager.py is in the same directory and contains MachineFirewallRule
from iptables_manager import MachineFirewallRule, apply_machine_firewall_rules

logger = logging.getLogger(__name__)

# Directory where configuration files are stored
CONFIG_DIR = "/opt/vpn-manager/config"
MACHINE_FIREWALL_RULES_FILE = os.path.join(CONFIG_DIR, "machine_firewall_rules.json")

class MachineFirewallManager:
    def __init__(self):
        try:
            self.rules: List[MachineFirewallRule] = []
            load_success = self._load_rules()
            # Apply rules on startup ONLY if loading was successful
            if load_success:
                self.apply_all_rules()
        except Exception as e:
            logger.error(f"FATAL: Error during MachineFirewallManager initialization: {e}", exc_info=True)
            # Re-raise to crash early and show full traceback
            raise 

    def _load_rules(self) -> bool: # Added return type for clarity
        """Loads machine firewall rules from a JSON file."""
        if not os.path.exists(CONFIG_DIR):
            logger.info(f"Creating config directory: {CONFIG_DIR}")
            os.makedirs(CONFIG_DIR)
        
        if os.path.exists(MACHINE_FIREWALL_RULES_FILE):
            try:
                logger.debug(f"Attempting to read rules from {MACHINE_FIREWALL_RULES_FILE}")
                with open(MACHINE_FIREWALL_RULES_FILE, 'r') as f:
                    rules_data = json.load(f)
                
                # Add logging for the raw loaded data
                logger.debug(f"Raw rules data loaded: {rules_data}")

                # Detailed error checking during deserialization
                loaded_rules = []
                for r_data in rules_data:
                    try:
                        loaded_rules.append(MachineFirewallRule.from_dict(r_data))
                    except Exception as rule_e:
                        logger.error(f"Error deserializing rule data '{r_data}': {rule_e}")
                        # Decide how to handle this: skip the rule, fail entirely, etc.
                        # For now, we'll log and continue if possible, but it implies a corrupt file.
                        pass # Continue processing other rules
                self.rules = loaded_rules
                
                logger.info(f"Loaded {len(self.rules)} machine firewall rules successfully.")
                return True
            except json.JSONDecodeError as json_e:
                logger.error(f"JSON decoding error in {MACHINE_FIREWALL_RULES_FILE}: {json_e}")
                self.rules = []
                return False
            except Exception as e:
                logger.error(f"Generic error loading machine firewall rules from {MACHINE_FIREWALL_RULES_FILE}: {e}")
                self.rules = []
                return False
        else:
            self.rules = []
            logger.info("No existing machine firewall rules file found. Initializing with empty rules.")
            return True # No file is not an error

    def _save_rules(self):
        """Saves current machine firewall rules to a JSON file."""
        try:
            with open(MACHINE_FIREWALL_RULES_FILE, 'w') as f:
                json.dump([r.to_dict() for r in self.rules], f, indent=4)
            logger.info(f"Saved {len(self.rules)} machine firewall rules.")
        except Exception as e:
            logger.error(f"Error saving machine firewall rules to {MACHINE_FIREWALL_RULES_FILE}: {e}")

    def get_all_rules(self) -> List[Dict]:
        """Returns all machine firewall rules as dictionaries, sorted by order."""
        self.rules.sort(key=lambda r: r.order)
        return [r.to_dict() for r in self.rules]

    def add_rule(self, rule_data: Dict) -> Dict:
        """Adds a new machine firewall rule and applies it."""
        if not rule_data.get("id"):
            rule_data["id"] = str(uuid.uuid4())
        
        # Assign an order if not provided
        if rule_data.get("order") is None:
            rule_data["order"] = len(self.rules)
        
        new_rule = MachineFirewallRule.from_dict(rule_data)
        self.rules.append(new_rule)
        self._save_rules()
        
        success, error = self.apply_all_rules() # Apply changes immediately
        if not success:
            # If applying rules fails, we should ideally roll back the add,
            # but for now, raising an exception is crucial for feedback.
            # We reload from the saved state to ensure consistency.
            self._load_rules() 
            raise Exception(f"Failed to apply rules after adding new rule: {error}")

        logger.info(f"Added new machine firewall rule: {new_rule.id}")
        return new_rule.to_dict()

    def delete_rule(self, rule_id: str):
        """Deletes a machine firewall rule by ID and applies changes."""
        original_len = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        if len(self.rules) == original_len:
            logger.warning(f"Attempted to delete non-existent rule: {rule_id}")
            raise ValueError("Rule not found")
        
        self._reorder_rules_consecutively()
        self._save_rules()

        success, error = self.apply_all_rules() # Apply changes immediately
        if not success:
            # Reload from saved state to roll back the deletion in memory
            self._load_rules()
            raise Exception(f"Failed to apply rules after deleting rule: {error}")

        logger.info(f"Deleted machine firewall rule: {rule_id}")

    def update_rule(self, rule_id: str, rule_data: Dict):
        """Updates an existing machine firewall rule and applies changes."""
        rule_to_update = next((r for r in self.rules if r.id == rule_id), None)
        if not rule_to_update:
            raise ValueError("Rule not found for update")

        # Update rule attributes from the provided data
        rule_to_update.chain = rule_data.get('chain', rule_to_update.chain).upper()
        rule_to_update.action = rule_data.get('action', rule_to_update.action).upper()
        rule_to_update.protocol = rule_data.get('protocol', rule_to_update.protocol)
        if rule_to_update.protocol:
            rule_to_update.protocol = rule_to_update.protocol.lower()
        rule_to_update.source = rule_data.get('source', rule_to_update.source)
        rule_to_update.destination = rule_data.get('destination', rule_to_update.destination)
        rule_to_update.port = rule_data.get('port', rule_to_update.port)
        rule_to_update.in_interface = rule_data.get('in_interface', rule_to_update.in_interface)
        rule_to_update.out_interface = rule_data.get('out_interface', rule_to_update.out_interface)
        rule_to_update.state = rule_data.get('state', rule_to_update.state)
        rule_to_update.comment = rule_data.get('comment', rule_to_update.comment)
        rule_to_update.table = rule_data.get('table', rule_to_update.table).lower()
        # Order is managed separately by update_rule_order

        self._save_rules()

        success, error = self.apply_all_rules()
        if not success:
            # Reload from saved state to roll back the update in memory
            self._load_rules()
            raise Exception(f"Failed to apply rules after updating rule: {error}")
        
        logger.info(f"Updated machine firewall rule: {rule_id}")
        return rule_to_update.to_dict()

    def update_rule_order(self, orders: List[Dict]):
        """
        Updates the order of rules based on a list of {"id": "...", "order": N} objects.
        Then reapplies all rules.
        """
        id_to_order_map = {item["id"]: item["order"] for item in orders}
        for rule in self.rules:
            if rule.id in id_to_order_map:
                rule.order = id_to_order_map[rule.id]
        
        self.rules.sort(key=lambda r: r.order)
        self._save_rules()

        success, error = self.apply_all_rules() # Apply changes immediately
        if not success:
            # Reload from saved state to roll back reordering
            self._load_rules()
            raise Exception(f"Failed to apply reordered rules: {error}")
            
        logger.info("Updated order of machine firewall rules.")

    def _reorder_rules_consecutively(self):
        """Ensures rule orders are consecutive after deletion/reordering."""
        self.rules.sort(key=lambda r: r.order)
        for i, rule in enumerate(self.rules):
            rule.order = i
            
    def apply_all_rules(self) -> (bool, Optional[str]):
        """Applies all currently managed machine firewall rules using iptables_manager."""
        self.rules.sort(key=lambda r: r.order) # Ensure rules are applied in order
        success, error = apply_machine_firewall_rules(self.rules)
        if not success:
            logger.error(f"Failed to apply machine firewall rules: {error}")
        else:
            logger.info("Machine firewall rules successfully applied to system.")
        return success, error

# Initialize the manager
machine_firewall_manager = MachineFirewallManager()
