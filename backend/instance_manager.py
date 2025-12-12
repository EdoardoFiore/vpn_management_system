import os
import subprocess
import logging
import re
from ipaddress import ip_network, ip_address, AddressValueError
from typing import List, Optional, Dict
from sqlmodel import Session, select

from database import engine
from models import Instance
import wireguard_manager
import iptables_manager

logger = logging.getLogger(__name__)

WIREGUARD_CONFIG_DIR = "/etc/wireguard"

def _save_iptables_rules():
    save_script = "/opt/vpn-manager/scripts/save-iptables.sh"
    if os.path.exists(save_script):
        try:
            subprocess.run(["bash", save_script], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to save iptables rules: {e}")

def get_instance_by_id(instance_id: str) -> Optional[Instance]:
    with Session(engine) as session:
        return session.get(Instance, instance_id)

def get_all_instances() -> List[Instance]:
    with Session(engine) as session:
        instances = session.exec(select(Instance)).all()
        # Update status check (runtime check, not stored in DB permanently)
        for inst in instances:
            if _is_service_active(inst):
                inst.status = "running"
            else:
                inst.status = "stopped"
        return instances

def get_instance(instance_id: str) -> Optional[Instance]:
    return get_instance_by_id(instance_id)

def _get_service_name(instance: Instance) -> str:
    return f"wg-quick@{instance.interface}"

def _is_service_active(instance: Instance) -> bool:
    service_name = _get_service_name(instance)
    try:
        subprocess.run(["/usr/bin/systemctl", "is-active", "--quiet", service_name], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_instance(name: str, port: int, subnet: str, 
                   tunnel_mode: str = "full", routes: List[Dict[str, str]] = None, dns_servers: List[str] = None) -> Instance:
    
    logger.info(f"Creating instance: {name}, {port}, {subnet}")
    
    # 1. Validation
    name_regex = r"^[a-zA-Z0-9_]+$"
    if not re.fullmatch(name_regex, name):
        raise ValueError("Invalid name")

    try:
        new_subnet = ip_network(subnet, strict=False)
        if not new_subnet.is_private:
            raise ValueError("Subnet must be private")
    except ValueError:
         raise ValueError("Invalid subnet format")

    with Session(engine) as session:
        if session.exec(select(Instance).where(Instance.name == name)).first():
            raise ValueError(f"Instance '{name}' exists")
        if session.exec(select(Instance).where(Instance.port == port)).first():
            raise ValueError(f"Port {port} in use")
        
        # Subnet overlap check
        existing_instances = session.exec(select(Instance)).all()
        for inst in existing_instances:
            try:
                if new_subnet.overlaps(ip_network(inst.subnet, strict=False)):
                    raise ValueError(f"Subnet overlap with {inst.name}")
            except: continue

        # Interface Name
        used_interfaces = [inst.interface for inst in existing_instances]
        next_id = 0
        while f"wg{next_id}" in used_interfaces:
            next_id += 1
        interface_name = f"wg{next_id}"
        
        instance_id = name.lower().replace(" ", "_")
        
        if routes is None: routes = []
        if not dns_servers: dns_servers = ["8.8.8.8", "1.1.1.1"]

        # 2. Key Gen
        priv_key, pub_key = wireguard_manager.WireGuardManager.generate_keypair()

        new_instance = Instance(
            id=instance_id,
            name=name,
            port=port,
            subnet=subnet,
            interface=interface_name,
            private_key=priv_key,
            public_key=pub_key,
            tunnel_mode=tunnel_mode,
            routes=routes,
            dns_servers=dns_servers,
            status="stopped"
        )

        # 3. Config File
        server_ip = str(list(new_subnet.hosts())[0]) + "/" + str(new_subnet.prefixlen)
        config_content = wireguard_manager.WireGuardManager.create_interface_config(
            instance_name=interface_name,
            listen_port=port,
            private_key=priv_key,
            address=server_ip
        )
        
        config_path = os.path.join(WIREGUARD_CONFIG_DIR, f"{interface_name}.conf")
        os.makedirs(WIREGUARD_CONFIG_DIR, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config_content)
        os.chmod(config_path, 0o600)

        # 4. Service Start
        service_name = _get_service_name(new_instance)
        try:
            subprocess.run(["systemctl", "enable", service_name], check=True)
            subprocess.run(["systemctl", "start", service_name], check=True)
            new_instance.status = "running"
        except subprocess.CalledProcessError as e:
            try: os.remove(config_path) 
            except: pass
            raise RuntimeError(f"Service start failed: {e}")

        # 5. DB Save
        session.add(new_instance)
        session.commit()
        session.refresh(new_instance)

    # 6. Firewall
    iptables_manager.add_openvpn_rules(
        port=port,
        proto="udp",
        tun_interface=interface_name,
        subnet=subnet
    )
    
    try:
        import firewall_manager
        firewall_manager.apply_firewall_rules()
    except Exception as e:
        logger.error(f"Firewall update failed: {e}")

    return new_instance

def delete_instance(instance_id: str):
    with Session(engine) as session:
        inst = session.get(Instance, instance_id)
        if not inst:
            raise ValueError("Instance not found")

        # Stop Service
        service_name = _get_service_name(inst)
        subprocess.run(["systemctl", "stop", service_name], check=False)
        subprocess.run(["systemctl", "disable", service_name], check=False)

        # Remove Config
        config_path = os.path.join(WIREGUARD_CONFIG_DIR, f"{inst.interface}.conf")
        if os.path.exists(config_path):
            os.remove(config_path)

        # Remove Firewall
        iptables_manager.remove_openvpn_rules(inst.port, "udp", inst.interface, inst.subnet)
        _save_iptables_rules()

        # DB Delete
        session.delete(inst)
        session.commit()

def update_instance_routes(instance_id: str, tunnel_mode: str, routes: List[Dict[str, str]], dns_servers: List[str] = None) -> Instance:
    with Session(engine) as session:
        instance = session.get(Instance, instance_id)
        if not instance:
            raise ValueError("Instance not found")
        
        instance.tunnel_mode = tunnel_mode
        if tunnel_mode == "full":
            instance.routes = []
        else:
            instance.routes = routes # SQLModel handles JSON serialization
            # Security: Force DROP policy on Split Tunnel to strictly enforce allowed routes
            instance.firewall_default_policy = "DROP"

        if dns_servers is not None:
            # If empty list is provided, fallback to default (User request)
            if not dns_servers:
                instance.dns_servers = ["8.8.8.8", "1.1.1.1"]
            else:
                instance.dns_servers = dns_servers
        
        session.add(instance)
        session.commit()
        session.refresh(instance)
        
        try:
            import firewall_manager
            firewall_manager.apply_firewall_rules()
        except Exception as e:
            logger.error(f"Firewall update failed after route change: {e}")

        return instance

def update_instance_firewall_policy(instance_id: str, new_policy: str) -> Instance:
    if new_policy.upper() not in ["ACCEPT", "DROP"]:
        raise ValueError("Invalid policy")

    with Session(engine) as session:
        inst = session.get(Instance, instance_id)
        if not inst:
            raise ValueError("Instance not found")

        inst.firewall_default_policy = new_policy.upper()
        session.add(inst)
        session.commit()
        session.refresh(inst)
        
        import firewall_manager
        firewall_manager.apply_firewall_rules()
        return inst
