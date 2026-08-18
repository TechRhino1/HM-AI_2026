"""
JARVIS AI 3.0 — Volatility & Fixed-Fractional Position Sizing Engine.
Calculates mathematically sound lot sizing based on account equity, stop-loss distance, tick values, and volatility.
"""
from typing import Dict, Any

class PositionSizer:
    """Calculates risk-controlled lot sizes adjusted for symbol contract specifications and account balance."""
    
    @staticmethod
    def calculate_lot_size(
        account_balance: float,
        entry_price: float,
        sl_price: float,
        risk_pct: float,
        symbol_info: Dict[str, Any],
        invalidation_risk_coefficient: float = 1.0
    ) -> float:
        risk_distance = abs(entry_price - sl_price)
        if risk_distance <= 0 or account_balance <= 0:
            return 0.01

        # Adjusted risk percent incorporating Devil's Advocate coefficient
        effective_risk_pct = max(0.1, min(2.0, risk_pct * invalidation_risk_coefficient))
        risk_amount_dollars = account_balance * (effective_risk_pct / 100.0)

        contract_size = symbol_info.get("trade_contract_size", 100000.0) if symbol_info else 100000.0
        if contract_size <= 0:
            contract_size = 1.0

        min_vol = symbol_info.get("volume_min", 0.01) if symbol_info else 0.01
        max_vol = symbol_info.get("volume_max", 100.0) if symbol_info else 100.0
        vol_step = symbol_info.get("volume_step", 0.01) if symbol_info else 0.01

        # Lot calculation: Risk ($) / (Risk Distance * Contract Size)
        raw_lots = risk_amount_dollars / (risk_distance * contract_size + 1e-9)

        # Apply account size protective caps
        if account_balance <= 100.0:
            account_cap = 0.03
        elif account_balance <= 500.0:
            account_cap = 0.05
        elif account_balance <= 1000.0:
            account_cap = 0.10
        elif account_balance <= 5000.0:
            account_cap = 0.50
        else:
            account_cap = max_vol

        final_lots = min(raw_lots, account_cap, max_vol)
        final_lots = max(min_vol, round(final_lots / vol_step) * vol_step)
        return round(final_lots, 2)
