#!/bin/bash
# Script to apply all firewall rules using the central Python script.
# This is called on boot by the iptables-openvpn.service.

# Absolute path to the Python interpreter in the virtual environment
PYTHON_EXEC="/opt/vpn-manager-env/bin/python3"
# Absolute path to the firewall application script
APPLY_SCRIPT="/opt/vpn-manager/backend/apply_firewall_rules.py"
LOG_FILE="/var/log/vpn_manager_firewall.log"

echo "---" >> "$LOG_FILE"
echo "$(date): Applying firewall rules..." >> "$LOG_FILE"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "$(date): ERROR: Python executable not found at $PYTHON_EXEC" >> "$LOG_FILE"
    exit 1
fi

if [ ! -f "$APPLY_SCRIPT" ]; then
    echo "$(date): ERROR: Firewall apply script not found at $APPLY_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# Execute the script and log its output
"$PYTHON_EXEC" "$APPLY_SCRIPT" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): Firewall rules applied successfully." >> "$LOG_FILE"
else
    echo "$(date): ERROR: The firewall script exited with an error. Check logs above." >> "$LOG_FILE"
fi
