"""Log lines grouped by message pattern, plus TLS alerts per virtual server."""

import argparse
from datetime import datetime, timedelta, timezone

from pyf5 import F5Client, aggregate, filter_entries, tls_alerts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Keychain item pyf5.<env>")
    parser.add_argument("--hours", type=int, default=1)
    parser.add_argument("--min-severity", default="notice")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    with F5Client.from_keychain(args.env) as f5:
        entries = f5.get_logs("ltm", end - timedelta(hours=args.hours), end).entries
        alerts = tls_alerts(entries, f5.get_virtual_servers())

    for g in aggregate(filter_entries(entries, min_severity=args.min_severity)):
        print(
            f"{g['count']:>5} {g['severity']:<7} {g['process']:<6} {g['pattern']}  {g['objects'][:3]}"
        )

    print()
    for name, c in sorted(
        alerts["virtual_servers"].items(), key=lambda kv: -sum(kv[1].values())
    ):
        print(
            f"{name:<40} 48={c.get('alert_48', 0):>5} 46={c.get('alert_46', 0):>5} "
            f"hs={c.get('handshake_failed', 0):>6}"
        )
    if alerts["throttled"]:
        print(f"log throttled {alerts['throttled']} times: counts are minimums")


if __name__ == "__main__":
    main()
