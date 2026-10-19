import time
from enum import Enum
from threading import Lock


class CircuitOpenError(Exception):
    pass


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = Lock()

    def call(self, func, *args, **kwargs):
        with self._lock:
            if self.state == CircuitState.OPEN:
                if (
                    self.last_failure_time is not None
                    and time.time() - self.last_failure_time < self.timeout
                ):
                    raise CircuitOpenError("Circuit breaker is OPEN")
                else:
                    self.state = CircuitState.HALF_OPEN

            try:
                result = func(*args, **kwargs)
                self._reset()
                return result
            except Exception:
                self._record_failure()
                raise

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def _reset(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
