from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceAddressTranslation(BaseModel):
    model_config = ConfigDict(strict=True)

    type: str


class ProfileReference(BaseModel):
    context: Optional[str] = None
    full_path: Optional[str] = Field(None, alias="fullPath")
    name: Optional[str] = None
    partition: Optional[str] = None
    kind: Optional[str] = None
    self_link: Optional[str] = Field(None, alias="selfLink")


class ProfileReferences(BaseModel):
    link: Optional[str] = None
    is_subcollection: bool = Field(alias="isSubcollection")
    items: Optional[List[ProfileReference]] = None


class VirtualServer(BaseModel):
    model_config = ConfigDict(strict=True)

    enabled: bool = False
    name: str
    destination: str
    source: str
    transport: str = Field(alias="ipProtocol")
    partition: str
    pool: Optional[str] = None
    rules: list[str] = Field(default_factory=list)
    sourceaddresstranslation: SourceAddressTranslation = Field(
        alias="sourceAddressTranslation"
    )
    profilesreference: ProfileReferences = Field(alias="profilesReference")
    creation_time: Optional[str] = Field(None, alias="creationTime")


class VirtualServers(BaseModel):
    model_config = ConfigDict(strict=True)
    items: List[VirtualServer]
