from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field


class Certificate(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    expiration_date: Optional[int] = Field(None, alias="expirationDate")
    expiration_string: Optional[str] = Field(None, alias="expirationString")
    subject: Optional[str] = None
    issuer: Optional[str] = None
    subject_alternative_name: Optional[str] = Field(
        None, alias="subjectAlternativeName"
    )
    is_bundle: Optional[str] = Field(None, alias="isBundle")

    @property
    def expires_at(self) -> Optional[datetime]:
        if self.expiration_date is None:
            return None
        return datetime.fromtimestamp(self.expiration_date, tz=timezone.utc)


class Certificates(BaseModel):
    items: List[Certificate] = Field(default_factory=list)


class CertKeyChain(BaseModel):
    name: Optional[str] = None
    cert: Optional[str] = None
    chain: Optional[str] = None


class SslProfile(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    cert: Optional[str] = None
    chain: Optional[str] = None
    ca_file: Optional[str] = Field(None, alias="caFile")
    cert_key_chain: List[CertKeyChain] = Field(
        default_factory=list, alias="certKeyChain"
    )

    def cert_references(self) -> Dict[str, Set[str]]:
        """Map each referenced certificate full path to the roles it plays."""
        candidates = [
            ("cert", self.cert),
            ("chain", self.chain),
            ("caFile", self.ca_file),
        ]
        for ckc in self.cert_key_chain:
            candidates += [("cert", ckc.cert), ("chain", ckc.chain)]

        refs: Dict[str, Set[str]] = {}
        for role, path in candidates:
            if path and path != "none":
                refs.setdefault(path, set()).add(role)
        return refs


class SslProfiles(BaseModel):
    items: List[SslProfile] = Field(default_factory=list)
