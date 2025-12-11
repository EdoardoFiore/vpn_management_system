# backend/apply_firewall_rules.py
import os
import json
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
OPENVPN_DIR = os.getenv("OPENVPN_DIR", "/etc/openvpn")
MACHINE_RULES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'machine_rules.json')

# Custom Chains
MACHINE_FW_INPUT_CHAIN = "MACHINE_FW_INPUT"
VPN_MAIN_FWD_CHAIN = "VPN_MAIN_FWD"


def run_command(command):
    """Runs a shell command and logs its output."""
    try:
        logging.info(f"Executing: {command}")
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            logging.info(result.stdout)
        if result.stderr:
            logging.warning(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing command: {command}")
        logging.error(f"Stderr: {e.stderr}")
        logging.error(f"Stdout: {e.stdout}")
        return False


def get_managed_chains():
    """Gathers all custom chains that this script manages."""
    managed_chains = {MACHINE_FW_INPUT_CHAIN, VPN_MAIN_FWD_CHAIN}
    
    # Add chains for VPN instances and groups
    for item in os.listdir(OPENVPN_DIR):
        instance_dir = os.path.join(OPENVPN_DIR, item)
        if os.path.isdir(instance_dir) and item.startswith("server_"):
            instance_name = item.replace("server_", "")
            managed_chains.add(f"VI_{instance_name}")
            
            rules_file = os.path.join(instance_dir, 'rules.json')
            if os.path.exists(rules_file):
                with open(rules_file, 'r') as f:
                    groups = json.load(f)
                    for group in groups:
                        managed_chains.add(f"VIG_{group['name']}")
    
    return list(managed_chains)


def flush_iptables():
    """Flushes all rules and deletes all managed custom chains."""
    logging.info("--- Flushing IPTables ---")
    
    managed_chains = get_managed_chains()

    # Flush rules from standard chains
    run_command("iptables -F INPUT")
    run_command("iptables -F FORWARD")
    run_command("iptables -F OUTPUT")
    run_command("iptables -t nat -F")

    # Flush managed chains before deleting them
    for chain in managed_chains:
        run_command(f"iptables -F {chain}")
        
    # Delete managed chains
    for chain in managed_chains:
        run_command(f"iptables -X {chain}")


def create_custom_chains():
    """Creates all necessary custom chains."""
    logging.info("--- Creating Custom Chains ---")
    
    managed_chains = get_managed_chains()
    for chain in managed_chains:
        run_command(f"iptables -N {chain}")


def apply_machine_firewall_rules():
    """Applies the main machine firewall rules from machine_rules.json."""
    logging.info("--- Applying Machine Firewall Rules ---")
    
    if not os.path.exists(MACHINE_RULES_FILE):
        logging.warning(f"Machine rules file not found at {MACHINE_RULES_FILE}")
        return

    with open(MACHINE_RULES_FILE, 'r') as f:
        rules = json.load(f)

    for rule in rules:
        cmd = rule['rule']
        # Ensure rules are appended to our custom chain, not a built-in one
        if f"-A {rule['chain']}" in cmd:
            if rule['chain'] == 'INPUT': # Remap INPUT to our custom chain
                 cmd = cmd.replace("-A INPUT", f"-A {MACHINE_FW_INPUT_CHAIN}")
            
            # Add comment with ID for traceability
            cmd_with_comment = f"{cmd} -m comment --comment ID_{rule['id']}"
            run_command(cmd_with_comment)
        else:
            logging.warning(f"Skipping rule with malformed chain: {cmd}")


def apply_vpn_firewall_rules():
    """Applies firewall rules for all VPN instances and their groups."""
    logging.info("--- Applying VPN Firewall Rules ---")
    
    for item in os.listdir(OPENVPN_DIR):
        instance_dir = os.path.join(OPENVPN_DIR, item)
        if not (os.path.isdir(instance_dir) and item.startswith("server_")):
            continue

        instance_name = item.replace("server_", "")
        instance_chain = f"VI_{instance_name}"
        
        # Get instance config to find the subnet
        config_path = os.path.join(instance_dir, 'config.json')
        if not os.path.exists(config_path):
            continue
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        subnet = config.get('subnet')
        if not subnet:
            continue

        # Add jump from main VPN forward chain to the instance-specific chain
        run_command(f"iptables -A {VPN_MAIN_FWD_CHAIN} -s {subnet} -j {instance_chain}")

        # Process group rules for the instance
        rules_file = os.path.join(instance_dir, 'rules.json')
        if not os.path.exists(rules_file):
            run_command(f"iptables -A {instance_chain} -j ACCEPT") # Default accept if no rules
            continue

        with open(rules_file, 'r') as f:
            groups = json.load(f)

        for group in sorted(groups, key=lambda x: x['priority']):
            group_chain = f"VIG_{group['name']}"
            
            # Add jump from instance chain to group chain for each client IP
            for client_ip in group.get('static_ips', []):
                run_command(f"iptables -A {instance_chain} -s {client_ip} -j {group_chain}")

            # Apply rules for the group
            for rule in sorted(group['rules'], key=lambda x: x['priority']):
                cmd = rule['rule'].replace('-A <chain>', f'-A {group_chain}')
                cmd_with_comment = f"{cmd} -m comment --comment ID_{rule['id']}"
                run_command(cmd_with_comment)
            
            # Each group chain must end with a RETURN to go back to the instance chain
            run_command(f"iptables -A {group_chain} -j RETURN")
        
        # Fallback for clients in the instance but not in a group
        run_command(f"iptables -A {instance_chain} -j ACCEPT")


def apply_base_rules_and_jumps():
    """Applies essential rules and jumps from built-in chains to our custom chains."""
    logging.info("--- Applying Base Rules and Jumps ---")
    
    # Set default policies
    run_command("iptables -P INPUT DROP")
    run_command("iptables -P FORWARD DROP")
    run_command("iptables -P OUTPUT ACCEPT")

    # --- INPUT Chain ---
    # Insert jumps to our custom chains at the top
    run_command(f"iptables -A INPUT -j {MACHINE_FW_INPUT_CHAIN}")
    
    # Allow loopback traffic
    run_command("iptables -A INPUT -i lo -j ACCEPT")
    
    # Allow established and related connections
    run_command(f"iptables -A {MACHINE_FW_INPUT_CHAIN} -m state --state RELATED,ESTABLISHED -j ACCEPT")
    
    # Allow OpenVPN connections
    for item in os.listdir(OPENVPN_DIR):
        instance_dir = os.path.join(OPENVPN_DIR, item)
        if os.path.isdir(instance_dir) and item.startswith("server_"):
            config_path = os.path.join(instance_dir, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                port = config.get('port')
                proto = config.get('protocol', 'udp').lower()
                if port:
                    run_command(f"iptables -A INPUT -p {proto} --dport {port} -j ACCEPT")

    # Allow traffic from VPN tunnels
    for i in range(10): # Assuming tun0-tun9
        run_command(f"iptables -A INPUT -i tun{i} -j ACCEPT")

    # --- FORWARD Chain ---
    # Insert jump to our main VPN forwarding chain
    run_command(f"iptables -A FORWARD -j {VPN_MAIN_FWD_CHAIN}")

    # Allow forwarding for established connections (essential for return traffic)
    for i in range(10):
        run_command(f"iptables -A FORWARD -i eth0 -o tun{i} -m state --state RELATED,ESTABLISHED -j ACCEPT")
        run_command(f"iptables -A FORWARD -i tun{i} -o eth0 -j ACCEPT") # Simplified, might need refinement

    # --- NAT Table ---
    # Apply NAT for all VPN instances
    for item in os.listdir(OPENVPN_DIR):
        instance_dir = os.path.join(OPENVPN_DIR, item)
        if os.path.isdir(instance_dir) and item.startswith("server_"):
            config_path = os.path.join(instance_dir, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                subnet = config.get('subnet')
                if subnet:
                    run_command(f"iptables -t nat -A POSTROUTING -s {subnet} -o eth0 -j MASQUERADE")

def main():
    """Main function to apply all firewall rules."""
    logging.info("=== Starting Firewall Rule Application ===")
    
    # 1. Flush existing rules and chains
    flush_iptables()
    
    # 2. Recreate all custom chains
    create_custom_chains()
    
    # 3. Apply base rules and main jumps to custom chains
    apply_base_rules_and_jumps()
    
    # 4. Apply the machine-specific firewall rules
    apply_machine_firewall_rules()

    # 5. Apply all the VPN-specific instance and group rules
    apply_vpn_firewall_rules()

    logging.info("=== Firewall Rule Application Finished Successfully ===")


if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() != 0:
        logging.error("This script must be run as root.")
        exit(1)
    
    main()
