"""
JARVIS AI 3.0 — Circuit Breaker & Safety Lockout Engine.
Halts trading during consecutive execution failures, rapid loss streaks, or platform anomalies.
"""
import time
import sqlite3
from typing import Dict, Any

class CircuitBreaker:
    def __init__(self, db_path: str = "jarvis_circuit_state.db"):
        self.enabled = True
        self.consecutive_losses = 0
        self.is_tripped = False
        self.tripped_timestamp = 0.0
        self.trip_reason = ""
        self.db_path = db_path
        if self.db_path:
            self._init_db()
            self._load_state()

    def _init_db(self):
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS circuit_state (
                    id INTEGER PRIMARY KEY,
                    consecutive_losses INTEGER,
                    is_tripped INTEGER,
                    tripped_timestamp REAL,
                    trip_reason TEXT
                )
            ''')
            conn.commit()

    def _load_state(self):
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT consecutive_losses, is_tripped, tripped_timestamp, trip_reason FROM circuit_state WHERE id = 1')
            row = cursor.fetchone()
            if row:
                self.consecutive_losses, is_tripped_int, self.tripped_timestamp, self.trip_reason = row
                self.is_tripped = bool(is_tripped_int)
            else:
                conn.execute('INSERT INTO circuit_state (id, consecutive_losses, is_tripped, tripped_timestamp, trip_reason) VALUES (1, 0, 0, 0.0, "")')
                conn.commit()

    def _save_state(self):
        if not self.db_path:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE circuit_state
                SET consecutive_losses = ?, is_tripped = ?, tripped_timestamp = ?, trip_reason = ?
                WHERE id = 1
            ''', (self.consecutive_losses, int(self.is_tripped), self.tripped_timestamp, self.trip_reason))
            conn.commit()

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def record_trade_result(self, is_win: bool):
        if is_win:
            self.consecutive_losses = 0
            self._save_state()
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                self.trip(f"{self.consecutive_losses} consecutive loss limit reached.")
            else:
                self._save_state()

    def trip(self, reason: str):
        self.is_tripped = True
        self.tripped_timestamp = time.time()
        self.trip_reason = reason
        self._save_state()

    def reset(self):
        self.is_tripped = False
        self.consecutive_losses = 0
        self.trip_reason = ""
        self._save_state()
        
    def _get_adaptive_cooldown(self) -> float:
        if self.consecutive_losses >= 7:
            return 28800.0  # 8 hours
        elif self.consecutive_losses >= 5:
            return 7200.0   # 2 hours
        else:
            return 1800.0   # 30 min

    def check_status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"active": False, "reason": ""}
            
        if self.is_tripped:
            elapsed = time.time() - self.tripped_timestamp
            cooldown_seconds = self._get_adaptive_cooldown()
            
            if elapsed >= cooldown_seconds:
                self.reset()
                return {"active": False, "reason": ""}
            return {
                "active": True,
                "reason": self.trip_reason,
                "remaining_cooldown_sec": round(cooldown_seconds - elapsed, 0)
            }
        return {"active": False, "reason": ""}
