"""
JARVIS AI 3.0 — Drawdown & Daily Loss Monitoring Engine.
Enforces hard daily loss caps and maximum portfolio drawdown limits to guarantee capital preservation.
"""
from typing import Dict, Any

class DrawdownGuard:
    def __init__(self, max_daily_loss_pct: float = 4.0, max_total_drawdown_pct: float = 10.0):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_total_drawdown_pct = max_total_drawdown_pct
        self.daily_start_equity: float = 0.0
        self.peak_equity: float = 0.0

    def update_equity_benchmarks(self, current_equity: float, current_balance: float):
        if self.daily_start_equity <= 0 or current_balance > self.daily_start_equity:
            self.daily_start_equity = current_balance
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

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
