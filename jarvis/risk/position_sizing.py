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
        invalidation_risk_coefficient: float = 1.0,
        atr_ratio: float = 1.0,
        current_drawdown_pct: float = 0.0
    ) -> float:
        risk_distance = abs(entry_price - sl_price)
        if risk_distance <= 0 or account_balance <= 0:
            return 0.01

        # Adjust risk_pct based on volatility and drawdown
        if atr_ratio > 1.5:
            risk_pct *= 0.70  # Reduce risk by 30%
            
        if current_drawdown_pct > 5.0:
            risk_pct *= 0.50  # Halve risk

        # Adjusted risk percent incorporating Devil's Advocate coefficient
        effective_risk_pct = max(0.1, min(2.0, risk_pct * invalidation_risk_coefficient))
        risk_amount_dollars = account_balance * (effective_risk_pct / 100.0)

        contract_size = symbol_info.get("trade_contract_size", 100000.0) if symbol_info else 100000.0
        if contract_size <= 0:
            contract_size = 1.0

        min_vol = symbol_info.get("volume_min", 0.01) if symbol_info else 0.01
        max_vol = symbol_info.get("volume_max", 100.0) if symbol_info else 100.0
        vol_step = symbol_info.get("volume_step", 0.01) if symbol_info else 0.01

        # Smooth continuous formula
        raw_lots = risk_amount_dollars / (risk_distance * contract_size + 1e-9)

        # Clamp between min_vol and max_vol
        final_lots = max(min_vol, min(raw_lots, max_vol))

        # Keep hard floor of 0.01 for micro accounts < $40
        if account_balance < 40.0:
            final_lots = min(final_lots, 0.01)

        # Volume step rounding
        final_lots = max(min_vol, round(final_lots / vol_step) * vol_step)
        return round(final_lots, 2)
