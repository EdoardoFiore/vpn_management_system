from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, JSON, Column
import uuid

# --- Models ---

class InstanceBase(SQLModel):
    name: str
    port: int = Field(unique=True)
    subnet: str
    interface: str = Field(unique=True)
    tunnel_mode: str = "full"
    routes: List[Dict] = Field(default=[], sa_column=Column(JSON))
    dns_servers: List[str] = Field(default=["1.1.1.1"], sa_column=Column(JSON))
    firewall_default_policy: str = "ACCEPT"
    status: str = "stopped"
    type: str = "wireguard"

class Instance(InstanceBase, table=True):
    id: str = Field(primary_key=True)
    private_key: str
    public_key: str
    
    # Relationships
    clients: List["Client"] = Relationship(back_populates="instance")
    groups: List["Group"] = Relationship(back_populates="instance")

class InstanceRead(InstanceBase):
    id: str
    public_key: str
    connected_clients: int = 0

class Client(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    instance_id: str = Field(foreign_key="instance.id")
    name: str
    private_key: str
    public_key: str
    preshared_key: str
    allocated_ip: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instance: Instance = Relationship(back_populates="clients")
    group_links: List["GroupMember"] = Relationship(back_populates="client")


class Group(SQLModel, table=True):
    id: str = Field(primary_key=True) # e.g. "amministrazione_devs"
    instance_id: str = Field(foreign_key="instance.id")
    name: str
    description: str = ""

    # Relationships
    instance: Instance = Relationship(back_populates="groups")
    client_links: List["GroupMember"] = Relationship(back_populates="group")
    rules: List["FirewallRule"] = Relationship(back_populates="group")

class GroupRead(SQLModel):
    id: str
    instance_id: str
    name: str
    description: str
    members: List[str] = []



class GroupMember(SQLModel, table=True):
    """Junction table for Many-to-Many between Groups and Clients"""
    group_id: str = Field(foreign_key="group.id", primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="client.id", primary_key=True)

    group: Group = Relationship(back_populates="client_links")
    client: Client = Relationship(back_populates="group_links")


class FirewallRule(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.id")
    action: str
    protocol: str
    port: Optional[str] = None
    destination: str
    description: str = ""
    order: int = 0

    group: Group = Relationship(back_populates="rules")


class MachineFirewallRule(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chain: str
    action: str
    protocol: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    port: Optional[str] = None
    in_interface: Optional[str] = None
    out_interface: Optional[str] = None
    state: Optional[str] = None
    comment: Optional[str] = None
    table_name: str = Field(default="filter", alias="table") # 'table' is reserved SQL keyword
    order: int = 0
