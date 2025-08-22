import time
from dataclasses import dataclass
from threading import Lock

@dataclass
class RateLimitConfig:
    requests_per_second: float = 10.0
    burst_capacity: int = 20
    cooldown_period: float = 1.0

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = Lock()

    def consume(self, amount: int = 1) -> bool:
        with self.lock:
            now = time.time()
            self.tokens = min(self.capacity, self.tokens + (now - self.last_refill) * self.rate)
            self.last_refill = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False
