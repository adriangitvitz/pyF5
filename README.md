# PyF5

English | [Español](README.es.md)

A read-only Python SDK for F5 BIG-IP that turns the iControl REST API into typed objects and ready-made analyses. Network and operations teams can use it to answer questions like these without clicking through the GUI or reading raw syslog: which certificates expire soon and which services do they break, what went down overnight and why, and are clients rejecting a new certificate?

## Demo

```python
from datetime import datetime, timedelta, timezone

from pyf5 import F5Client, outages, virtual_servers_by_pool

with F5Client.from_keychain("prod-internal") as f5:
    print(f5.get_devices().current.failover_state)

    vs_by_pool = virtual_servers_by_pool(f5.get_virtual_servers(), f5.get_pools(), f5.get_rules())
    end = datetime.now(timezone.utc)
    entries = f5.get_logs("ltm", end - timedelta(days=1), end).entries

for o in outages(entries, vs_by_pool):
    print(o["pool"], o["member"], o["virtual_servers"], o["down_at"], o["up_at"], o["last_error"])
```

```text
active
/Common/app-a_pool  /Common/node-12:8443  ['app-a_vs']  11:00  11:59  Response Code: 200 (OK)
/Common/api_pool_a  /Common/node-21:2525  ['api_vs']    10:59  12:00  Response Code: 301 (Moved Permanently)
/Common/ldap_pool   /Common/node-31:6803  ['ldap_vs']   11:05  11:56  Unable to connect.
```

Log summary, grouped by message pattern:

```text
   18 err     tmm    No members available for pool <obj>                ['/Common/api_pool_a', '/Common/app-a_pool', ...]
   20 notice  mcpd   Pool <obj> member <obj> monitor status down.        ['/Common/app-a_pool', '/Common/node-12:8443', ...]
    9 notice  mcpd   SNMP_TRAP: Virtual <obj> has become unavailable     ['/Common/app-a_vs', '/Common/api_vs', ...]
   14 notice  tmm    Clock advanced by <n> ticks                         []
```

TLS alerts per virtual server:

```text
portal_vs                                48=    0 46=    8 hs=     8
web_vs                                   48=    0 46=    0 hs=   121
log throttled 4 times: counts are minimums
```

## Why PyF5

A BIG-IP already holds everything you need to explain an incident. The trouble is that it is spread across objects that only make sense together. A log line names a pool member, the member belongs to a pool, an iRule picks that pool, and a virtual server runs the iRule. A certificate is referenced by SSL profiles, and those profiles are attached to virtual servers.

PyF5 connects those pieces for you:

- **Typed, not raw.** Every response is validated into a pydantic model, so you work with `pool.members`, `cert.expires_at` and `entry.severity` instead of nested dicts.
- **Relationships built in.** Certificate to profile to virtual server, pool to virtual server (through the default pool or any iRule that names it), and log line to virtual server.
- **Analysis next to the data.** Log parsing, aggregation, outage pairing, TLS alert counting and certificate inventory are plain functions over the models, so they compose in a notebook, a script or another service.
- **Read-only by design.** It only issues `GET` requests, so it is safe to point at production.
- **Gentle on the device.** It has a token-bucket rate limit, a circuit breaker, retries with exponential backoff for network errors and 5xx, and token revocation on exit.

## Features

### Configuration and state

| Method | Returns |
|---|---|
| `get_virtual_servers()` / `get_virtual_server(name)` | Virtual servers with destination, default pool, iRules and profiles |
| `get_virtual_servers_stats()` | Traffic statistics per virtual server |
| `get_pools()` | Pools with their members and member state (`pool.members`) |
| `get_nodes()` | Nodes with state and session |
| `get_monitors(type)` / `get_all_monitors()` | HTTP, HTTPS and TCP monitors with `send`, `recv`, `interval` and `timeout`, indexed by full path |
| `get_rules()` | iRules with their definitions |
| `get_certificates()` | Certificates with subject, issuer, SAN and expiration |
| `get_ssl_profiles(type)` | Client-SSL and server-SSL profiles and the certificates they use |
| `get_devices()` | Cluster devices. `.current` shows whether you are talking to the active or the standby unit |
| `get_logs(facility, start, end)` | Any log facility (`ltm`, `audit`, ...) for a time range, parsed into `LogEntry` objects via `.entries` |

### Analysis

| Function | What it answers |
|---|---|
| `pyf5.filter_entries(entries, min_severity, text)` | Only the lines at or above a severity, or containing some text |
| `pyf5.aggregate(entries)` | Which message patterns repeat, how often, from when to when, and on which objects |
| `pyf5.outages(entries, vs_by_pool)` | Which pool members went down, for how long, with what monitor error, and which virtual servers were affected |
| `pyf5.tls_alerts(entries, virtual_servers)` | Which virtual servers have clients rejecting the certificate (alerts 46 and 48) or failing the handshake |
| `pyf5.virtual_servers_by_pool(vs, pools, rules)` | Which virtual servers use each pool, through the default pool or an iRule |
| `pyf5.certs.retrieve_inventory(f5)` / `filter_inventory(...)` / `flatten(...)` | Which certificates expire within N days and which profiles and virtual servers depend on them |
| `pyf5.report.pool_health(f5)` / `summarize(data)` | Pool health per virtual server: members up and down, and health percentage |

## Quick start

1. Install the SDK (requires Python 3.9+):

   ```bash
   uv add git+https://github.com/adriangitvitz/pyF5.git
   # or: pip install git+https://github.com/adriangitvitz/pyF5.git
   ```

2. Provide credentials. Either export environment variables:

   ```bash
   export F5_HOST=<management-host> F5_USERNAME=<username> F5_PASSWORD=<password>
   ```

   or, on macOS, store one Keychain item per device. The service is `pyf5.<environment>`, the account is the username, and the comment is the management host. `-w` prompts for the password:

   ```bash
   security add-generic-password -s pyf5.prod-internal -a <username> -j <management-host> -w
   ```

3. Query the device:

   ```python
   from pyf5 import F5Client

   with F5Client.from_env() as f5:  # or F5Client.from_keychain("prod-internal")
       device = f5.get_devices().current
       print(device.name, device.failover_state, device.version)
       for vs in f5.get_virtual_servers().items:
           print(vs.name, vs.destination, vs.pool)
   ```

## Usage and configuration

### Creating a client

```python
from pyf5 import F5Client, RateLimitConfig

f5 = F5Client(host=host, username=username, password=password)
f5 = F5Client.from_env()
f5 = F5Client.from_keychain("prod-internal")
```

All three accept the same options:

```python
F5Client.from_env(
    rate_limit_config=RateLimitConfig(requests_per_second=5.0, burst_capacity=10),
    timeout=30,      # seconds per request; raise it for long log ranges
    max_retries=3,   # applies to network errors and 5xx; 4xx fail immediately
)
```

Use the client as a context manager (`with ... as f5:`) or call `f5.close()` yourself. Either way the auth token is revoked on the device and the connection is closed.

### Errors

| Exception | When |
|---|---|
| `pyf5.AuthenticationError` | The device rejects the credentials or does not return a token |
| `pyf5.CircuitOpenError` | Too many consecutive failures; requests pause for 60 seconds |
| `httpx.HTTPStatusError` | The API answers 4xx, or 5xx after all retries |
| `httpx.TransportError` | The device is unreachable after all retries |

### Logs

`get_logs` takes timezone-aware datetimes and converts them to UTC for the API:

```python
from datetime import datetime, timedelta, timezone

from pyf5 import aggregate, filter_entries, tls_alerts

end = datetime.now(timezone.utc)
entries = f5.get_logs("ltm", end - timedelta(hours=1), end).entries

for line in filter_entries(entries, text="pool"):
    print(line.raw)

for g in aggregate(filter_entries(entries, min_severity="warning")):
    print(g["count"], g["severity"], g["pattern"], g["objects"][:3])

result = tls_alerts(entries, f5.get_virtual_servers())
```

Severity levels go from `emerg` to `debug`. Pool member state changes are logged at `notice`, so use `min_severity="notice"` when you are looking for outages.

### Monitors

```python
monitors = f5.get_all_monitors()
for pool in f5.get_pools().items:
    m = monitors.get(pool.monitor)
    print(pool.name, m.recv if m else pool.monitor)
```

### Certificates and pool health

```python
from pyf5.certs import filter_inventory, retrieve_inventory
from pyf5.report import pool_health, summarize

expiring = filter_inventory(retrieve_inventory(f5), days=30, in_use=True)
rows = summarize(pool_health(f5))
```

### Examples

Ready-to-run scripts live in `examples/`. Each one takes `--env`, the name of a Keychain item:

| Script | Output |
|---|---|
| `examples/certificate_inventory.py --env <env> --days 30 --in-use` | `certs/<env>_certificates.json` and `.csv`, plus a console report |
| `examples/pool_health.py --env <env>` | `<env>_output.json` and `<env>_summary.csv` |
| `examples/outages.py --env <env> --hours 24` | Outages with duration, monitor error and affected virtual servers |
| `examples/log_summary.py --env <env> --hours 1` | Log patterns and TLS alerts per virtual server |

```bash
uv run python examples/outages.py --env prod-internal
```

### Project layout

```text
pyf5/
  base.py          F5Client: auth, retries, rate limit, circuit breaker, API methods
  logs.py          log filtering, aggregation, outages, TLS alerts
  topology.py      pool to virtual server mapping (default pool and iRules)
  certs.py         certificate inventory
  report.py        pool health per virtual server
  credentials.py   macOS Keychain lookup
  schemas/         pydantic models for every response
examples/          runnable scripts built on the SDK
```
