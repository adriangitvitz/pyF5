import re
from collections import defaultdict

from .schemas.pools import Pools
from .schemas.rules import Rules
from .schemas.virtual_servers import VirtualServers

TOKEN = re.compile(r"[\w./-]+")


def virtual_servers_by_pool(
    virtual_servers: VirtualServers, pools: Pools, rules: Rules
) -> dict[str, list[str]]:
    """Map pool full path -> VS names, via the VS default pool or any iRule that names the pool.

    iRules are matched by name (`pool X`, `active_members X`, ...); pools picked from
    variables like `pool $selection` only count if their name also appears literally.
    """
    rule_pools: dict[str, set[str]] = {}
    for rule in rules.items:
        tokens = set(TOKEN.findall(rule.definition))
        rule_pools[rule.full_path] = {
            p.full_path for p in pools.items if p.full_path in tokens or p.name in tokens
        }

    result: dict[str, list[str]] = defaultdict(list)
    for vs in virtual_servers.items:
        referenced = {vs.pool} if vs.pool else set()
        for rule in vs.rules:
            referenced |= rule_pools.get(rule, set())
        for pool in sorted(referenced):
            result[pool].append(vs.name)
    return dict(result)
