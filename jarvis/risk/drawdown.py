"""
JARVIS AI 3.0 — Drawdown & Daily Loss Monitoring Engine.
Enforces hard daily loss caps and maximum portfolio drawdown limits to guarantee capital preservation.
"""
import sqlite3
import os
from typing import Dict, Any
from datetime import datetime, timezone

class DrawdownGuard:
    def __init__(self, max_daily_loss_pct: float = 4.0, max_total_drawdown_pct: float = 10.0):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_total_drawdown_pct = max_total_drawdown_pct
        self.daily_start_equity: float = 0.0
        self.peak_equity: float = 0.0
        self.db_path = "jarvis_drawdown_state.db"
        self._init_db()
        self._load_state()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS drawdown_state (
                    id INTEGER PRIMARY KEY,
                    daily_start_equity REAL,
                    peak_equity REAL,
                    last_saved_date TEXT
                )
            ''')
            conn.commit()

    def _load_state(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT daily_start_equity, peak_equity, last_saved_date FROM drawdown_state WHERE id = 1')
            row = cursor.fetchone()
            if row:
                self.daily_start_equity, self.peak_equity, last_saved_date_str = row
                
                # Check for daily reset
                current_date = datetime.now(timezone.utc).date().isoformat()
                if last_saved_date_str != current_date:
                    self.daily_start_equity = 0.0
                    self._save_state()
            else:
                conn.execute('INSERT INTO drawdown_state (id, daily_start_equity, peak_equity, last_saved_date) VALUES (1, 0.0, 0.0, ?)',
                            (datetime.now(timezone.utc).date().isoformat(),))
                conn.commit()

    def _save_state(self):
        with sqlite3.connect(self.db_path) as conn:
            current_date = datetime.now(timezone.utc).date().isoformat()
            conn.execute('''
                UPDATE drawdown_state
                SET daily_start_equity = ?, peak_equity = ?, last_saved_date = ?
                WHERE id = 1
            ''', (self.daily_start_equity, self.peak_equity, current_date))
            conn.commit()

    def update_equity_benchmarks(self, current_equity: float, current_balance: float):
        changed = False
        
        # True daily reset check in case process stays open across midnight
        current_date = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT last_saved_date FROM drawdown_state WHERE id = 1')
            row = cursor.fetchone()
            if row and row[0] != current_date:
                self.daily_start_equity = 0.0
                changed = True

        if self.daily_start_equity <= 0 or current_balance > self.daily_start_equity or self.daily_start_equity > current_balance * 1.5:
            self.daily_start_equity = current_balance
            changed = True
        if self.peak_equity <= 0 or current_equity > self.peak_equity or self.peak_equity > current_equity * 1.5:
            self.peak_equity = current_equity
            changed = True
            
        if changed:
            self._save_state()

    def get_risk_multiplier(self, current_equity: float) -> float:
        if self.peak_equity <= 0:
            return 1.0
        
        dd_pct = max(0.0, ((self.peak_equity - current_equity) / self.peak_equity) * 100.0)
        
        if dd_pct < 3.0:
            return 1.0
        elif dd_pct < 5.0:
            return 0.75
        elif dd_pct < 8.0:
            return 0.50
        else:
            return 0.0

    def check_limits(self, current_equity: float, current_balance: float) -> Dict[str, Any]:
        self.update_equity_benchmarks(current_equity, current_balance)

        # Daily loss check
        daily_loss_pct = 0.0
        if self.daily_start_equity > 0:
            daily_loss_pct = max(0.0, ((self.daily_start_equity - current_equity) / self.daily_start_equity) * 100.0)

        # Max drawdown check
        total_dd_pct = 0.0
        if self.peak_equity > 0:
            total_dd_pct = max(0.0, ((self.peak_equity - current_equity) / self.peak_equity) * 100.0)

        breaches = []
        if daily_loss_pct >= self.max_daily_loss_pct:
            breaches.append(f"Max Daily Loss breached ({daily_loss_pct:.2f}% >= {self.max_daily_loss_pct:.2f}%). Trading halted for today.")
        if total_dd_pct >= self.max_total_drawdown_pct:
            breaches.append(f"Max Portfolio Drawdown breached ({total_dd_pct:.2f}% >= {self.max_total_drawdown_pct:.2f}%). Circuit breaker triggered.")

        return {
            "passed": len(breaches) == 0,
            "daily_loss_pct": round(daily_loss_pct, 2),
            "total_dd_pct": round(total_dd_pct, 2),
            "breaches": breaches
        }
