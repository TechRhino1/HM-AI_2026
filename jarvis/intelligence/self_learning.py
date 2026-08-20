import logging
import sqlite3

logger = logging.getLogger('JARVIS_SelfLearning')

class SelfLearningEngine:
    def __init__(self, db_path='jarvis_history.db'):
        self.db_path = db_path

    def get_regime_multiplier(self, regime: str, lookback: int = 50) -> float:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT expected_value FROM executed_trades WHERE regime=? ORDER BY id DESC LIMIT ?", (regime, lookback))
            rows = cur.fetchall()
            conn.close()
            
            if len(rows) < 5:
                return 1.0 # Not enough data
            
            avg_ev = sum(r[0] for r in rows) / len(rows)
            if avg_ev > 0.5:
                return 1.10 # Boost
            elif avg_ev < 0:
                return 0.90 # Penalize
            return 1.0
        except Exception as e:
            logger.warning(f"Self-learning DB read failed: {e}")
            return 1.0
