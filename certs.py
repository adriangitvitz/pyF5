"""Certificate inventory: expiration -> SSL profiles that use it -> virtual servers."""

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from client.base import F5Client
from client.credentials import keychain_credentials
from client.ratelimit import RateLimitConfig
from client.schemas.ssl import Certificates, SslProfiles
from client.schemas.virtual_servers import VirtualServers

SSL_PROFILE_TYPES = ("client-ssl", "server-ssl")


def build_inventory(
    certificates: Certificates,
    profiles: Dict[str, SslProfiles],
    virtual_servers: VirtualServers,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
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
    inventory: List[Dict[str, Any]],
    days: Optional[int] = None,
    name: Optional[str] = None,
    in_use: bool = False,
) -> List[Dict[str, Any]]:
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


def flatten(inventory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def retrieve_inventory(f5_client: F5Client) -> List[Dict[str, Any]]:
    certificates = f5_client.get_certificates()
    profiles = {t: f5_client.get_ssl_profiles(t) for t in SSL_PROFILE_TYPES}
    virtual_servers = f5_client.get_virtual_servers()
    return build_inventory(certificates, profiles, virtual_servers)


def print_report(inventory: List[Dict[str, Any]]):
    for cert in inventory:
        days = "?" if cert["days_left"] is None else cert["days_left"]
        print(f"{days:>6}d  {cert['expires_at'] or '-':<25}  {cert['name']}")
        if not cert["profiles"]:
            print("          (sin perfiles asociados)")
        for profile in cert["profiles"]:
            print(
                f"          {profile['type']:<10} {profile['name']}  [{','.join(profile['roles'])}]"
            )
            if not profile["virtual_servers"]:
                print("              (sin VS asociados)")
            for vs in profile["virtual_servers"]:
                state = "enabled" if vs["enabled"] else "disabled"
                print(
                    f"              VS /{vs['partition']}/{vs['name']}  {vs['destination']}  {state}"
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        required=True,
        help="Ambiente: busca el item pyf5.<env> en el Keychain y nombra los archivos de salida",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Solo certificados que vencen en N días o menos (incluye vencidos)",
    )
    parser.add_argument(
        "--name", help="Filtra por nombre o subject del certificado (substring)"
    )
    parser.add_argument(
        "--in-use", action="store_true", help="Solo certificados que llegan a algún VS"
    )
    args = parser.parse_args()

    host, username, password = keychain_credentials(args.env)
    f5_client = F5Client(
        host=host,
        username=username,
        password=password,
        rate_limit_config=RateLimitConfig(
            requests_per_second=5.0, burst_capacity=10, cooldown_period=2.0
        ),
        timeout=30,
        max_retries=3,
    )
    inventory = filter_inventory(
        retrieve_inventory(f5_client), args.days, args.name, args.in_use
    )

    os.makedirs("certs", exist_ok=True)
    with open(f"certs/{args.env}_certificates.json", "w") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    rows = flatten(inventory)
    if rows:
        with open(f"certs/{args.env}_certificates.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print_report(inventory)


if __name__ == "__main__":
    main()
