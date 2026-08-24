import logging
from typing import Dict, Any

logger = logging.getLogger("JARVIS_PositionSizer")

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
        current_drawdown_pct: float = 0.0,
        model_confidence: float = 0.60,
        pattern_sample_size: int = 0,
        portfolio_heat_multiplier: float = 1.0,
        is_second_trade: bool = False
    ) -> float:
        risk_distance = abs(entry_price - sl_price)
        if risk_distance <= 0 or account_balance <= 0:
            return 0.01

        # Adjust risk_pct based on volatility and drawdown
        sym_name = str(symbol_info.get("name", "") if symbol_info else "").upper()
        is_high_vol = any(x in sym_name for x in ["XAU", "GOLD", "BTC", "OIL", "US30", "NAS100"])
        if is_high_vol:
            risk_pct *= 0.85

        if atr_ratio > 1.5:
            risk_pct *= 0.70  # Reduce risk by 30%
            
        if current_drawdown_pct > 5.0:
            risk_pct *= 0.50  # Halve risk

        # Adaptive Second-Trade position discount: scale to 75% to prevent overconcentration
        if is_second_trade:
            risk_pct *= 0.75

        # Portfolio heat scaling (e.g. 1.0x Normal, 0.75x Moderate, 0.50x High)
        risk_pct *= max(0.25, min(1.0, portfolio_heat_multiplier))

        # Conviction scaling: high conviction (>=75%) scales up to 1.35x; marginal confidence (<55%) scales down to 0.70x
        conviction_factor = max(0.70, min(1.35, (model_confidence / 0.60)))

        # P3: Dedicated Evidence Strength / Sample Size Scaling
        # Well-evidenced patterns (N>=30) get a modest boost; thinly evidenced (N=3-4) receive a slight caution buffer
        if pattern_sample_size >= 30:
            evidence_factor = 1.10
        elif pattern_sample_size >= 15:
            evidence_factor = 1.05
        elif pattern_sample_size >= 5:
            evidence_factor = 1.00
        elif pattern_sample_size >= 3:
            evidence_factor = 0.90
        else:
            evidence_factor = 1.00

        combined_scaler = max(0.65, min(1.40, conviction_factor * evidence_factor))

        # Adjusted risk percent incorporating Devil's Advocate coefficient and combined conviction/evidence scaling
        effective_risk_pct = max(0.1, min(2.0, risk_pct * invalidation_risk_coefficient * combined_scaler))
        risk_amount_dollars = account_balance * (effective_risk_pct / 100.0)

        contract_size = symbol_info.get("trade_contract_size", 100000.0) if symbol_info else 100000.0
        if contract_size <= 0:
            contract_size = 1.0

        min_vol = symbol_info.get("volume_min", 0.01) if symbol_info else 0.01
        max_vol = symbol_info.get("volume_max", 100.0) if symbol_info else 100.0
        vol_step = symbol_info.get("volume_step", 0.01) if symbol_info else 0.01

        # Smooth continuous formula
        raw_lots = risk_amount_dollars / (risk_distance * contract_size + 1e-9)

        # §8: Detect when raw_lots is below broker minimum volume floor
        if raw_lots < min_vol:
            actual_risk_dollars = min_vol * risk_distance * contract_size
            actual_risk_pct = (actual_risk_dollars / (account_balance + 1e-9)) * 100.0
            if actual_risk_pct > (effective_risk_pct * 1.5):
                logger.info(
                    f"Position sizing minimum lot floor active: raw_lots={raw_lots:.4f} < min={min_vol}. "
                    f"Effective risk adjusted to {actual_risk_pct:.2f}% (${actual_risk_dollars:.2f}) on ${account_balance:.2f} equity."
                )

        # Clamp between min_vol and max_vol
        final_lots = max(min_vol, min(raw_lots, max_vol))

        # Keep hard floor of 0.01 for micro accounts < $40
        if account_balance < 40.0:
            final_lots = min(final_lots, 0.01)

        # Volume step rounding
        final_lots = max(min_vol, round(final_lots / vol_step) * vol_step)
        return round(final_lots, 2)
