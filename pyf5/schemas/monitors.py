# ruff: noqa: FA100
from typing import Optional

from pydantic import BaseModel, Field


class Monitor(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    defaults_from: Optional[str] = Field(None, alias="defaultsFrom")
    send: Optional[str] = None
    recv: Optional[str] = None
    recv_disable: Optional[str] = Field(None, alias="recvDisable")
    interval: Optional[int] = None
    timeout: Optional[int] = None
    destination: Optional[str] = None


class Monitors(BaseModel):
    items: list[Monitor] = Field(default_factory=list)
