"""Certificate inventory: expiration -> SSL profiles that use it -> virtual servers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .base import F5Client
from .schemas.ssl import Certificates, SslProfiles
from .schemas.virtual_servers import VirtualServers

SSL_PROFILE_TYPES = ("client-ssl", "server-ssl")


def build_inventory(
    certificates: Certificates,
    profiles: dict[str, SslProfiles],
    virtual_servers: VirtualServers,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)

    vs_by_profile = defaultdict(list)
    for vs in virtual_servers.items:
        for ref in vs.profilesreference.items or []:
            if ref.full_path:
                vs_by_profile[ref.full_path].append(
                    {
                        "name": vs.name,
                        "partition": vs.partition,
                        "destination": vs.destination.split("/")[-1],
                        "enabled": vs.enabled,
                        "context": ref.context,
                    }
                )

    profiles_by_cert = defaultdict(list)
    for profile_type, profile_list in profiles.items():
        for profile in profile_list.items:
            for cert_path, roles in profile.cert_references().items():
                profiles_by_cert[cert_path].append(
                    {
                        "name": profile.full_path,
                        "type": profile_type,
                        "roles": sorted(roles),
                        "virtual_servers": vs_by_profile.get(profile.full_path, []),
                    }
                )

    inventory = []
    for cert in certificates.items:
        expires_at = cert.expires_at
        inventory.append(
            {
                "name": cert.full_path,
                "subject": cert.subject,
                "issuer": cert.issuer,
                "san": cert.subject_alternative_name,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "days_left": (expires_at - now).days if expires_at else None,
                "profiles": profiles_by_cert.get(cert.full_path, []),
            }
        )
    inventory.sort(key=lambda c: (c["days_left"] is None, c["days_left"]))
    return inventory


def filter_inventory(
    inventory: list[dict[str, Any]],
    days: int | None = None,
    name: str | None = None,
    in_use: bool = False,
) -> list[dict[str, Any]]:
    result = inventory
    if days is not None:
        result = [
            c for c in result if c["days_left"] is not None and c["days_left"] <= days
        ]
    if name:
        needle = name.lower()
        result = [
            c
            for c in result
            if needle in c["name"].lower() or needle in (c["subject"] or "").lower()
        ]
    if in_use:
        result = [c for c in result if any(p["virtual_servers"] for p in c["profiles"])]
    return result


def flatten(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per certificate -> profile -> virtual server."""
    rows = []
    for cert in inventory:
        base = {
            "certificate": cert["name"],
            "expires_at": cert["expires_at"],
            "days_left": cert["days_left"],
            "subject": cert["subject"],
        }
        empty = {
            "profile": "",
            "profile_type": "",
            "roles": "",
            "virtual_server": "",
            "destination": "",
            "vs_enabled": "",
        }
        if not cert["profiles"]:
            rows.append({**base, **empty})
        for profile in cert["profiles"]:
            profile_cols = {
                "profile": profile["name"],
                "profile_type": profile["type"],
                "roles": ";".join(profile["roles"]),
            }
            if not profile["virtual_servers"]:
                rows.append({**base, **empty, **profile_cols})
            for vs in profile["virtual_servers"]:
                rows.append(
                    {
                        **base,
                        **profile_cols,
                        "virtual_server": f"/{vs['partition']}/{vs['name']}",
                        "destination": vs["destination"],
                        "vs_enabled": vs["enabled"],
                    }
                )
    return rows


def retrieve_inventory(f5_client: F5Client) -> list[dict[str, Any]]:
    certificates = f5_client.get_certificates()
    profiles = {t: f5_client.get_ssl_profiles(t) for t in SSL_PROFILE_TYPES}
    virtual_servers = f5_client.get_virtual_servers()
    return build_inventory(certificates, profiles, virtual_servers)
