import json
import re
from client.ratelimit import RateLimitConfig
from client.base import F5Client
from typing import List, Dict, Any
import csv

rate_config = RateLimitConfig(
    requests_per_second=5.0,
    burst_capacity=10,
    cooldown_period=2.0
)

def extract_pool_name_from_url(url: str) -> str:
    pattern = r"~Common~([^/?]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract pool name from URL: {url}")


def retrieve_data(f5_client, environment):
    vs = f5_client.get_vs()
    with open('vs.json', 'w') as f:
        json.dump(vs, f, indent=4)

    pools = f5_client.get_pools()
    with open('pools.json', 'w') as f:
        json.dump(pools, f, indent=4)

    vs = json.loads(open('vs.json', 'r').read())["items"]
    pools = json.loads(open('pools.json', 'r').read())["items"]

    data = []
    for virtual in vs:
        virtual_data = {
            "name": virtual["name"],
            "creationTime": virtual["creationTime"],
            "destination": virtual.get("destination", "").replace("/Common/", ""),
            "disabled": virtual.get("disabled", False),
            "source": virtual["source"],
            "sourceAddressTranslation": virtual["sourceAddressTranslation"]["type"],
            "pool": {}
        }
        pool_reference = virtual.get("poolReference", None)
        if pool_reference:
            pool_vs = pool_reference["link"]
            related_pool = [pool for pool in pools if pool["selfLink"] == pool_vs][0]
            filter_member_keys = ["name", "monitor", "address", "state", "session"]
            pool_name = extract_pool_name_from_url(related_pool["selfLink"])
            members: List[Dict[str, Any]] = f5_client.get_pool_members(pool_name)
            filtered_members = [
                {k: d[k] for k in filter_member_keys if k in d}
                for d in members
            ]
            virtual_data["pool"] = {
                "name": pool_name,
                "monitor": related_pool.get("monitor", "").replace("/Common/", ""),
                "members": filtered_members
            }
        data.append(virtual_data)

    with open(f"{environment}_output.json", "w") as f:
        json.dump(data, f, indent=4)

def summary_csv(json_file: str, csv_file: str):
    with open(json_file, 'r') as f:
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
        row.update({
            "pool_name": pool.get("name", ""),
            "pool_monitor": pool.get("monitor", ""),
            "total_members": member_count,
            "up_members": up_members,
            "down_members": down_members,
            "health_percentage": round((up_members / member_count) * 100, 2) if member_count > 0 else 0,
            "member_addresses": "; ".join([m["address"] for m in members]),
            "member_names": "; ".join([m["name"] for m in members])
        })

        rows.append(row)

    if rows:
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

if __name__ == "__main__":
    environment = "<environment>"
    f5_client = F5Client(
        host="<host_or_ip>",
        username="<username>",
        password="<password>",
        rate_limit_config=rate_config,
        timeout=30,
        max_retries=3
    )
    retrieve_data(f5_client, environment)
    summary_csv(f"{environment}_output.json", f"{environment}_summary.csv")
