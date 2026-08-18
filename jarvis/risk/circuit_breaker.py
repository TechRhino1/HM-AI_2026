"""
JARVIS AI 3.0 — Circuit Breaker & Safety Lockout Engine.
Halts trading during consecutive execution failures, rapid loss streaks, or platform anomalies.
"""
import time
from typing import Dict, Any

class CircuitBreaker:
    def __init__(self, max_consecutive_losses: int = 3, cooldown_seconds: float = 1800.0):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_losses = 0
        self.is_tripped = False
        self.tripped_timestamp = 0.0
        self.trip_reason = ""

    def record_trade_result(self, is_win: bool):
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trip(f"{self.consecutive_losses} consecutive loss limit reached.")

    def trip(self, reason: str):
        self.is_tripped = True
        self.tripped_timestamp = time.time()
        self.trip_reason = reason

    def reset(self):
        self.is_tripped = False
        self.consecutive_losses = 0
        self.trip_reason = ""

    def check_status(self) -> Dict[str, Any]:
        if self.is_tripped:
            elapsed = time.time() - self.tripped_timestamp
            if elapsed >= self.cooldown_seconds:
                self.reset()
                return {"active": False, "reason": ""}
            return {
                "active": True,
                "reason": self.trip_reason,
                "remaining_cooldown_sec": round(self.cooldown_seconds - elapsed, 0)
            }
        return {"active": False, "reason": ""}
