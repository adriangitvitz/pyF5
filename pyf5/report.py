from typing import Any

from .base import F5Client


def pool_health(f5_client: F5Client) -> list[dict[str, Any]]:
    """One entry per virtual server with its default pool and member states."""
    pools = {p.full_path: p for p in f5_client.get_pools().items}
    data = []
    for vs in f5_client.get_virtual_servers().items:
        virtual_data: dict[str, Any] = {
            "name": vs.name,
            "creationTime": vs.creation_time,
            "destination": vs.destination.replace("/Common/", ""),
            "disabled": not vs.enabled,
            "source": vs.source,
            "sourceAddressTranslation": vs.sourceaddresstranslation.type,
            "pool": {},
        }
        pool = pools.get(vs.pool) if vs.pool else None
        if pool:
            virtual_data["pool"] = {
                "name": pool.name,
                "monitor": (pool.monitor or "").replace("/Common/", ""),
                "members": [
                    m.model_dump(
                        include={"name", "monitor", "address", "state", "session"}
                    )
                    for m in pool.members
                ],
            }
        data.append(virtual_data)
    return data


def summarize(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten pool_health output into one row per virtual server."""
    rows = []
    for entry in data:
        pool = entry["pool"]
        members = pool.get("members", [])
        total = len(members)
        up = len([m for m in members if m["state"] == "up"])
        rows.append(
            {
                **{k: v for k, v in entry.items() if k != "pool"},
                "pool_name": pool.get("name", ""),
                "pool_monitor": pool.get("monitor", ""),
                "total_members": total,
                "up_members": up,
                "down_members": total - up,
                "health_percentage": round(up / total * 100, 2) if total else 0,
                "member_addresses": "; ".join(m["address"] for m in members),
                "member_names": "; ".join(m["name"] for m in members),
            }
        )
    return rows
