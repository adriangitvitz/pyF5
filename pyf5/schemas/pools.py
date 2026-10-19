# ruff: noqa: FA100
from typing import Optional

from pydantic import BaseModel, Field


class PoolMember(BaseModel):
    name: str
    full_path: Optional[str] = Field(None, alias="fullPath")
    address: Optional[str] = None
    state: Optional[str] = None
    session: Optional[str] = None
    monitor: Optional[str] = None

    @property
    def node(self) -> str:
        """Node name without the port: "SA_Linux_113.12_Node:443" -> "SA_Linux_113.12_Node"."""
        return self.name.rsplit(":", 1)[0]


class MembersReference(BaseModel):
    items: list[PoolMember] = Field(default_factory=list)


class Pool(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    partition: str
    monitor: Optional[str] = None
    load_balancing_mode: Optional[str] = Field(None, alias="loadBalancingMode")
    members_reference: MembersReference = Field(
        default_factory=MembersReference, alias="membersReference"
    )

    @property
    def members(self) -> list[PoolMember]:
        return self.members_reference.items


class Pools(BaseModel):
    items: list[Pool] = Field(default_factory=list)


class Node(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    address: Optional[str] = None
    state: Optional[str] = None
    session: Optional[str] = None
    monitor: Optional[str] = None


class Nodes(BaseModel):
    items: list[Node] = Field(default_factory=list)
