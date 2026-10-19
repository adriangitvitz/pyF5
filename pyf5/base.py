from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from typing_extensions import Self

from .breaker import CircuitBreaker
from .credentials import keychain_credentials
from .ratelimit import RateLimitConfig, TokenBucket
from .schemas.devices import Devices
from .schemas.logs import LogsResponse
from .schemas.monitors import Monitor, Monitors
from .schemas.pools import Nodes, Pools
from .schemas.rules import Rules
from .schemas.ssl import Certificates, SslProfiles
from .schemas.virtual_servers import VirtualServer, VirtualServers
from .schemas.virtual_stats import VirtualServerStatsResponse
from .tokenmanager import TokenManager

logger = logging.getLogger(__name__)

MONITOR_TYPES = ("http", "https", "tcp")


class F5Client:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        rate_limit_config: RateLimitConfig | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.base_url = f"https://{host}"
        self.host = host
        self.username = username
        self.password = password
        self.rate_limit_config = (
            rate_limit_config if rate_limit_config is not None else RateLimitConfig()
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = 1.0
        self.rate_limiter = TokenBucket(
            self.rate_limit_config.requests_per_second,
            self.rate_limit_config.burst_capacity,
        )
        self.circuit_breaker = CircuitBreaker()
        self.token_manager = TokenManager(self, username, password)
        self.client = httpx.Client(
            base_url=self.base_url,
            verify=False,
            timeout=self.timeout,
            limits=httpx.Limits(
                max_connections=100, max_keepalive_connections=10, keepalive_expiry=30.0
            ),
        )

    @classmethod
    def from_keychain(cls, environment: str, **kwargs: Any) -> F5Client:
        """Build a client from the macOS Keychain item pyf5.<environment>"""
        host, username, password = keychain_credentials(environment)
        return cls(host=host, username=username, password=password, **kwargs)

    @classmethod
    def from_env(cls, **kwargs: Any) -> F5Client:
        """Build a client from F5_HOST, F5_USERNAME and F5_PASSWORD"""
        return cls(
            host=os.environ["F5_HOST"],
            username=os.environ["F5_USERNAME"],
            password=os.environ["F5_PASSWORD"],
            **kwargs,
        )

    def close(self) -> None:
        token = self.token_manager.token
        if token:
            try:
                self.client.delete(
                    f"/mgmt/shared/authz/tokens/{token}",
                    headers={"X-F5-Auth-Token": token},
                )
            except httpx.HTTPError as e:
                logger.warning(f"Could not revoke token: {e}")
            self.token_manager.token = None
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _wait_for_rate_limit(self):
        while not self.rate_limiter.consume():
            time.sleep(0.1)

    def _make_request_without_auth(self, method: str, endpoint: str, **kwargs):
        url = f"{self.base_url}{endpoint}"
        return self.client.request(method, url, **kwargs)

    def _make_authenticated_request(self, method: str, endpoint: str, **kwargs):
        def _request_with_auth():
            self._wait_for_rate_limit()
            token = self.token_manager.get_valid_token()
            headers = kwargs.get("headers", {})
            headers["X-F5-Auth-Token"] = token
            kwargs["headers"] = headers
            url = f"{self.base_url}{endpoint}"
            response = self.client.request(method, url, **kwargs)
            if response.status_code == 401:
                logger.warning("token expired, forcing refresh")
                self.token_manager.token = None
                token = self.token_manager.get_valid_token()
                headers["X-F5-Auth-Token"] = token
                kwargs["headers"] = headers
                response = self.client.request(method, url, **kwargs)
            return response

        return self.circuit_breaker.call(_request_with_auth)

    def _backoff(self, attempt: int, reason: object) -> None:
        wait_time = self.backoff_factor * (2**attempt)
        logger.warning(
            f"Request failed (attempt {attempt + 1}): {reason} retrying in {wait_time}s"
        )
        time.sleep(wait_time)

    def make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._make_authenticated_request(method, endpoint, **kwargs)
            except httpx.TransportError as e:
                if attempt == self.max_retries:
                    raise
                self._backoff(attempt, e)
                continue
            if response.status_code < 400:
                return response
            if response.status_code < 500 or attempt == self.max_retries:
                response.raise_for_status()
            self._backoff(attempt, f"HTTP {response.status_code}")
        raise RuntimeError("retry loop ended without a response")

    def get_virtual_server_stats(self, name: str, partition: str = "Common"):
        response = self.make_request(
            "GET", f"/mgmt/tm/ltm/virtual/~{partition}~{name}/stats"
        )
        return response.json()

    def get_virtual_server(self, name: str, partition: str = "Common") -> VirtualServer:
        response = self.make_request("GET", f"/mgmt/tm/ltm/virtual/~{partition}~{name}")
        return VirtualServer.model_validate(response.json())

    def get_virtual_servers(self) -> VirtualServers:
        """Retrieve all virtual servers with their profiles"""
        response = self.make_request(
            "GET", "/mgmt/tm/ltm/virtual?expandSubcollections=true"
        )
        return VirtualServers.model_validate(response.json())

    def get_virtual_servers_stats(self) -> VirtualServerStatsResponse:
        response = self.make_request("GET", "/mgmt/tm/ltm/virtual/stats")
        return VirtualServerStatsResponse.model_validate(response.json())

    def get_pools(self) -> Pools:
        """Retrieve all load balancing pools with their members"""
        response = self.make_request(
            "GET", "/mgmt/tm/ltm/pool?expandSubcollections=true"
        )
        return Pools.model_validate(response.json())

    def get_nodes(self) -> Nodes:
        response = self.make_request("GET", "/mgmt/tm/ltm/node")
        return Nodes.model_validate(response.json())

    def get_monitors(self, monitor_type: str) -> Monitors:
        """Retrieve monitors of one type ('http', 'https', 'tcp', ...)"""
        response = self.make_request("GET", f"/mgmt/tm/ltm/monitor/{monitor_type}")
        return Monitors.model_validate(response.json())

    def get_all_monitors(self) -> dict[str, Monitor]:
        """Index http/https/tcp monitors by full path"""
        return {
            m.full_path: m for t in MONITOR_TYPES for m in self.get_monitors(t).items
        }

    def get_rules(self) -> Rules:
        """Retrieve all iRules with their definitions"""
        response = self.make_request("GET", "/mgmt/tm/ltm/rule")
        return Rules.model_validate(response.json())

    def get_devices(self) -> Devices:
        """Retrieve cluster devices; Devices.current is the one being queried"""
        response = self.make_request("GET", "/mgmt/tm/cm/device")
        return Devices.model_validate(response.json())

    def get_certificates(self) -> Certificates:
        """Retrieve all SSL certificates with their expiration data"""
        response = self.make_request("GET", "/mgmt/tm/sys/file/ssl-cert")
        return Certificates.model_validate(response.json())

    def get_ssl_profiles(self, profile_type: str) -> SslProfiles:
        """Retrieve SSL profiles; profile_type is 'client-ssl' or 'server-ssl'"""
        response = self.make_request("GET", f"/mgmt/tm/ltm/profile/{profile_type}")
        return SslProfiles.model_validate(response.json())

    def get_logs(self, facility: str, start: datetime, end: datetime) -> LogsResponse:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = self.make_request(
            "GET",
            f"/mgmt/tm/sys/log/{facility}/stats?options=range,{fmt(start)}--{fmt(end)}",
        )
        return LogsResponse.model_validate(response.json())
