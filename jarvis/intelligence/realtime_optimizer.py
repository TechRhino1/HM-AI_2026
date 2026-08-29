"""
JARVIS AI 4.0 -- Real-Time Adaptive Feedback Optimizer.
Queries recent closed trade PnLs from SQLite to adjust win probability, score, and R:R deltas dynamically.
"""
from typing import Dict, Any, List
import time
import threading
import logging

logger = logging.getLogger("JARVIS_RealtimeOptimizer")

class RealtimeOptimizer:
    def __init__(self, db_path: str = "jarvis_history.db", cache_ttl: float = 60.0):
        self.db_path = db_path
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _query_pnls(db_path: str, where_sql: str, params: tuple) -> list:
        """Runs a SELECT realized_pnl query, guaranteeing the connection is
        always closed even if the query raises (prevents fd/connection leaks)."""
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=5.0)
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT realized_pnl FROM executed_trades WHERE realized_pnl != 0 AND {where_sql} "
                f"ORDER BY id DESC LIMIT 30",
                params
            )
            return cur.fetchall()
        finally:
            conn.close()

    def get_adjustments(self, symbol: str, regime: str = "GLOBAL") -> Dict[str, float]:
        key = f"{symbol}_{regime}"
        now = time.time()
        with self._lock:
            if key in self._cache:
                ts, val = self._cache[key]
                if now - ts < self.cache_ttl:
                    return val
        adj = {"win_p_delta": 0.0, "score_delta": 0.0, "rr_delta": 0.0}
        try:
            rows = self._query_pnls(self.db_path, "symbol=? AND regime=?", (symbol, regime))
            if len(rows) < 10:
                rows = self._query_pnls(self.db_path, "symbol=?", (symbol,))
                if len(rows) < 10:
                    with self._lock:
                        self._cache[key] = (now, adj)
                    return adj
            wins = sum(1 for r in rows if r[0] is not None and float(r[0]) > 0)
            win_rate = wins / len(rows)
            if win_rate < 0.50:
                adj = {"win_p_delta": 0.03, "score_delta": 3.0, "rr_delta": 0.10}
            elif win_rate < 0.55:
                adj = {"win_p_delta": 0.02, "score_delta": 2.0, "rr_delta": 0.05}
            elif win_rate > 0.68:
                adj = {"win_p_delta": -0.02, "score_delta": -2.0, "rr_delta": -0.05}
            elif win_rate > 0.62:
                adj = {"win_p_delta": -0.01, "score_delta": -1.0, "rr_delta": 0.0}
            with self._lock:
                self._cache[key] = (now, adj)
            return adj
        except Exception as e:
            logger.debug(f"RealtimeOptimizer DB failed ({symbol}): {e}")
            with self._lock:
                self._cache[key] = (now, adj)
            return adj
