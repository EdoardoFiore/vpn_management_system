import os
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import vpn_manager
import re

# Regex per validare i nomi dei client (permette alfanumerici, underscore, trattini e punti)
CLIENT_NAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"

# --- Modello per la richiesta di creazione client ---
class ClientRequest(BaseModel):
    client_name: str

# --- Sicurezza con API Key ---
API_KEY = os.getenv("API_KEY", "change-this-in-production") # Cambiare questa chiave!
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
    description="API per gestire client OpenVPN.",
    version="1.0.0",
)

# --- Middleware CORS ---
# Permetti tutte le origini per semplicità. In produzione, dovresti limitarlo.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoint dell'API ---

@app.get("/api/clients", dependencies=[Depends(get_api_key)])
async def get_clients():
    """
    Ottiene la lista di tutti i client configurati e il loro stato (connesso/disconnesso).
    """
    try:
        clients = vpn_manager.list_clients()
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clients", dependencies=[Depends(get_api_key)])
async def create_new_client(request: ClientRequest):
    """
    Crea un nuovo client OpenVPN.
    Restituisce il file di configurazione .ovpn come testo.
    """
    client_name = request.client_name
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Il nome del client non è valido. Usare solo caratteri alfanumerici.")

    config_content, error = vpn_manager.create_client(client_name)

    if error:
        raise HTTPException(status_code=500, detail=error)

    return {"message": f"Client '{client_name}' creato con successo. Puoi scaricare il file .ovpn usando l'endpoint di download."}

@app.get("/api/clients/{client_name}/download", dependencies=[Depends(get_api_key)])
async def download_client_config(client_name: str):
    """
    Scarica il file di configurazione .ovpn per un client esistente.
    """
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Il nome del client non è valido.")
    
    config_content, error = vpn_manager.get_client_config(client_name)

    if error:
        raise HTTPException(status_code=404, detail=error) # 404 if file not found

    return PlainTextResponse(
        content=config_content,
        media_type="application/x-openvpn-profile",
        headers={"Content-Disposition": f"attachment; filename={client_name}.ovpn"}
    )

@app.delete("/api/clients/{client_name}", dependencies=[Depends(get_api_key)])
async def revoke_existing_client(client_name: str):
    """
    Revoca un client OpenVPN esistente.
    """
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Il nome del client non è valido.")

    success, message = vpn_manager.revoke_client(client_name)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}

@app.get("/")
async def root():
    return {"message": "OpenVPN Management API is running."}

