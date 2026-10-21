"""Circuit breaker. Spec: docs/03-specs/04-model-gateway.md."""

from dataclasses import dataclass


@dataclass
class Breaker:
    """Closed, then open after ``threshold`` failures, then half-open."""

    threshold: int = 5
    reset_s: float = 30
    failures: int = 0
    state: str = "closed"
    open_until: float = 0

    def allow(self, now: float) -> bool:
        if self.state == "open" and now < self.open_until:
            return False
        if self.state == "open":
            self.state = "half_open"
        return True

    def success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def failure(self, now: float) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.threshold:
            self.state = "open"
            self.open_until = now + self.reset_s
            self.failures = 0
