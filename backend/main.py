import os
import re
from typing import List, Optional, Dict, Union
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Security, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlmodel import Session, select

import vpn_manager
import instance_manager
import network_utils
import firewall_manager as instance_firewall_manager
import iptables_manager
from machine_firewall_manager import machine_firewall_manager
from database import create_db_and_tables, engine
from models import User, UserRole, UserInstance
import auth

# --- Pydantic Models for Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.VIEWER

class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    username: str
    role: UserRole
    is_active: bool

# --- Pydantic Models for App ---
# (Existing models kept, but shifted down in file usually, preserving here)

# --- App Init ---
app = FastAPI(
    title="VPN Manager API",
    description="WireGuard VPN Management with RBAC.",
    version="3.0.0",
)

# --- Auth Endpoints ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.get(User, form_data.username)
        if not user or not auth.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user.username, "role": user.role},
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(auth.get_current_user)):
    return current_user

@app.get("/api/users", response_model=List[UserResponse], dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def read_users():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        return users

@app.post("/api/users", response_model=UserResponse, dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def create_user(user: UserCreate):
    with Session(engine) as session:
        if session.get(User, user.username):
             raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = auth.get_password_hash(user.password)
        db_user = User(username=user.username, hashed_password=hashed_password, role=user.role)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user

@app.delete("/api/users/{username}", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def delete_user(username: str):
    with Session(engine) as session:
        user = session.get(User, username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        session.commit()
        return {"success": True}


@app.on_event("startup")
async def startup_event():
    """
    Initialize system components on startup.
    - Setup DB.
    - Setup IP tables chains and rules.
    """
    # Create DB tables
    create_db_and_tables()

    # Seed Default Admin if no users exist
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            print("Startup: No users found. Creating default 'admin' user.")
            admin_user = User(
                username="admin", 
                hashed_password=auth.get_password_hash("admin"),
                role=UserRole.ADMIN
            )
            session.add(admin_user)
            session.commit()
    
    # Verify/Execute OpenVPN rules application
    try:
        iptables_manager.apply_all_openvpn_rules()
        print("Startup: OpenVPN firewall rules applied.")
    except Exception as e:
        print(f"Startup Error: Failed to apply OpenVPN rules: {e}")
        
    # Re-apply Machine Firewall rules to ensure they are placed correctly (after VPN rules)
    try:
        machine_firewall_manager.apply_all_rules()
        print("Startup: Machine firewall rules applied.")
    except Exception as e:
        print(f"Startup Error: Failed to apply Machine firewall rules: {e}")

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

@app.get("/api/instances", dependencies=[Depends(auth.get_current_user)])
async def get_instances():
    """Restituisce la lista di tutte le istanze OpenVPN con il conteggio dei client connessi."""
    instances = instance_manager.get_all_instances()
    response_data = []
    for inst in instances:
        # Convert to dict to append extra fields not in DB model
        inst_dict = inst.dict()
        if inst.status == "running":
            connected = vpn_manager.get_connected_clients(inst.name)
            inst_dict["connected_clients"] = len(connected)
        else:
            inst_dict["connected_clients"] = 0
        response_data.append(inst_dict)
    return response_data

@app.get("/api/instances/{instance_id}", dependencies=[Depends(auth.get_current_user)])
async def get_instance(instance_id: str):
    """Restituisce i dettagli di una specifica istanza."""
    instance = instance_manager.get_instance_by_id(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance

@app.post("/api/instances", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER]))])
async def create_instance(request: InstanceRequest):
    """Crea una nuova istanza OpenVPN."""
    try:
        instance = instance_manager.create_instance(
            name=request.name,
            port=request.port,
            subnet=request.subnet,
            # protocol=request.protocol, # WireGuard is always UDP
            tunnel_mode=request.tunnel_mode,
            routes=[route.dict() for route in request.routes],
            dns_servers=request.dns_servers
        )
        return instance
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error creating instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/instances/{instance_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER]))])
def delete_instance(instance_id: str):
    try:
        instance_manager.delete_instance(instance_id)
        return {"success": True, "message": "Instance deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/instances/{instance_id}/routes", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER]))])
def update_instance_routes(instance_id: str, request: RouteUpdateRequest):
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

@app.patch("/api/instances/{instance_id}/firewall-policy", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER]))])
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

@app.get("/api/stats/top-clients", dependencies=[Depends(auth.get_current_user)])
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

@app.get("/api/network/interfaces", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def get_network_interfaces():
    """Restituisce la lista delle interfacce di rete disponibili."""
    try:
        interfaces = network_utils.get_network_interfaces()
        return interfaces
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Client (Scoped per Istanza) ---

@app.get("/api/instances/{instance_id}/clients", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def get_clients(instance_id: str):
    """Ottiene la lista dei client per una specifica istanza."""
    try:
        clients = vpn_manager.list_clients(instance_id)
        return clients
    except ValueError:
        raise HTTPException(status_code=404, detail="Instance not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instances/{instance_id}/clients", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def create_client(instance_id: str, request: ClientRequest):
    """Crea un nuovo client per una specifica istanza."""
    client_name = request.client_name
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, error = vpn_manager.create_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=error)

    return {"message": f"Client '{client_name}' creato con successo."}

@app.get("/api/instances/{instance_id}/clients/{client_name}/download", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def download_client_config(instance_id: str, client_name: str):
    """Scarica il file .ovpn per un client."""
    # Verifica esistenza istanza (opzionale, ma buona pratica)
    if not instance_manager.get_instance(instance_id):
        raise HTTPException(status_code=404, detail="Instance not found")

    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")
    
    config_content, error = vpn_manager.get_client_config(client_name, instance_id)
    if error:
        raise HTTPException(status_code=404, detail=error)

    return PlainTextResponse(
        content=config_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={client_name}.conf"}
    )

@app.delete("/api/instances/{instance_id}/clients/{client_name}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def revoke_client(instance_id: str, client_name: str):
    """Revoca un client."""
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, message = vpn_manager.revoke_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


# --- Endpoints Gruppi e Firewall ---

@app.get("/api/groups", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def list_groups(instance_id: Optional[str] = None):
    return instance_firewall_manager.get_groups(instance_id)

@app.post("/api/groups", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def create_group(request: GroupRequest):
    try:
        return instance_firewall_manager.create_group(request.name, request.instance_id, request.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/groups/{group_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def delete_group(group_id: str):
    instance_firewall_manager.delete_group(group_id)
    return {"success": True}

@app.post("/api/groups/{group_id}/members", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def add_group_member(group_id: str, request: GroupMemberRequest):
    try:
        instance_firewall_manager.add_member_to_group(group_id, request.client_identifier, request.subnet_info)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/groups/{group_id}/members/{client_identifier}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def remove_group_member(group_id: str, client_identifier: str, instance_name: str):
    try:
        instance_firewall_manager.remove_member_from_group(group_id, client_identifier, instance_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall Rules ---

@app.get("/api/firewall/rules", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def list_rules(group_id: Optional[str] = None):
    return instance_firewall_manager.get_rules(group_id)

@app.post("/api/firewall/rules", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def create_rule(request: RuleRequest):
    try:
        return instance_firewall_manager.add_rule(request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/firewall/rules/{rule_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def update_rule(rule_id: str, request: RuleRequest):
    try:
        # Note: The group_id is part of the request model, but we also pass rule_id from path
        updated_rule = instance_firewall_manager.update_rule(
            rule_id=rule_id,
            group_id=request.group_id, # Must be provided in the request body
            action=request.action,
            protocol=request.protocol,
            destination=request.destination,
            port=request.port,
            description=request.description
        )
        return updated_rule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/firewall/rules/{rule_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def delete_rule(rule_id: str):
    instance_firewall_manager.delete_rule(rule_id)
    return {"success": True}

@app.post("/api/firewall/rules/order", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.OPERATOR]))])
async def reorder_rules(orders: List[RuleOrderRequest]):
    try:
        data = [{"id": x.id, "order": x.order} for x in orders]
        instance_firewall_manager.update_rule_order(data)
        return {"success": True}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall (Machine-level) ---

@app.get("/api/machine-firewall/rules", response_model=List[MachineFirewallRuleModel], dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def list_machine_firewall_rules():
    """List all machine-level firewall rules."""
    try:
        all_rules = machine_firewall_manager.get_all_rules()
        return all_rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/machine-firewall/rules", response_model=MachineFirewallRuleModel, dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def add_machine_firewall_rule_endpoint(rule_data: MachineFirewallRuleModel):
    """Add a new machine-level firewall rule."""
    try:
        new_rule = machine_firewall_manager.add_rule(rule_data.dict())
        return new_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/machine-firewall/rules/{rule_id}", response_model=MachineFirewallRuleModel, dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def update_machine_firewall_rule_endpoint(rule_id: str, rule_data: MachineFirewallRuleModel):
    """Update a machine-level firewall rule."""
    try:
        updated_rule = machine_firewall_manager.update_rule(rule_id, rule_data.dict())
        return updated_rule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/machine-firewall/rules/{rule_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def delete_machine_firewall_rule_endpoint(rule_id: str):
    """Delete a machine-level firewall rule."""
    try:
        machine_firewall_manager.delete_rule(rule_id)
        return {"success": True, "message": "Machine firewall rule deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/machine-firewall/rules/apply", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def apply_machine_firewall_rules_endpoint(rules_order: List[MachineFirewallRuleOrderRequest]):
    """Apply a new order or set of machine-level firewall rules."""
    try:
        rules_data = [{"id": r.id, "order": r.order} for r in rules_order]
        machine_firewall_manager.update_rule_order(rules_data) # This will reorder and apply
        return {"success": True, "message": "Machine firewall rules updated and applied."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Network Interface (Machine-level) ---

@app.get("/api/machine-network/interfaces", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def get_all_machine_network_interfaces():
    """Get all machine network interfaces with detailed information."""
    try:
        interfaces = network_utils.get_network_interfaces()
        return interfaces
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/machine-network/interfaces/{interface_name}/config", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
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

@app.post("/api/machine-network/interfaces/{interface_name}/config", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
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

@app.post("/api/machine-network/netplan-apply", dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
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