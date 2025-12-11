#!/bin/bash
# This script is intentionally left blank.

# In the new architecture, firewall rules are stored declaratively in JSON files
# within the /opt/vpn-manager/backend/ directory.
# The `restore-iptables.sh` script, executed on boot, reads these files
# and applies the rules using a central Python script.

# This "save" script is called on shutdown by the persistence service. We do not
# want to save the current (potentially modified) state of iptables, as that
# would defeat the "single source of truth" principle of our JSON files.
# Therefore, this script does nothing, ensuring that only the rules defined
# in our application are applied on the next boot.

exit 0
