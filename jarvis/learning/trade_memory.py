"""
JARVIS AI 3.0 — Persistent Trade Memory & Journaling Engine.
Logs rich execution records, market snapshots, MFE/MAE excursions, and decision context to SQLite.
"""
import os
import sqlite3
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

class TradeMemory:
    def __init__(self, db_path: str = "jarvis_trade_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                trade_type TEXT,
                entry_price REAL,
                exit_price REAL,
                sl REAL,
                tp REAL,
                lots REAL,
                pnl REAL,
                is_win INTEGER,
                regime TEXT,
                strategy TEXT,
                model_confidence REAL,
                adversarial_penalty REAL,
                expected_value REAL,
                mfe REAL,
                mae REAL,
                reasoning TEXT,
                quality_gate TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_trade(self, trade_data: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO trade_records VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            trade_data.get("ticket", int(datetime.now().timestamp())),
            trade_data.get("symbol", "UNKNOWN"),
            trade_data.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
            trade_data.get("type", "BUY"),
            trade_data.get("entry", 0.0),
            trade_data.get("exit", 0.0),
            trade_data.get("sl", 0.0),
            trade_data.get("tp", 0.0),
            trade_data.get("lots", 0.01),
            trade_data.get("pnl", 0.0),
            1 if trade_data.get("pnl", 0.0) > 0 else 0,
            trade_data.get("regime", "NEUTRAL"),
            trade_data.get("strategy", "TREND_FOLLOWING"),
            trade_data.get("model_confidence", 0.5),
            trade_data.get("adversarial_penalty", 0.0),
            trade_data.get("expected_value", 0.0),
            trade_data.get("mfe", 0.0),
            trade_data.get("mae", 0.0),
            json.dumps(trade_data.get("reasoning", {})),
            json.dumps(trade_data.get("quality_gate", {}))
        ))
        conn.commit()
        conn.close()

    def fetch_all_trades(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM trade_records ORDER BY timestamp DESC")
        rows = cur.fetchall()
        trades = [dict(r) for r in rows]
        conn.close()
        return trades
