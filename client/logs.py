import re
from collections import Counter, defaultdict
from typing import Any

from .schemas.logs import SEVERITIES, LogEntry
from .schemas.virtual_servers import VirtualServers

OBJECT = re.compile(r"/\S+?/[^\s:]+(?::\d+)?")
NUMBER = re.compile(r"\b\d+\b")
TMM_THREAD = re.compile(r"^tmm\d+$")

ALERT = re.compile(r"-> (\S+): Connection error: ssl_codec_rx:\d+: alert\((46|48)\)")
HANDSHAKE = re.compile(r"SSL Handshake failed for TCP \S+ -> (\S+)")
THROTTLED = "Per-invocation log rate exceeded"

MEMBER_STATUS = re.compile(r"^Pool (\S+) member (\S+) monitor status (down|up)\.")
LAST_ERROR = re.compile(r"last error: \S+:\s+(.*?)\s*@")


def filter_entries(
    entries: list[LogEntry], min_severity: str = "debug", text: str = ""
) -> list[LogEntry]:
    limit = SEVERITIES.index(min_severity)
    needle = text.lower()
    return [e for e in entries if e.level <= limit and needle in e.message.lower()]


def aggregate(entries: list[LogEntry]) -> list[dict[str, Any]]:
    groups: dict[tuple, dict[str, Any]] = {}
    for e in entries:
        message = e.message.split(" [ ")[0]
        process = TMM_THREAD.sub("tmm", e.process)
        template = NUMBER.sub("<n>", OBJECT.sub("<obj>", message))
        key = (e.severity, process, template)
        g = groups.setdefault(
            key,
            {
                "severity": e.severity,
                "process": process,
                "pattern": template,
                "count": 0,
                "first": e.timestamp,
                "last": e.timestamp,
                "objects": set(),
            },
        )
        g["count"] += 1
        g["first"] = min(g["first"], e.timestamp)
        g["last"] = max(g["last"], e.timestamp)
        g["objects"].update(OBJECT.findall(message))

    result = [{**g, "objects": sorted(g["objects"])} for g in groups.values()]
    result.sort(key=lambda g: (SEVERITIES.index(g["severity"]), -g["count"]))
    return result


def vs_by_destination(virtual_servers: VirtualServers) -> dict[str, str]:
    return {vs.destination.split("/")[-1]: vs.name for vs in virtual_servers.items}


def tls_alerts(
    entries: list[LogEntry], virtual_servers: VirtualServers
) -> dict[str, Any]:
    """Count TLS alerts 46/48 and failed handshakes per virtual server.

    throttled > 0 means the F5 dropped log lines, so counts are minimums.
    """
    dest2vs = vs_by_destination(virtual_servers)
    per_vs: dict[str, Counter] = defaultdict(Counter)
    throttled = 0
    for e in entries:
        if THROTTLED in e.message:
            throttled += 1
        elif m := ALERT.search(e.message):
            per_vs[dest2vs.get(m[1], m[1])][f"alert_{m[2]}"] += 1
        elif m := HANDSHAKE.search(e.message):
            per_vs[dest2vs.get(m[1], m[1])]["handshake_failed"] += 1
    return {
        "virtual_servers": {vs: dict(c) for vs, c in per_vs.items()},
        "throttled": throttled,
    }


def outages(
    entries: list[LogEntry], vs_by_pool: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Pair member down/up events; up_at is None if still down at the end of the range.

    vs_by_pool comes from topology.virtual_servers_by_pool.
    """
    pending: dict[tuple, dict[str, Any]] = {}
    closed = []
    for e in sorted(entries, key=lambda e: e.timestamp):
        m = MEMBER_STATUS.match(e.message)
        if not m:
            continue
        pool, member, status = m.groups()
        if status == "down":
            error = LAST_ERROR.search(e.message)
            pending[(pool, member)] = {
                "pool": pool,
                "member": member,
                "virtual_servers": vs_by_pool.get(pool, []),
                "down_at": e.timestamp,
                "up_at": None,
                "last_error": error[1] if error else None,
            }
        elif outage := pending.pop((pool, member), None):
            outage["up_at"] = e.timestamp
            closed.append(outage)
    return closed + list(pending.values())
