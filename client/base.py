import logging
from typing import Optional, Dict, Any, List
import httpx
import time
from .ratelimit import TokenBucket
from .breaker import CircuitBreaker
from .tokenmanager import TokenManager
from .ratelimit import RateLimitConfig


class F5Client:
    def __init__(self,
            host: str,
            username: str,
            password: str,
            rate_limit_config: Optional[RateLimitConfig] = None,
            timeout: int = 30,
            max_retries: int = 3):
        self.base_url = f"https://{host}"
        self.host = host
        self.username = username
        self.password = password
        self.rate_limit_config = rate_limit_config if rate_limit_config is not None else RateLimitConfig()
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
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=10, keepalive_expiry=30.0),
        )

    def _wait_for_rate_limit(self):
        while not self.rate_limiter.consume():
            time.sleep(0.1)

    def _make_request_without_auth(self, method: str, endpoint:str, **kwargs):
        url = f"{self.base_url}{endpoint}"
        return self.client.request(method, url, **kwargs)

    def _make_authenticated_request(self, method: str, endpoint:str, **kwargs):
        def _request_with_auth():
            self._wait_for_rate_limit()
            token = self.token_manager.get_valid_token()
            headers = kwargs.get('headers', {})
            headers["X-F5-Auth-Token"] = token
            kwargs['headers'] = headers
            url = f"{self.base_url}{endpoint}"
            response =  self.client.request(method, url, **kwargs)
            if response.status_code == 401:
                logging.warning("token expired, forcing refresh")
                self.token_manager.token = None
                token = self.token_manager.get_valid_token()
                headers["X-F5-Auth-Token"] = token
                kwargs['headers'] = headers
                response =  self.client.request(method, url, **kwargs)
            return response

        return self.circuit_breaker.call(_request_with_auth)

    def make_request(self, method: str, endpoint:str, **kwargs):
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._make_authenticated_request(method, endpoint, **kwargs)
                if 200 <= response.status_code < 300:
                    return response
                if 400 <= response.status_code < 500 and response.status_code != 401:
                    response.raise_for_status()
                if response.status_code >=  500 or response.status_code == 401:
                    if attempt < self.max_retries:
                        wait_time = self.backoff_factor * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
            except Exception as e:
                last_exception = e
                logging.warning(f"Request exception (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor * (2 ** attempt)
                    logging.warning(f"Request exception (attempt {attempt + 1}): {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    raise last_exception
        raise last_exception or Exception("Max retries exceeded")

    def get_vs(self) -> Dict[str, Any]:
        """Retrieve all load balancing pools"""
        response = self.make_request("GET", "/mgmt/tm/ltm/virtual")
        return response.json()

    def get_pools(self) -> Dict[str, Any]:
        """Retrieve all load balancing pools"""
        response = self.make_request("GET", "/mgmt/tm/ltm/pool")
        return response.json()

    def get_pool_members(self, pool_name: str) -> List[Dict[str, Any]]:
        """Get members of a specific pool"""
        endpoint = f"/mgmt/tm/ltm/pool/~Common~{pool_name}/members"
        response = self.make_request("GET", endpoint)
        return response.json().get('items', [])
