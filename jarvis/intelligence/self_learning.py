import logging
import sqlite3
import time
import threading

logger = logging.getLogger('JARVIS_SelfLearning')

class SelfLearningEngine:
    def __init__(self, db_path='jarvis_history.db', cache_ttl_sec: float = 15.0):
        self.db_path = db_path
        self.cache_ttl_sec = cache_ttl_sec
        self._cache = {}
        self._lock = threading.Lock()

    def get_regime_multiplier(self, regime: str, lookback: int = 50) -> float:
        now = time.time()
        cache_key = f"{regime}_{lookback}"
        with self._lock:
            if cache_key in self._cache:
                ts, val = self._cache[cache_key]
                if now - ts < self.cache_ttl_sec:
                    return val

        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute("SELECT expected_value FROM executed_trades WHERE regime=? ORDER BY id DESC LIMIT ?", (regime, lookback))
            rows = cur.fetchall()
            conn.close()
            
            if len(rows) < 5:
                res = 1.0 # Not enough data
            else:
                avg_ev = sum(r[0] for r in rows) / len(rows)
                if avg_ev > 0.5:
                    res = 1.10 # Boost
                elif avg_ev < 0:
                    res = 0.90 # Penalize
                else:
                    res = 1.0

            with self._lock:
                self._cache[cache_key] = (now, res)
            return res
        except Exception as e:
            logger.warning(f"Self-learning DB read failed: {e}")
            return 1.0
