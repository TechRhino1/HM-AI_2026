import sqlite3
import json
import logging
from datetime import datetime
import threading
import os

logger = logging.getLogger("JARVIS_Database")

class SQLiteTradeDB:
    def __init__(self, db_path="jarvis_history.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn.execute("PRAGMA cache_size=-64000;")
            self._local.conn.execute("PRAGMA temp_store=MEMORY;")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS executed_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER,
                    symbol TEXT,
                    action TEXT,
                    entry_price REAL,
                    sl REAL,
                    tp REAL,
                    volume REAL,
                    timestamp TEXT,
                    ai_score REAL,
                    regime TEXT,
                    expected_value REAL,
                    executor TEXT DEFAULT 'BOT (AI)'
                )
            ''')
            # Create fast query lookup indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executed_trades_ticket ON executed_trades(ticket);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executed_trades_symbol ON executed_trades(symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executed_trades_timestamp ON executed_trades(timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executed_trades_regime ON executed_trades(regime);")

            # Ensure executor column exists in existing tables
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(executed_trades)")
            cols = [row[1] for row in cur.fetchall()]
            if "executor" not in cols:
                conn.execute("ALTER TABLE executed_trades ADD COLUMN executor TEXT DEFAULT 'BOT (AI)'")
            conn.commit()
            logger.info("SQLite database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite DB: {e}")

    def log_trade(self, ticket: int, symbol: str, action: str, entry: float, sl: float, tp: float, volume: float, score: float, regime: str, ev: float, executor: str = "BOT (AI)"):
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO executed_trades (ticket, symbol, action, entry_price, sl, tp, volume, timestamp, ai_score, regime, expected_value, executor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket, symbol, action, entry, sl, tp, volume, datetime.now(timezone.utc).isoformat(), score, regime, ev, executor))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log trade to DB: {e}")

    def sync_mt5_history(self, days: int = 30, limit: int = 100):
        """Syncs executed and closed trades from MT5 broker history into SQLite database."""
        try:
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta, timezone
            from jarvis.data.symbol_registry import resolve
            
            if not mt5.terminal_info():
                mt5.initialize()

            # Broker server time can be ahead of local machine time (e.g. GMT+3 / EET)
            from_date = datetime.now() - timedelta(days=days)
            to_date = datetime.now() + timedelta(days=7)
            deals = mt5.history_deals_get(from_date, to_date)
            if not deals:
                return

            conn = self._get_conn()
            pos_map = {}
            for d in deals:
                pid = d.position_id
                if not pid:
                    continue
                if pid not in pos_map:
                    pos_map[pid] = {"entry": None, "exit": None}
                if d.entry == 0:  # DEAL_ENTRY_IN
                    pos_map[pid]["entry"] = d
                elif d.entry == 1:  # DEAL_ENTRY_OUT
                    pos_map[pid]["exit"] = d

            for pid, pdata in pos_map.items():
                entry_deal = pdata["entry"]
                exit_deal = pdata["exit"]
                target_deal = exit_deal or entry_deal
                if not target_deal:
                    continue

                raw_sym = target_deal.symbol
                spec = resolve(raw_sym)
                clean_sym = spec.canonical if spec else raw_sym.replace(".i#", "").replace("#", "")
                
                # Determine buy/sell side accurately
                if entry_deal:
                    side = "BUY" if entry_deal.type == 0 else "SELL"
                elif exit_deal:
                    side = "BUY" if exit_deal.type == 1 else "SELL"
                else:
                    side = "BUY"

                entry_p = float(entry_deal.price) if entry_deal else float(target_deal.price)
                vol = float(target_deal.volume)
                pnl = float(exit_deal.profit) if exit_deal else 0.0
                target_time = exit_deal.time if exit_deal else target_deal.time
                dt_str = datetime.fromtimestamp(target_time, timezone.utc).isoformat()
                
                # Determine executor (BOT vs MANUAL)
                magic_num = getattr(target_deal, "magic", 0)
                raw_comment = str(exit_deal.comment if exit_deal else target_deal.comment or "")
                comment_lower = raw_comment.lower()
                
                if magic_num == 888999 or "jarvis_auto" in comment_lower or "ai" in comment_lower:
                    exec_label = "BOT (AI)"
                elif magic_num == 0 or "manual" in comment_lower or "desk" in comment_lower:
                    exec_label = "MANUAL"
                else:
                    exec_label = "BOT (AI)" if magic_num > 0 else "MANUAL"

                sl_val = 0.0
                tp_val = 0.0
                if "[sl" in raw_comment:
                    try:
                        sl_val = float(raw_comment.split("[sl")[1].split("]")[0].strip())
                    except Exception:
                        pass
                if "[tp" in raw_comment:
                    try:
                        tp_val = float(raw_comment.split("[tp")[1].split("]")[0].strip())
                    except Exception:
                        pass

                # Check if ticket already exists
                cur = conn.cursor()
                cur.execute("SELECT id FROM executed_trades WHERE ticket = ?", (pid,))
                row = cur.fetchone()
                if not row:
                    regime_str = "TREND_BULL" if side == "BUY" else "TREND_BEAR"
                    conn.execute('''
                        INSERT INTO executed_trades (ticket, symbol, action, entry_price, sl, tp, volume, timestamp, ai_score, regime, expected_value, executor)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (pid, clean_sym, side, entry_p, sl_val, tp_val, vol, dt_str, 85.0, regime_str, pnl, exec_label))
                else:
                    # Update realized PnL, executor, and close timestamp for completed positions
                    conn.execute('''
                        UPDATE executed_trades 
                        SET expected_value = ?, executor = ?, timestamp = ?, 
                            sl = CASE WHEN ? > 0 THEN ? ELSE sl END, 
                            tp = CASE WHEN ? > 0 THEN ? ELSE tp END
                        WHERE ticket = ?
                    ''', (pnl, exec_label, dt_str, sl_val, sl_val, tp_val, tp_val, pid))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to sync MT5 history: {e}")

    def fetch_recent_trades(self, limit=100):
        self.sync_mt5_history(days=30, limit=limit)
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM executed_trades ORDER BY datetime(timestamp) DESC, id DESC LIMIT ?", (limit,))
            columns = [description[0] for description in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []

TRADE_DB = SQLiteTradeDB()
