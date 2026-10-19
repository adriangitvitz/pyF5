"""Certificate inventory: expiration -> SSL profiles -> virtual servers."""

import argparse
import csv
import json
import os
from typing import Any

from pyf5 import F5Client
from pyf5.certs import filter_inventory, flatten, retrieve_inventory


def print_report(inventory: list[dict[str, Any]]):
    for cert in inventory:
        days = "?" if cert["days_left"] is None else cert["days_left"]
        print(f"{days:>6}d  {cert['expires_at'] or '-':<25}  {cert['name']}")
        if not cert["profiles"]:
            print("          (no profiles)")
        for profile in cert["profiles"]:
            print(
                f"          {profile['type']:<10} {profile['name']}  [{','.join(profile['roles'])}]"
            )
            if not profile["virtual_servers"]:
                print("              (no virtual servers)")
            for vs in profile["virtual_servers"]:
                state = "enabled" if vs["enabled"] else "disabled"
                print(
                    f"              VS /{vs['partition']}/{vs['name']}  {vs['destination']}  {state}"
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Keychain item pyf5.<env>")
    parser.add_argument(
        "--days", type=int, help="Expiring within N days, including expired"
    )
    parser.add_argument("--name", help="Substring of the certificate name or subject")
    parser.add_argument(
        "--in-use",
        action="store_true",
        help="Only certificates reaching a virtual server",
    )
    args = parser.parse_args()

    with F5Client.from_keychain(args.env) as f5:
        inventory = filter_inventory(
            retrieve_inventory(f5), args.days, args.name, args.in_use
        )

    os.makedirs("certs", exist_ok=True)
    with open(f"certs/{args.env}_certificates.json", "w") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    write_csv(f"certs/{args.env}_certificates.csv", flatten(inventory))
    print_report(inventory)


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if rows:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
