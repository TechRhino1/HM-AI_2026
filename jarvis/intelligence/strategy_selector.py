"""
JARVIS AI 3.0 — Strategy Selection Engine.
Maps causal market regimes, fast structure shifts, and macro catalysts to strategy suitability probability distributions.
"""
from typing import Dict, Any, List
from jarvis.data.schemas import MarketRegime, RegimeOutput

class StrategySelector:
    """Selects and ranks candidate trading strategies based on current market regime & structure."""
    
    STRATEGIES = [
        "TREND_FOLLOWING",
        "TREND_PULLBACK",
        "BREAKOUT_EXPANSION",
        "LIQUIDITY_SWEEP_REVERSAL",
        "RANGE_MEAN_REVERSION",
        "CHOCH_STRUCTURAL_REVERSAL"
    ]

    def select_strategy_probabilities(self, regime: RegimeOutput) -> Dict[str, float]:
        r = regime.primary_regime

        weights = {
            "TREND_FOLLOWING": 0.10,
            "TREND_PULLBACK": 0.10,
            "BREAKOUT_EXPANSION": 0.10,
            "LIQUIDITY_SWEEP_REVERSAL": 0.10,
            "RANGE_MEAN_REVERSION": 0.10,
            "CHOCH_STRUCTURAL_REVERSAL": 0.10
        }

        if r == MarketRegime.TREND_BULL or r == MarketRegime.TREND_BEAR:
            weights["TREND_PULLBACK"] = 0.40
            weights["TREND_FOLLOWING"] = 0.30
            weights["BREAKOUT_EXPANSION"] = 0.15
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.10
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.03
            weights["RANGE_MEAN_REVERSION"] = 0.02

        elif r == MarketRegime.BREAKOUT:
            weights["BREAKOUT_EXPANSION"] = 0.60
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.20
            weights["TREND_FOLLOWING"] = 0.15
            weights["TREND_PULLBACK"] = 0.05
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.00
            weights["RANGE_MEAN_REVERSION"] = 0.00

        elif r == MarketRegime.REVERSAL or r == MarketRegime.TRANSITION:
            # Immediate capture of breakdowns and structural flips
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.50
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30
            weights["BREAKOUT_EXPANSION"] = 0.15
            weights["RANGE_MEAN_REVERSION"] = 0.05
            weights["TREND_PULLBACK"] = 0.00
            weights["TREND_FOLLOWING"] = 0.00

        elif r == MarketRegime.RANGE or r == MarketRegime.LOW_VOLATILITY:
            weights["RANGE_MEAN_REVERSION"] = 0.50
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.10
            weights["TREND_PULLBACK"] = 0.05
            weights["TREND_FOLLOWING"] = 0.03
            weights["BREAKOUT_EXPANSION"] = 0.02

        elif r == MarketRegime.HIGH_VOLATILITY or r == MarketRegime.EVENT_RISK:
            # High-volatility news breakdown mode
            weights["BREAKOUT_EXPANSION"] = 0.45
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.35
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.10
            weights["TREND_FOLLOWING"] = 0.10
            weights["TREND_PULLBACK"] = 0.00
            weights["RANGE_MEAN_REVERSION"] = 0.00

        total = sum(weights.values())
        return {k: round(v / total, 3) for k, v in weights.items()}
