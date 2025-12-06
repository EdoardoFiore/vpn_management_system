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
    """Restituisce la lista di tutte le istanze OpenVPN."""
    return instance_manager.get_all_instances()

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

@app.get("/")
async def root():
    return {"message": "OpenVPN Management API v2 is running."}


