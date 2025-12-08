import os
import re
from typing import List
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import vpn_manager
import instance_manager
import network_utils
import firewall_manager
from typing import Optional, Dict

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
    return firewall_manager.get_groups(instance_id)

@app.post("/api/groups", dependencies=[Depends(get_api_key)])
async def create_group(request: GroupRequest):
    try:
        return firewall_manager.create_group(request.name, request.instance_id, request.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/groups/{group_id}", dependencies=[Depends(get_api_key)])
async def delete_group(group_id: str):
    firewall_manager.delete_group(group_id)
    return {"success": True}

@app.post("/api/groups/{group_id}/members", dependencies=[Depends(get_api_key)])
async def add_group_member(group_id: str, request: GroupMemberRequest):
    try:
        firewall_manager.add_member_to_group(group_id, request.client_identifier, request.subnet_info)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/groups/{group_id}/members/{client_identifier}", dependencies=[Depends(get_api_key)])
async def remove_group_member(group_id: str, client_identifier: str, instance_name: str):
    try:
        firewall_manager.remove_member_from_group(group_id, client_identifier, instance_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall Rules ---

@app.get("/api/firewall/rules", dependencies=[Depends(get_api_key)])
async def list_rules(group_id: Optional[str] = None):
    return firewall_manager.get_rules(group_id)

@app.post("/api/firewall/rules", dependencies=[Depends(get_api_key)])
async def create_rule(request: RuleRequest):
    try:
        return firewall_manager.add_rule(request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/firewall/rules/{rule_id}", dependencies=[Depends(get_api_key)])
async def delete_rule(rule_id: str):
    firewall_manager.delete_rule(rule_id)
    return {"success": True}

@app.post("/api/firewall/rules/order", dependencies=[Depends(get_api_key)])
async def reorder_rules(orders: List[RuleOrderRequest]):
    try:
        data = [{"id": x.id, "order": x.order} for x in orders]
        firewall_manager.update_rule_order(data)
        return {"success": True}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "OpenVPN Management API v2 is running."}


