# ruff: noqa: FA100
from typing import Optional

from pydantic import BaseModel, Field


class Device(BaseModel):
    name: str
    hostname: Optional[str] = None
    failover_state: Optional[str] = Field(None, alias="failoverState")
    self_device: Optional[str] = Field(None, alias="selfDevice")
    version: Optional[str] = None
    management_ip: Optional[str] = Field(None, alias="managementIp")

    @property
    def is_self(self) -> bool:
        return self.self_device == "true"


class Devices(BaseModel):
    items: list[Device] = Field(default_factory=list)

    @property
    def current(self) -> Optional[Device]:
        """The device answering the API (selfDevice == "true")."""
        return next((d for d in self.items if d.is_self), None)
