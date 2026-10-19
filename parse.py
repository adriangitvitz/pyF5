import argparse
import csv
import json

from client.base import F5Client
from client.credentials import keychain_credentials
from client.ratelimit import RateLimitConfig

rate_config = RateLimitConfig(
    requests_per_second=5.0, burst_capacity=10, cooldown_period=2.0
)


def retrieve_data(f5_client: F5Client, environment):
    pools = {p.full_path: p for p in f5_client.get_pools().items}
    data = []

    for vs in f5_client.get_virtual_servers().items:
        virtual_data = {
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
                    m.model_dump(include={"name", "monitor", "address", "state", "session"})
                    for m in pool.members
                ],
            }
        data.append(virtual_data)
    with open(f"{environment}_output.json", "w") as f:
        json.dump(data, f, indent=4)


def summary_csv(json_file: str, csv_file: str):
    with open(json_file, "r") as f:
        data = json.load(f)

    rows = []
    for entry in data:
        vs_info = {k: v for k, v in entry.items() if k != "pool"}
        pool = entry["pool"]

        members = pool.get("members", [])
        member_count = len(members)
        up_members = len([m for m in members if m["state"] == "up"])
        down_members = member_count - up_members

        row = vs_info.copy()
        row.update(
            {
                "pool_name": pool.get("name", ""),
                "pool_monitor": pool.get("monitor", ""),
                "total_members": member_count,
                "up_members": up_members,
                "down_members": down_members,
                "health_percentage": (
                    round((up_members / member_count) * 100, 2)
                    if member_count > 0
                    else 0
                ),
                "member_addresses": "; ".join([m["address"] for m in members]),
                "member_names": "; ".join([m["name"] for m in members]),
            }
        )

        rows.append(row)

    if rows:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env", default="Prod-interno-1", help="Item pyf5.<env> del Keychain"
    )
    environment = parser.parse_args().env
    host, username, password = keychain_credentials(environment)
    f5_client = F5Client(
        host=host,
        username=username,
        password=password,
        rate_limit_config=rate_config,
        timeout=30,
        max_retries=3,
    )
    retrieve_data(f5_client, environment)
    summary_csv(f"{environment}_output.json", f"{environment}_summary.csv")
