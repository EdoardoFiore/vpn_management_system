import logging
import subprocess
from typing import List, Dict, Optional, Tuple
from sqlmodel import Session, select
import datetime

from database import engine
from models import Client, Instance
import ip_manager
import instance_manager
import wireguard_manager

logger = logging.getLogger(__name__)

def list_clients(instance_id: str) -> List[Dict]:
    with Session(engine) as session:
        inst = session.get(Instance, instance_id)
        if not inst: return []
        
        clients = session.exec(select(Client).where(Client.instance_id == instance_id)).all()
        
        # Get live status
        connected_data = get_connected_clients(inst.name)
        
        result = []
        for c in clients:
            c_dict = c.dict()
            if c.name in connected_data:
                stats = connected_data[c.name]
                c_dict["status"] = "connected"
                c_dict["bytes_received"] = stats["bytes_received"]
                c_dict["bytes_sent"] = stats["bytes_sent"]
                c_dict["latest_handshake"] = stats["connected_since"]
                c_dict["real_ip"] = stats["real_ip"]
            else:
                c_dict["status"] = "disconnected"
                c_dict["bytes_received"] = 0
                c_dict["bytes_sent"] = 0
                c_dict["latest_handshake"] = 0
                
            result.append(c_dict)
            
        return result

def get_connected_clients(instance_name: str) -> Dict:
    # ... (Same logic as before, parsing wg show, but mapping keys from DB)
    # instance_name here is likely the ID or Name. get_instance_by_id resolves it.
    inst = instance_manager.get_instance_by_id(instance_name)
    if not inst: return {}
    
    try:
        output = wireguard_manager.WireGuardManager._run_wg_command(['show', inst.interface, 'dump'])
        lines = output.splitlines()
        connected = {}
        
        # Load clients from DB for mapping
        with Session(engine) as session:
            db_clients = session.exec(select(Client).where(Client.instance_id == inst.id)).all()
            pubkey_to_name = {c.public_key: c.name for c in db_clients}
        
        import time
        now = int(time.time())

        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) >= 4:
                pub_key = parts[0]
                endpoint = parts[2]
                handshake = int(parts[4])
                
                # Active if handshake < 3 mins ago
                if (now - handshake) < 180 and handshake > 0:
                    name = pubkey_to_name.get(pub_key, "Unknown")
                    connected[name] = {
                        "allocated_ip": "lookup...", # WireGuard dump doesn't show internal IP easily here, peer does
                        "real_ip": endpoint.split(':')[0],
                        "bytes_received": int(parts[5]),
                        "bytes_sent": int(parts[6]),
                        "connected_since": handshake
                    }
                    
                    # Optimization: Get allocated IP from DB client object
                    # We can do this better by iterating clients instead of dump lines? No, dump is source of truth for activity.
                    # We skip IP lookup here for perf, frontend has it in static list.
        return connected
    except Exception:
        return {}

def create_client(instance_id: str, client_name: str) -> Tuple[bool, Optional[str]]:
    with Session(engine) as session:
        inst = session.get(Instance, instance_id)
        if not inst: return False, "Instance not found"
        
        if session.exec(select(Client).where(Client.instance_id == instance_id, Client.name == client_name)).first():
            return False, "Client name exists"

        # 1. Gen Keys
        priv, pub = wireguard_manager.WireGuardManager.generate_keypair()
        psk = wireguard_manager.WireGuardManager.generate_psk()

        # 2. IP Alloc
        ip = ip_manager.allocate_static_ip(instance_id, inst.subnet, client_name)
        if not ip: return False, "No IP available"

        # 3. DB Save
        new_client = Client(
            instance_id=instance_id,
            name=client_name,
            private_key=priv,
            public_key=pub,
            preshared_key=psk,
            allocated_ip=ip,
            created_at=datetime.datetime.utcnow()
        )
        session.add(new_client)
        session.commit()
        session.refresh(new_client)

        # 4. Update Server Config
        config_path = f"/etc/wireguard/{inst.interface}.conf"
        allowed_ips = f"{ip}/32"
        try:
            wireguard_manager.WireGuardManager.add_peer_to_interface_config(
                config_path, pub, psk, allowed_ips, comment=client_name
            )
            wireguard_manager.WireGuardManager.hot_reload_interface(inst.interface)
        except Exception as e:
            session.delete(new_client) # Rollback DB
            session.commit()
            return False, f"Config update failed: {e}"

        return True, None

def revoke_client(instance_id: str, client_name: str) -> Tuple[bool, str]:
    with Session(engine) as session:
        client = session.exec(select(Client).where(Client.instance_id == instance_id, Client.name == client_name)).first()
        if not client: return False, "Client not found"
        
        inst = session.get(Instance, instance_id)
        
        # 1. Update Server Config
        if inst:
            config_path = f"/etc/wireguard/{inst.interface}.conf"
            try:
                wireguard_manager.WireGuardManager.remove_peer_from_interface_config(config_path, client.public_key)
                wireguard_manager.WireGuardManager.hot_reload_interface(inst.interface)
            except Exception as e:
                logger.error(f"Failed to remove peer from config: {e}")
                # Continue to delete from DB anyway

        # 2. DB Delete
        session.delete(client)
        session.commit()
        
        return True, "Revoked"

def get_client_config(client_name: str, instance_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    with Session(engine) as session:
        client = None
        if instance_id:
            client = session.exec(select(Client).where(Client.instance_id == instance_id, Client.name == client_name)).first()
        else:
            # Search all
            client = session.exec(select(Client).where(Client.name == client_name)).first()
        
        if not client: return None, "Client not found"
        
        inst = session.get(Instance, client.instance_id)
        
        # Routing Logic
        allowed_ips = "0.0.0.0/0, ::/0"
        if inst.tunnel_mode == "split":
            routes = [inst.subnet]
            # inst.routes is a JSON list of dicts
            for r in inst.routes:
                if 'network' in r: routes.append(r['network'])
            allowed_ips = ", ".join(routes)

        dns_str = ", ".join(inst.dns_servers)
        
        # Public IP
        public_ip = "SERVER_IP"
        try:
            public_ip = subprocess.run(["curl", "-s", "https://ifconfig.me"], capture_output=True, text=True).stdout.strip()
        except: pass

        config = f"""
[Interface]
PrivateKey = {client.private_key}
Address = {client.allocated_ip}/32
DNS = {dns_str}

[Peer]
PublicKey = {inst.public_key}
PresharedKey = {client.preshared_key}
Endpoint = {public_ip}:{inst.port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
"""
        return config, None
