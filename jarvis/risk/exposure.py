"""
JARVIS AI 3.0 — Portfolio Exposure & Margin Management Engine.
Enforces limits on total concurrent positions, per-symbol exposures, and maximum margin utilization.
"""
from typing import List, Dict, Any
from jarvis.data.schemas import PositionSnapshot, AccountSnapshot

class ExposureManager:
    def __init__(self, max_open_positions: int = 3, max_symbol_positions: int = 1, max_margin_utilization_pct: float = 40.0, max_notional_exposure_pct: float = 200.0):
        self.max_open_positions = max_open_positions
        self.max_symbol_positions = max_symbol_positions
        self.max_margin_utilization_pct = max_margin_utilization_pct
        self.max_notional_exposure_pct = max_notional_exposure_pct

    def check_exposure(
        self,
        symbol: str,
        positions: List[PositionSnapshot],
        account: AccountSnapshot
    ) -> Dict[str, Any]:
        breaches = []

        symbol_count = sum(1 for p in positions if p.symbol == symbol)
        if symbol_count >= self.max_symbol_positions:
            breaches.append(f"Max Exposure for symbol {symbol} reached ({symbol_count} >= {self.max_symbol_positions}).")

        if account.equity > 0:
            margin_pct = (account.margin / account.equity) * 100.0
            if margin_pct >= self.max_margin_utilization_pct:
                breaches.append(f"High Margin Utilization ({margin_pct:.1f}% >= {self.max_margin_utilization_pct:.1f}%).")

            # Notional exposure calculation
            long_notional = 0.0
            short_notional = 0.0
            
            for pos in positions:
                contract_size = getattr(pos, 'contract_size', 100000.0)
                current_price = getattr(pos, 'current_price', getattr(pos, 'entry_price', 1.0))
                
                pos_notional = pos.volume * contract_size * current_price
                if getattr(pos, 'side', getattr(pos, 'type', '')).upper() in ('BUY', 'LONG', '0'):
                    long_notional += pos_notional
                else:
                    short_notional += pos_notional

            notional = long_notional + short_notional
            net_notional = abs(long_notional - short_notional)
            
            exposure_pct = (notional / account.equity) * 100.0
            
            if exposure_pct >= self.max_notional_exposure_pct:
                breaches.append(f"Max Notional Exposure reached ({exposure_pct:.1f}% >= {self.max_notional_exposure_pct:.1f}%).")

        return {
            "passed": len(breaches) == 0,
            "open_positions": len(positions),
            "symbol_count": symbol_count,
            "breaches": breaches,
            "exposure_pct": exposure_pct if account.equity > 0 else 0.0
        }
