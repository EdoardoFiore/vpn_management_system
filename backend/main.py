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
from models import User, UserRole, UserInstance, Instance
import auth

# --- Pydantic Models for Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.VIEWER
    instance_ids: List[str] = []

class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    instance_ids: Optional[List[str]] = None

class UserResponse(BaseModel):
    username: str
    role: UserRole
    is_active: bool
    instance_ids: List[str] = []

# --- Pydantic Models for App ---
# --- Pydantic Models for App ---
class ClientRequest(BaseModel):
    client_name: str

class GroupMemberRequest(BaseModel):
    client_identifier: str # e.g. "instance_clientname"
    subnet_info: Dict[str, str]

class GroupRequest(BaseModel):
    name: str
    instance_id: str
    description: str = ""

class RouteConfig(BaseModel):
    network: str
    interface: str

class RouteUpdateRequest(BaseModel):
    tunnel_mode: str = "full"
    routes: List[RouteConfig] = []
    dns_servers: List[str] = []

class InstanceRequest(BaseModel):
    name: str
    port: int
    subnet: str
    tunnel_mode: str = "full"
    routes: List[RouteConfig] = []
    dns_servers: List[str] = []

class FirewallPolicyRequest(BaseModel):
    default_policy: str

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

from pydantic import BaseModel, Field, validator
import ipaddress

class MachineFirewallRuleModel(BaseModel):
    id: Optional[str] = None
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
    table_name: str = Field(default="filter", alias="table") 
    order: int = 0
    
    model_config = {
        "populate_by_name": True
    }

    @validator('action')
    def validate_action(cls, v):
        valid_actions = ["ACCEPT", "DROP", "REJECT", "MASQUERADE", "SNAT", "DNAT", "RETURN", "LOG"]
        if v.upper() not in valid_actions:
            raise ValueError(f"Invalid action: {v}. Must be one of {valid_actions}")
        return v.upper()

    @validator('protocol')
    def validate_protocol(cls, v):
        if not v: return None
        if v.lower() == "all": return "all"
        valid_protocols = ["tcp", "udp", "icmp", "esp", "ah", "gre", "igmp"] 
        if v.lower() not in valid_protocols:
            raise ValueError(f"Invalid protocol: {v}. Must be one of {valid_protocols} or 'all'")
        return v.lower()

    @validator('port')
    def validate_port(cls, v):
        if not v: return None
        v_str = str(v)
        if ":" in v_str:
            # Range check
            parts = v_str.split(":")
            if len(parts) != 2: raise ValueError("Invalid port range format (start:end)")
            try:
                p1, p2 = int(parts[0]), int(parts[1])
                if not (1 <= p1 <= 65535 and 1 <= p2 <= 65535): raise ValueError
            except ValueError:
                raise ValueError("Ports must be integers between 1 and 65535")
        else:
            try:
                p = int(v_str)
                if not (1 <= p <= 65535): raise ValueError
            except ValueError:
                raise ValueError("Port must be integer between 1 and 65535")
        return v_str

    @validator('source', 'destination')
    def validate_ip_network(cls, v):
        if not v or v.lower() == "any": return None
        try:
            # Check if it's a valid IP or CIDR
            ipaddress.ip_network(v, strict=False)
        except ValueError:
             # It might be a single IP, try ip_address
             try:
                 ipaddress.ip_address(v)
             except ValueError:
                 raise ValueError(f"Invalid IP address or CIDR: {v}")
        return v

    @validator('table_name')
    def validate_table(cls, v):
        valid_tables = ["filter", "nat", "mangle", "raw"]
        if v.lower() not in valid_tables:
            raise ValueError(f"Invalid table: {v}")
        return v.lower()
    
    @validator('chain')
    def validate_chain(cls, v, values):
        # We can try to validate chain based on table if table is already validated/present
        # note: 'table_name' might not be in values if it failed validation or hasn't run yet?
        # Pydantic validates in order of definition usually.
        # But for simplicity, let's just ensure it's uppercase.
        # Standard chains: INPUT, OUTPUT, FORWARD, PREROUTING, POSTROUTING
        # Custom chains allowed? The model is for Machine Firewall, usually standard chains.
        # Let's verify standard + custom just in case, but usually we restrict to standard for UI safety.
        # Given UI has dropdown, let's enforce standard chains per table if possible, OR just basic check.
        # Let's stick to upper() for now to avoid blocking custom usage if user manually posted.
        if not v: raise ValueError("Chain is required")
        return v.upper()

class MachineFirewallRuleOrderRequest(BaseModel):
    id: str
    order: int
    
# Regex per validare i nomi dei client (permette alfanumerici, underscore, trattini e punti)
CLIENT_NAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"

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
    # For 'me' endpoint, we might want to include instance_ids as well
    with Session(engine) as session:
        user_with_instances = session.get(User, current_user.username)
        if not user_with_instances:
            raise HTTPException(status_code=404, detail="User not found")
        
        instance_ids = [inst.id for inst in user_with_instances.assigned_instances]
        return UserResponse(
            username=user_with_instances.username,
            role=user_with_instances.role,
            is_active=user_with_instances.is_active,
            instance_ids=instance_ids
        )

@app.get("/api/users", response_model=List[UserResponse], dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.ADMIN_READ_ONLY]))])
async def read_users():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        response = []
        for user in users:
            # Eager load instance_ids logic via relationship or query
            # Since we defined relationship assigned_instances, we can access it
            instance_ids = [inst.id for inst in user.assigned_instances]
            response.append(UserResponse(
                username=user.username,
                role=user.role,
                is_active=user.is_active,
                instance_ids=instance_ids
            ))
        return response

@app.post("/api/users", response_model=UserResponse, dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def create_user(user: UserCreate):
    with Session(engine) as session:
        if session.get(User, user.username):
             raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = auth.get_password_hash(user.password)
        db_user = User(username=user.username, hashed_password=hashed_password, role=user.role)
        session.add(db_user)
        
        # If role is Technician or Viewer (Scoped) and instance_ids are provided
        assigned_ids = []
        if user.role in [UserRole.TECHNICIAN, UserRole.VIEWER] and user.instance_ids:
             # Verify instances exist
             from models import Instance
             for instance_id in user.instance_ids:
                 if not session.get(Instance, instance_id):
                      raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
                 
                 link = UserInstance(user_id=user.username, instance_id=instance_id)
                 session.add(link)
                 assigned_ids.append(instance_id)

        session.commit()
        session.refresh(db_user)
        
        # Construct response manually to include instance_ids
        return UserResponse(
            username=db_user.username,
            role=db_user.role,
            is_active=db_user.is_active,
            instance_ids=assigned_ids
        )

@app.patch("/api/users/{username}", response_model=UserResponse, dependencies=[Depends(auth.check_role([UserRole.ADMIN]))])
async def update_user(username: str, user_update: UserUpdate):
    with Session(engine) as session:
        db_user = session.get(User, username)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_update.dict(exclude_unset=True)
        instance_ids_to_update = None
        
        if "password" in user_data:
            password = user_data.pop("password")
            db_user.hashed_password = auth.get_password_hash(password)
            
        if "instance_ids" in user_data:
            instance_ids_to_update = user_data.pop("instance_ids")

        for key, value in user_data.items():
            setattr(db_user, key, value)
            
        session.add(db_user)
        
        # Handle Instance Assignments Update
        if instance_ids_to_update is not None:
            # 1. Remove existing links
            from sqlmodel import delete
            stmt = delete(UserInstance).where(UserInstance.user_id == username)
            session.exec(stmt)
            
            # 2. Add new links if role allows
            if db_user.role in [UserRole.TECHNICIAN, UserRole.VIEWER]:
                from models import Instance
                for i_id in instance_ids_to_update:
                     if session.get(Instance, i_id):
                        session.add(UserInstance(user_id=username, instance_id=i_id))

        session.commit()
        session.refresh(db_user)
        
        # Return updated response
        # Need to re-fetch assigned instances to be sure
        updated_instance_ids = [inst.id for inst in db_user.assigned_instances]
        return UserResponse(
            username=db_user.username,
            role=db_user.role,
            is_active=db_user.is_active,
            instance_ids=updated_instance_ids
        )

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
async def get_instances(current_user: User = Depends(auth.get_current_user)):
    """Restituisce la lista di tutte le istanze OpenVPN, filtrate per permessi."""
    
    # Logic: Admin, Partner, Admin ReadOnly -> ALL instances
    # Technician, Viewer -> Assigned instances only
    
    # Logic: Admin, Partner, Admin ReadOnly -> ALL instances
    # Technician, Viewer -> Assigned instances only
    
    instances = get_user_instances(current_user)
    
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
async def get_instance(instance_id: str, current_user: User = Depends(auth.get_current_user)):
    """Restituisce i dettagli di una specifica istanza."""
    
    # Check access
    if current_user.role not in [UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY]:
        user_instances = get_user_instances(current_user)
        if not any(inst.id == instance_id for inst in user_instances):
             raise HTTPException(status_code=403, detail="Access denied to this instance.")

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


def get_user_instances(user: User) -> List[Instance]:
    """Helper to get instances accessible by a specific user."""
    global_access_roles = [UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY]
    
    if user.role in global_access_roles:
        return instance_manager.get_all_instances()
    else:
        with Session(engine) as session:
            from models import UserInstance, Instance
            stmt = select(Instance).join(UserInstance).where(UserInstance.user_id == user.username)
            return session.exec(stmt).all()

@app.get("/api/stats/top-clients", dependencies=[Depends(auth.get_current_user)])
async def get_top_clients(current_user: User = Depends(auth.get_current_user)):
    """Restituisce i top 5 client per traffico totale (filtrati per permessi)."""
    
    # Use helper to get only accessible instances
    instances = get_user_instances(current_user)
    
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

@app.get("/api/instances/{instance_id}/clients", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY, UserRole.TECHNICIAN, UserRole.VIEWER]))])
async def get_clients(instance_id: str, current_user: User = Depends(auth.get_current_user)):
    """Ottiene la lista dei client per una specifica istanza."""
    
    # Check access for restricted roles
    if current_user.role not in [UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY]:
        user_instances = get_user_instances(current_user)
        # Check if the requested instance_id is one of the user's assigned instances
        if not any(inst.id == instance_id for inst in user_instances):
             raise HTTPException(status_code=403, detail="Access denied to this instance.")

    try:
        clients = vpn_manager.list_clients(instance_id)
        return clients
    except ValueError:
        raise HTTPException(status_code=404, detail="Instance not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instances/{instance_id}/clients", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def create_client(instance_id: str, request: ClientRequest, current_user: User = Depends(auth.get_current_user)):
    """Crea un nuovo client per una specifica istanza."""
    
    # Check access for Technician
    if current_user.role == UserRole.TECHNICIAN:
        user_instances = get_user_instances(current_user)
        if not any(inst.id == instance_id for inst in user_instances):
             raise HTTPException(status_code=403, detail="Access denied to this instance.")
    client_name = request.client_name
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, error = vpn_manager.create_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=error)

    return {"message": f"Client '{client_name}' creato con successo."}

@app.get("/api/instances/{instance_id}/clients/{client_name}/download", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def download_client_config(instance_id: str, client_name: str, current_user: User = Depends(auth.get_current_user)):
    """Scarica il file .conf per un client."""
    
    # Check access for Technician
    if current_user.role == UserRole.TECHNICIAN:
        user_instances = get_user_instances(current_user)
        if not any(inst.id == instance_id for inst in user_instances):
             raise HTTPException(status_code=403, detail="Access denied to this instance.")
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

@app.delete("/api/instances/{instance_id}/clients/{client_name}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def revoke_client(instance_id: str, client_name: str, current_user: User = Depends(auth.get_current_user)):
    """Revoca un client."""
    
    # Check access for Technician
    if current_user.role == UserRole.TECHNICIAN:
        user_instances = get_user_instances(current_user)
        if not any(inst.id == instance_id for inst in user_instances):
             raise HTTPException(status_code=403, detail="Access denied to this instance.")
    if not client_name or not re.fullmatch(CLIENT_NAME_PATTERN, client_name):
        raise HTTPException(status_code=400, detail="Nome client non valido.")

    success, message = vpn_manager.revoke_client(instance_id, client_name)
    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


# --- Endpoints Gruppi e Firewall ---

@app.get("/api/groups", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY, UserRole.TECHNICIAN]))])
async def list_groups(instance_id: Optional[str] = None):
    return instance_firewall_manager.get_groups(instance_id)

@app.post("/api/groups", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def create_group(request: GroupRequest):
    try:
        return instance_firewall_manager.create_group(request.name, request.instance_id, request.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/groups/{group_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def delete_group(group_id: str):
    instance_firewall_manager.delete_group(group_id)
    return {"success": True}

@app.post("/api/groups/{group_id}/members", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def add_group_member(group_id: str, request: GroupMemberRequest):
    try:
        instance_firewall_manager.add_member_to_group(group_id, request.client_identifier, request.subnet_info)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/groups/{group_id}/members/{client_identifier}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def remove_group_member(group_id: str, client_identifier: str, instance_name: str):
    try:
        instance_firewall_manager.remove_member_from_group(group_id, client_identifier, instance_name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall Rules ---

@app.get("/api/firewall/rules", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.ADMIN_READ_ONLY, UserRole.TECHNICIAN]))])
async def list_rules(group_id: Optional[str] = None):
    return instance_firewall_manager.get_rules(group_id)

@app.post("/api/firewall/rules", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def create_rule(request: RuleRequest):
    try:
        return instance_firewall_manager.add_rule(request.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/firewall/rules/{rule_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
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

@app.delete("/api/firewall/rules/{rule_id}", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def delete_rule(rule_id: str):
    instance_firewall_manager.delete_rule(rule_id)
    return {"success": True}

@app.post("/api/firewall/rules/order", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.PARTNER, UserRole.TECHNICIAN]))])
async def reorder_rules(orders: List[RuleOrderRequest]):
    try:
        data = [{"id": x.id, "order": x.order} for x in orders]
        instance_firewall_manager.update_rule_order(data)
        return {"success": True}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

# --- Endpoints Firewall (Machine-level) ---

@app.get("/api/machine-firewall/rules", response_model=List[MachineFirewallRuleModel], dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.ADMIN_READ_ONLY]))])
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

@app.get("/api/machine-network/interfaces", dependencies=[Depends(auth.check_role([UserRole.ADMIN, UserRole.ADMIN_READ_ONLY]))])
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