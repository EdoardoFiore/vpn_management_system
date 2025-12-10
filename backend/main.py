import os
import re
from typing import List, Optional, Dict, Union # Added Union
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import vpn_manager
import instance_manager
import network_utils
import firewall_manager as instance_firewall_manager # Renamed for clarity on instance-specific firewall
from machine_firewall_manager import machine_firewall_manager # Will be created later

# --- Modelli Pydantic ---
class ClientRequest(BaseModel):
    client_name: str

class GroupRequest(BaseModel):
    name: str
    instance_id: str
    description: str = ""

class GroupMemberRequest(BaseModel):
    client_identifier: str # e.g. "instance_clientname"
    subnet_info: Dict[str, str]

class RuleRequest(BaseModel):
    group_id: str
    action: str
    protocol: str
    port: Optional[str] = None
    destination: str
    description: str = ""
    order: Optional[int] = None

class RuleOrderRequest(BaseModel):
    id: str
    order: int

# Pydantic model for Machine-level Firewall Rules
class MachineFirewallRuleModel(BaseModel):
    id: Optional[str] = None # Will be generated if not provided
    chain: str
    action: str
    protocol: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    port: Optional[Union[int, str]] = None
    in_interface: Optional[str] = None
    out_interface: Optional[str] = None
    state: Optional[str] = None
    comment: Optional[str] = None
    table: str = "filter"
    order: int = 0

class MachineFirewallRuleOrderRequest(BaseModel):
    id: str
    order: int

# Regex per validare i nomi dei client (permette alfanumerici, underscore, trattini e punti)
CLIENT_NAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"

# --- Modelli Pydantic ---
class ClientRequest(BaseModel):
    client_name: str

class RouteConfig(BaseModel):
    network: str  # e.g., "192.168.1.0/24"
    interface: str  # e.g., "eth1"

class RouteUpdateRequest(BaseModel):
    tunnel_mode: str = "full"  # "full" or "split"
    routes: List[RouteConfig] = []  # Custom routes for split tunnel
    dns_servers: List[str] = [] # Optional custom DNS servers

class InstanceRequest(BaseModel):
    name: str
    port: int
    subnet: str
    protocol: str = "udp"
    tunnel_mode: str = "full"  # "full" or "split"
    routes: List[RouteConfig] = []  # Custom routes for split tunnel
    dns_servers: List[str] = [] # Optional custom DNS servers

class FirewallPolicyRequest(BaseModel):
    default_policy: str

# --- Sicurezza con API Key ---
API_KEY = os.getenv("API_KEY", "change-this-in-production")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(key: str = Security(api_key_header)):
    if key == API_KEY:
        return key
    else:
        raise HTTPException(
            status_code=403,
            detail="Could not validate credentials",
        )

# --- Applicazione FastAPI ---
app = FastAPI(
    title="OpenVPN Management API",
    description="API per gestire istanze multiple di OpenVPN.",
    version="2.0.0",
)

# --- Middleware CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints Istanze ---

@app.get("/api/instances", dependencies=[Depends(get_api_key)])
async def get_instances():
    """Restituisce la lista di tutte le istanze OpenVPN con il conteggio dei client connessi."""
    instances = instance_manager.get_all_instances()
    for inst in instances:
        if inst.status == "running":
            connected = vpn_manager.get_connected_clients(inst.name)
            inst.connected_clients = len(connected)
        else:
            inst.connected_clients = 0
    return instances

@app.get("/api/instances/{instance_id}", dependencies=[Depends(get_api_key)])
async def get_instance(instance_id: str):
    """Restituisce i dettagli di una specifica istanza."""
    instance = instance_manager.get_instance_by_id(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance

@app.post("/api/instances", dependencies=[Depends(get_api_key)])
async def create_instance(request: InstanceRequest):
    """Crea una nuova istanza OpenVPN."""
    try:
        instance = instance_manager.create_instance(
            name=request.name,
            port=request.port,
            subnet=request.subnet,
            protocol=request.protocol,
            tunnel_mode=request.tunnel_mode,
            routes=[route.dict() for route in request.routes],
            dns_servers=request.dns_servers
        )
        return instance
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/instances/{instance_id}")
def delete_instance(instance_id: str, api_key: str = Depends(get_api_key)): # Changed verify_api_key to get_api_key for consistency
    try:
        instance_manager.delete_instance(instance_id)
        return {"success": True, "message": "Instance deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/instances/{instance_id}/routes")
def update_instance_routes(instance_id: str, request: RouteUpdateRequest, api_key: str = Depends(get_api_key)): # Changed verify_api_key to get_api_key for consistency
    try:
        updated_instance = instance_manager.update_instance_routes(
            instance_id=instance_id,
            tunnel_mode=request.tunnel_mode,
            routes=[route.dict() for route in request.routes],
            dns_servers=request.dns_servers
        )
        return updated_instance
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/instances/{instance_id}/firewall-policy", dependencies=[Depends(get_api_key)])
async def update_instance_firewall_policy_endpoint(instance_id: str, request: FirewallPolicyRequest):
    """Aggiorna la policy di default del firewall per una specifica istanza."""
    try:
        updated_instance = instance_manager.update_instance_firewall_policy(
            instance_id=instance_id,
            new_policy=request.default_policy
        )
        return updated_instance
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Statistiche ---

@app.get("/api/stats/top-clients", dependencies=[Depends(get_api_key)])
async def get_top_clients():
    """Restituisce i top 5 client per traffico totale (tutte le istanze)."""
    instances = instance_manager.get_all_instances()
    all_clients = []

    for inst in instances:
        if inst.status == "running":
            connected = vpn_manager.get_connected_clients(inst.name)
            for name, data in connected.items():
                # data keys: virtual_ip, real_ip, connected_since, bytes_received, bytes_sent
                try:
                    b_rx = int(data.get("bytes_received", 0))
                    b_tx = int(data.get("bytes_sent", 0))
                    total_bytes = b_rx + b_tx
                    
                    all_clients.append({
                        "client_name": name,
                        "instance_name": inst.name,
                        "total_bytes": total_bytes,
                        "bytes_received": b_rx,
                        "bytes_sent": b_tx,
                        "connected_since": data.get("connected_since", "-")
                    })
                except (ValueError, TypeError):
                    continue

    # Sort by total_bytes descending
    sorted_clients = sorted(all_clients, key=lambda x: x["total_bytes"], reverse=True)
    return sorted_clients[:5]

# --- Endpoints Network ---

@app.get("/api/network/interfaces", dependencies=[Depends(get_api_key)])
async def get_network_interfaces():
    """Restituisce la lista delle interfacce di rete disponibili."""
    try:
        interfaces = network_utils.get_network_interfaces()
        return interfaces
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Client (Scoped per Istanza) ---

@app.get("/api/instances/{instance_id}/clients", dependencies=[Depends(get_api_key)])
async def get_clients(instance_id: str):
    """Ottiene la lista dei client per una specifica istanza."""
    try:
        clients = vpn_manager.list_clients(instance_id)
        return clients
    except ValueError:
        raise HTTPException(status_code=404, detail="Instance not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instances/{instance_id}/clients", dependencies=[Depends(get_api_key)])
async def create_client(instance_id: str, request: ClientRequest):
    """Crea un nuovo client per una specifica istanza."""
    client_name = request.client_name
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, error = vpn_manager.create_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=error)

    return {"message": f"Client '{client_name}' creato con successo."}

@app.get("/api/instances/{instance_id}/clients/{client_name}/download", dependencies=[Depends(get_api_key)])
async def download_client_config(instance_id: str, client_name: str):
    """Scarica il file .ovpn per un client."""
    # Verifica esistenza istanza (opzionale, ma buona pratica)
    if not instance_manager.get_instance(instance_id):
        raise HTTPException(status_code=404, detail="Instance not found")

    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")
    
    config_content, error = vpn_manager.get_client_config(client_name)
    if error:
        raise HTTPException(status_code=404, detail=error)

    return PlainTextResponse(
        content=config_content,
        media_type="application/x-openvpn-profile",
        headers={"Content-Disposition": f"attachment; filename={client_name}.ovpn"}
    )

@app.delete("/api/instances/{instance_id}/clients/{client_name}", dependencies=[Depends(get_api_key)])
async def revoke_client(instance_id: str, client_name: str):
    """Revoca un client."""
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, message = vpn_manager.revoke_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


# --- Endpoints Gruppi e Firewall ---

@app.get("/api/groups", dependencies=[Depends(get_api_key)])
async def list_groups(instance_id: Optional[str] = None):
    return instance_firewall_manager.get_groups(instance_id)

@app.post("/api/groups", dependencies=[Depends(get_api_key)])
async def create_group(request: GroupRequest):
    try:
        return instance_firewall_manager.create_group(request.name, request.instance_id, request.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/groups/{group_id}", dependencies=[Depends(get_api_key)])
async def delete_group(group_id: str):
    instance_firewall_manager.delete_group(group_id)
    return {"success": True}

@app.post("/api/groups/{group_id}/members", dependencies=[Depends(get_api_key)])
async def add_group_member(group_id: str, request: GroupMemberRequest):
    try:
        instance_firewall_manager.add_member_to_group(group_id, request.client_identifier, request.subnet_info)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/groups/{group_id}/members/{client_identifier}", dependencies=[Depends(get_api_key)])
async def remove_group_member(group_id: str, client_identifier: str, instance_name: str):
    try:
        instance_firewall_manager.remove_member_from_group(group_id, client_identifier, instance_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall Rules ---

@app.get("/api/firewall/rules", dependencies=[Depends(get_api_key)])
async def list_rules(group_id: Optional[str] = None):
    return instance_firewall_manager.get_rules(group_id)

@app.post("/api/firewall/rules", dependencies=[Depends(get_api_key)])
async def create_rule(request: RuleRequest):
    try:
        return instance_firewall_manager.add_rule(request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/firewall/rules/{rule_id}", dependencies=[Depends(get_api_key)])
async def delete_rule(rule_id: str):
    instance_firewall_manager.delete_rule(rule_id)
    return {"success": True}

@app.post("/api/firewall/rules/order", dependencies=[Depends(get_api_key)])
async def reorder_rules(orders: List[RuleOrderRequest]):
    try:
        data = [{"id": x.id, "order": x.order} for x in orders]
        instance_firewall_manager.update_rule_order(data)
        return {"success": True}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall (Machine-level) ---

@app.get("/api/machine-firewall/rules", response_model=List[MachineFirewallRuleModel], dependencies=[Depends(get_api_key)])
async def list_machine_firewall_rules():
    """List all machine-level firewall rules."""
    try:
        all_rules = machine_firewall_manager.get_all_rules()
        return all_rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/machine-firewall/rules", response_model=MachineFirewallRuleModel, dependencies=[Depends(get_api_key)])
async def add_machine_firewall_rule_endpoint(rule_data: MachineFirewallRuleModel):
    """Add a new machine-level firewall rule."""
    try:
        new_rule = machine_firewall_manager.add_rule(rule_data.dict())
        return new_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/machine-firewall/rules/{rule_id}", response_model=MachineFirewallRuleModel, dependencies=[Depends(get_api_key)])
async def update_machine_firewall_rule_endpoint(rule_id: str, rule_data: MachineFirewallRuleModel):
    """Update a machine-level firewall rule."""
    try:
        updated_rule = machine_firewall_manager.update_rule(rule_id, rule_data.dict())
        return updated_rule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/machine-firewall/rules/{rule_id}", dependencies=[Depends(get_api_key)])
async def delete_machine_firewall_rule_endpoint(rule_id: str):
    """Delete a machine-level firewall rule."""
    try:
        machine_firewall_manager.delete_rule(rule_id)
        return {"success": True, "message": "Machine firewall rule deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/machine-firewall/rules/apply", dependencies=[Depends(get_api_key)])
async def apply_machine_firewall_rules_endpoint(rules_order: List[MachineFirewallRuleOrderRequest]):
    """Apply a new order or set of machine-level firewall rules."""
    try:
        rules_data = [{"id": r.id, "order": r.order} for r in rules_order]
        machine_firewall_manager.update_rule_order(rules_data) # This will reorder and apply
        return {"success": True, "message": "Machine firewall rules updated and applied."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Network Interface (Machine-level) ---

@app.get("/api/machine-network/interfaces", dependencies=[Depends(get_api_key)])
async def get_all_machine_network_interfaces():
    """Get all machine network interfaces with detailed information."""
    try:
        interfaces = network_utils.get_network_interfaces()
        return interfaces
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/machine-network/interfaces/{interface_name}/config", dependencies=[Depends(get_api_key)])
async def get_machine_network_interface_config(interface_name: str):
    """Get the current Netplan configuration for a specific interface."""
    try:
        netplan_files = network_utils.get_netplan_config_files()
        # For simplicity, we assume the config is in the first file, or we need to iterate
        # and find the config relevant to this interface.
        if not netplan_files:
            return {} # No netplan config files found
        
        # Read the first netplan file and extract config for the specific interface
        config_data = network_utils.read_netplan_config(netplan_files[0])
        if config_data and "network" in config_data and "ethernets" in config_data["network"]:
            return config_data["network"]["ethernets"].get(interface_name, {})
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/machine-network/interfaces/{interface_name}/config", dependencies=[Depends(get_api_key)])
async def update_machine_network_interface_config(interface_name: str, config_data: Dict):
    """Update the Netplan configuration for a specific interface and apply it."""
    try:
        # This endpoint will manage reading, updating, and writing the netplan config.
        # It's a critical operation that needs to be handled carefully.
        # For this iteration, we'll try to modify the first netplan file found.
        netplan_files = network_utils.get_netplan_config_files()
        
        # If no netplan file exists, create a new one with a default structure
        if not netplan_files:
            config_file_path = f"/etc/netplan/99-custom-{interface_name}.yaml"
            current_netplan_full_config = {"network": {"version": 2, "renderer": "networkd"}}
        else:
            config_file_path = netplan_files[0] # Pick the first one
            current_netplan_full_config = network_utils.read_netplan_config(config_file_path)
            if current_netplan_full_config is None: # handle empty or invalid YAML
                 current_netplan_full_config = {"network": {"version": 2, "renderer": "networkd"}}

        if "network" not in current_netplan_full_config:
            current_netplan_full_config["network"] = {"version": 2, "renderer": "networkd"}
        if "ethernets" not in current_netplan_full_config["network"]:
            current_netplan_full_config["network"]["ethernets"] = {}

        # Apply the new config_data for the specific interface
        current_netplan_full_config["network"]["ethernets"][interface_name] = config_data

        if not network_utils.write_netplan_config(config_file_path, current_netplan_full_config):
            raise HTTPException(status_code=500, detail="Failed to write Netplan config file.")
        
        success, error = network_utils.apply_netplan_config()
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to apply Netplan config: {error}")

        return {"success": True, "message": f"Netplan config for {interface_name} updated and applied."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating Netplan config: {e}")

@app.post("/api/machine-network/netplan-apply", dependencies=[Depends(get_api_key)])
async def apply_global_netplan_config():
    """Applies the current Netplan configuration globally."""
    try:
        success, error_msg = network_utils.apply_netplan_config()
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to apply Netplan config: {error_msg}")
        return {"success": True, "message": "Netplan configuration applied."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "OpenVPN Management API v2 is running."}

