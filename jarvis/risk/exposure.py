"""
JARVIS AI 3.0 — Portfolio Exposure & Margin Management Engine.
Enforces limits on total concurrent positions, per-symbol exposures, and maximum margin utilization.
"""
from typing import List, Dict, Any
from jarvis.data.schemas import PositionSnapshot, AccountSnapshot

class ExposureManager:
    def __init__(self, max_open_positions: int = 3, max_symbol_positions: int = 1, max_margin_utilization_pct: float = 40.0):
        self.max_open_positions = max_open_positions
        self.max_symbol_positions = max_symbol_positions
        self.max_margin_utilization_pct = max_margin_utilization_pct

    def check_exposure(
        self,
        symbol: str,
        positions: List[PositionSnapshot],
        account: AccountSnapshot
    ) -> Dict[str, Any]:
        breaches = []

        if len(positions) >= self.max_open_positions:
            breaches.append(f"Max Concurrent Positions reached ({len(positions)} >= {self.max_open_positions}).")

        symbol_count = sum(1 for p in positions if p.symbol == symbol)
        if symbol_count >= self.max_symbol_positions:
            breaches.append(f"Max Exposure for symbol {symbol} reached ({symbol_count} >= {self.max_symbol_positions}).")

        if account.equity > 0:
            margin_pct = (account.margin / account.equity) * 100.0
            if margin_pct >= self.max_margin_utilization_pct:
                breaches.append(f"High Margin Utilization ({margin_pct:.1f}% >= {self.max_margin_utilization_pct:.1f}%).")

        return {
            "passed": len(breaches) == 0,
            "open_positions": len(positions),
            "symbol_count": symbol_count,
            "breaches": breaches
        }
