"""JARVIS AI 4.0 — Real-Time Per-Symbol Optimizer."""
import time, threading, logging
from typing import Dict
logger = logging.getLogger("JARVIS_RealtimeOptimizer")
class RealtimeOptimizer:
    def __init__(self, db_path: str = "jarvis_history.db", cache_ttl: float = 60.0):
        self.db_path = db_path
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()
    def get_adjustments(self, symbol: str, regime: str = "GLOBAL") -> Dict[str, float]:
        key = f"{symbol}_{regime}"
        now = time.time()
        with self._lock:
            if key in self._cache:
                ts, val = self._cache[key]
                if now - ts < self.cache_ttl: return val
        adj = {"win_p_delta": 0.0, "score_delta": 0.0, "rr_delta": 0.0}
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT is_win FROM executed_trades WHERE symbol=? AND regime=? ORDER BY id DESC LIMIT 30", (symbol, regime))
            rows = cur.fetchall()
            conn.close()
            if len(rows) < 10:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
                cur = conn.cursor()
                cur.execute("SELECT is_win FROM executed_trades WHERE symbol=? ORDER BY id DESC LIMIT 30", (symbol,))
                rows = cur.fetchall()
                conn.close()
                if len(rows) < 10:
                    with self._lock: self._cache[key] = (now, adj)
                    return adj
            wins = sum(1 for r in rows if r[0]==1)
            win_rate = wins / len(rows)
            if win_rate < 0.50: adj = {"win_p_delta": 0.03, "score_delta": 3.0, "rr_delta": 0.10}
            elif win_rate < 0.55: adj = {"win_p_delta": 0.02, "score_delta": 2.0, "rr_delta": 0.05}
            elif win_rate > 0.68: adj = {"win_p_delta": -0.02, "score_delta": -2.0, "rr_delta": -0.05}
            elif win_rate > 0.62: adj = {"win_p_delta": -0.01, "score_delta": -1.0, "rr_delta": 0.0}
        except Exception as e:
            logger.debug(f"RealtimeOptimizer DB failed ({symbol}): {e}")
        with self._lock: self._cache[key] = (now, adj)
        return adj
