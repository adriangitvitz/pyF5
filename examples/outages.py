"""Pool member outages in the last N hours and the virtual servers they affected."""

import argparse
from datetime import datetime, timedelta, timezone

from pyf5 import F5Client, outages, virtual_servers_by_pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Keychain item pyf5.<env>")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    with F5Client.from_keychain(args.env) as f5:
        vs_by_pool = virtual_servers_by_pool(
            f5.get_virtual_servers(), f5.get_pools(), f5.get_rules()
        )
        entries = f5.get_logs("ltm", end - timedelta(hours=args.hours), end).entries

    for o in outages(entries, vs_by_pool):
        up = o["up_at"].strftime("%H:%M") if o["up_at"] else "still down"
        print(
            f"{o['down_at']:%H:%M} -> {up:<10} {o['pool']}  {o['member']}  "
            f"{o['virtual_servers']}  {o['last_error']}"
        )


if __name__ == "__main__":
    main()
