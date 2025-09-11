from threading import Lock
import time
from typing_extensions import Optional
import logging


class TokenManager:
    def __init__(self, f5_client, username: str, password: str):
        self.f5_client = f5_client
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self.token_expiration = None
        self.refresh_threshold = 300  # 5 minutes in seconds
        self._lock = Lock()

    def get_valid_token(self) -> str:
        with self._lock:
            if self._needs_refresh():
                self._refresh_token()
            if self.token is None:
                raise Exception("Failed to obtain a valid token")
            return self.token

    def _needs_refresh(self) -> bool:
        if self.token_expiration is None or not self.token:
            return True
        return time.time() >= (self.token_expiration - self.refresh_threshold)

    def _refresh_token(self):
        try:
            auth_data = {
                "username": self.username,
                "password": self.password,
                "loginProviderName": "tmos",
            }

            response = self.f5_client._make_request_without_auth(
                "POST", "/mgmt/shared/authn/login", json=auth_data
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token", {}).get("token")
                self.token_expiration = time.time() + data.get("token", {}).get(
                    "timeout", 1200
                )
            else:
                logging.error(f"Failed to refresh token: {response.status_code}")
                raise Exception(f"Failed to refresh token: {response.status_code}")
        except Exception as e:
            logging.error(f"Failed to refresh token: {e}")
            raise
