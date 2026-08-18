"""
JARVIS AI 3.0 — Dynamic Context-Aware Strategy Selection Engine.
Features:
- Micro-Account Adaptive Sizing & Execution (< $100 Equity)
- Standard Institutional Multi-Strategy Suite (>= $100 Equity - Fully Preserved)
"""
from typing import Dict, Any, List, Optional
from jarvis.data.schemas import MarketRegime, RegimeOutput, MarketContext

class StrategySelector:
    """Selects and ranks candidate trading strategies with dynamic context awareness."""
    
    STRATEGIES = [
        "MICRO_ACCOUNT_ADAPTIVE",
        "TREND_FOLLOWING",
        "TREND_PULLBACK",
        "BREAKOUT_EXPANSION",
        "LIQUIDITY_SWEEP_REVERSAL",
        "RANGE_MEAN_REVERSION",
        "CHOCH_STRUCTURAL_REVERSAL"
    ]

    def select_strategy_probabilities(
        self,
        regime: RegimeOutput,
        context: Optional[MarketContext] = None,
        account_equity: float = 10000.0
    ) -> Dict[str, float]:
        r = regime.primary_regime

        # =========================================================================
        # 1. MICRO-ACCOUNT ADAPTIVE MODE (Active ONLY when Equity < $100.00)
        # =========================================================================
        if account_equity < 100.0:
            return {
                "MICRO_ACCOUNT_ADAPTIVE": 0.85,
                "CHOCH_STRUCTURAL_REVERSAL": 0.05,
                "BREAKOUT_EXPANSION": 0.05,
                "LIQUIDITY_SWEEP_REVERSAL": 0.05,
                "TREND_FOLLOWING": 0.00,
                "TREND_PULLBACK": 0.00,
                "RANGE_MEAN_REVERSION": 0.00
            }

        # =========================================================================
        # 2. STANDARD INSTITUTIONAL MODE (Active when Equity >= $100.00 - UNTOUCHED)
        # =========================================================================
        weights = {
            "MICRO_ACCOUNT_ADAPTIVE": 0.00,
            "TREND_FOLLOWING": 0.15,
            "TREND_PULLBACK": 0.15,
            "BREAKOUT_EXPANSION": 0.15,
            "LIQUIDITY_SWEEP_REVERSAL": 0.15,
            "RANGE_MEAN_REVERSION": 0.20,
            "CHOCH_STRUCTURAL_REVERSAL": 0.20
        }

        # Evaluate Dynamic Context for standard mode
        if context:
            st = context.structure
            mom = context.momentum
            vol = context.volatility
            liq = context.liquidity

            # A. Structural Inversion (CHoCH) -> Priority #1
            if st.choch:
                weights["CHOCH_STRUCTURAL_REVERSAL"] += 0.55
                weights["BREAKOUT_EXPANSION"] += 0.25
                weights["TREND_PULLBACK"] = 0.05
                weights["TREND_FOLLOWING"] = 0.05

            # B. Break of Structure / High Momentum Acceleration -> Breakout Expansion
            elif st.bos or (mom.adx >= 28 and abs(mom.trend_score) >= 55):
                weights["BREAKOUT_EXPANSION"] += 0.50
                weights["TREND_FOLLOWING"] += 0.30
                weights["TREND_PULLBACK"] = 0.10
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.05

            # C. Institutional Liquidity Sweep -> Sweep Reversal
            elif liq.sweep_detected or (st.discount_premium_zone == "PREMIUM" and mom.rsi > 70) or (st.discount_premium_zone == "DISCOUNT" and mom.rsi < 30):
                weights["LIQUIDITY_SWEEP_REVERSAL"] += 0.50
                weights["CHOCH_STRUCTURAL_REVERSAL"] += 0.25
                weights["RANGE_MEAN_REVERSION"] += 0.15
                weights["TREND_PULLBACK"] = 0.05

            # D. Volatility Compression / Low ADX Range -> Range Mean Reversion
            elif vol.state == "COMPRESSION" or mom.adx < 18 or r == MarketRegime.RANGE:
                weights["RANGE_MEAN_REVERSION"] += 0.55
                weights["LIQUIDITY_SWEEP_REVERSAL"] += 0.25
                weights["TREND_PULLBACK"] = 0.10
                weights["BREAKOUT_EXPANSION"] = 0.05

            # E. Smooth Sustained Trend -> Trend Following vs Trend Pullback
            elif r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
                if abs(mom.trend_score) > 40:
                    weights["TREND_FOLLOWING"] += 0.45
                    weights["TREND_PULLBACK"] += 0.35
                else:
                    weights["TREND_PULLBACK"] += 0.45
                    weights["TREND_FOLLOWING"] += 0.35
        else:
            if r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
                weights["TREND_FOLLOWING"] = 0.40
                weights["TREND_PULLBACK"] = 0.35
                weights["BREAKOUT_EXPANSION"] = 0.15
            elif r == MarketRegime.BREAKOUT:
                weights["BREAKOUT_EXPANSION"] = 0.60
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.20
            elif r in [MarketRegime.REVERSAL, MarketRegime.TRANSITION]:
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.50
                weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30
            elif r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY]:
                weights["RANGE_MEAN_REVERSION"] = 0.55
                weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.25

        total = sum(weights.values())
        return {k: round(v / total, 3) for k, v in weights.items()}
