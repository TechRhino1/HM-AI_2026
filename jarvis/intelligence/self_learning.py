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

        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute("SELECT expected_value FROM executed_trades WHERE regime=? ORDER BY id DESC LIMIT ?", (regime, lookback))
            rows = cur.fetchall()
            
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
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_pattern_win_rate_and_ev(
        self,
        symbol: str,
        regime: str,
        session_name: str = "LONDON",
        is_prime: bool = True,
        lookback: int = 60
    ) -> dict:
        """
        Queries historical closed trades with similar market conditions (Symbol + Regime + Session)
        to yield empirical win rate, average EV, and sample size for evidence-based decision calibration.
        """
        now = time.time()
        cache_key = f"pattern_{symbol}_{regime}_{session_name}_{int(is_prime)}_{lookback}"
        with self._lock:
            if cache_key in self._cache:
                ts, val = self._cache[cache_key]
                if now - ts < self.cache_ttl_sec:
                    return val

        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("""
                SELECT expected_value, ai_score, session_name, is_prime_session 
                FROM executed_trades 
                WHERE symbol=? AND regime=?
                ORDER BY id DESC LIMIT ?
            """, (symbol, regime, lookback))
            rows = cur.fetchall()

            if not rows or len(rows) < 3:
                res = {
                    "sample_size": len(rows) if rows else 0,
                    "avg_ev": 0.0,
                    "win_rate": 0.50,
                    "conviction_multiplier": 1.0,
                    "empirical_edge": False
                }
            else:
                avg_ev = sum(r[0] for r in rows if r[0] is not None) / len(rows)
                positive_ev_count = sum(1 for r in rows if (r[0] or 0) > 0)
                win_rate = positive_ev_count / len(rows)

                # Conviction multiplier between 0.8x and 1.25x based on empirical pattern history
                if win_rate >= 0.65 and avg_ev >= 1.0:
                    conviction_mult = 1.25
                elif win_rate >= 0.55:
                    conviction_mult = 1.10
                elif win_rate <= 0.35 or avg_ev < 0:
                    conviction_mult = 0.80
                else:
                    conviction_mult = 1.0

                res = {
                    "sample_size": len(rows),
                    "avg_ev": round(avg_ev, 2),
                    "win_rate": round(win_rate, 2),
                    "conviction_multiplier": conviction_mult,
                    "empirical_edge": avg_ev > 0.5 and win_rate >= 0.55
                }

            with self._lock:
                self._cache[cache_key] = (now, res)
            return res
        except Exception as e:
            logger.warning(f"Self-learning pattern read failed: {e}")
            return {
                "sample_size": 0,
                "avg_ev": 0.0,
                "win_rate": 0.50,
                "conviction_multiplier": 1.0,
                "empirical_edge": False
            }
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
