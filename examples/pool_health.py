"""Pool health per virtual server as JSON and CSV."""

import argparse
import csv
import json

from pyf5 import F5Client
from pyf5.report import pool_health, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Keychain item pyf5.<env>")
    args = parser.parse_args()

    with F5Client.from_keychain(args.env) as f5:
        data = pool_health(f5)

    with open(f"{args.env}_output.json", "w") as f:
        json.dump(data, f, indent=2)
    rows = summarize(data)
    if rows:
        with open(f"{args.env}_summary.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
