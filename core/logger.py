import os
import json
import sqlite3
import logging
from datetime import datetime, timezone

class SystemLogger:
    def __init__(self, db_path="trades_log.db", log_level=logging.INFO):
        self.db_path = db_path
        self._setup_console_logger(log_level)
        self._setup_database()

    def _setup_console_logger(self, log_level):
        self.logger = logging.getLogger("AdaptiveAITrader")
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(log_level)
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def _setup_database(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Decisions log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                regime TEXT,
                regime_confidence REAL,
                bias TEXT,
                strategy TEXT,
                trade_score REAL,
                action TEXT,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                risk_pct REAL,
                lot_size REAL,
                reasons TEXT,
                reasons_not_to_trade TEXT
            )
            """)
            
            # Executed trades log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticket INTEGER,
                symbol TEXT,
                order_type TEXT,
                lots REAL,
                entry_price REAL,
                sl REAL,
                tp REAL,
                magic INTEGER,
                status TEXT,
                comment TEXT
            )
            """)
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite database: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def log_decision(self, decision: dict):
        self.info(f"DECISION [{decision.get('symbol', 'N/A')}]: Action={decision.get('action')} Score={decision.get('trade_score', 0):.1f} Regime={decision.get('regime')} ({decision.get('regime_confidence', 0):.0f}%)")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO decisions_log (
                timestamp, symbol, regime, regime_confidence, bias, strategy,
                trade_score, action, entry_price, sl_price, tp_price, risk_pct,
                lot_size, reasons, reasons_not_to_trade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                decision.get("symbol"),
                decision.get("regime"),
                decision.get("regime_confidence"),
                decision.get("bias"),
                decision.get("strategy"),
                decision.get("trade_score"),
                decision.get("action"),
                decision.get("entry_price"),
                decision.get("sl_price"),
                decision.get("tp_price"),
                decision.get("risk_pct"),
                decision.get("lot_size"),
                json.dumps(decision.get("reasons", [])),
                json.dumps(decision.get("reasons_not_to_trade", []))
            ))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log decision to DB: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def log_execution(self, ticket: int, symbol: str, order_type: str, lots: float, price: float, sl: float, tp: float, magic: int, status: str, comment: str):
        self.info(f"EXECUTION [{symbol}] Ticket={ticket} Type={order_type} Lots={lots:.2f} Price={price} Status={status}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO trades_execution_log (
                timestamp, ticket, symbol, order_type, lots, entry_price, sl, tp, magic, status, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(), ticket, symbol, order_type, lots, price, sl, tp, magic, status, comment
            ))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log execution to DB: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
