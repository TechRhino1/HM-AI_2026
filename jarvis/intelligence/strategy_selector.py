"""
JARVIS AI 3.0 — Strategy Selection Engine.
Maps causal market regimes to strategy suitability probability distributions.
"""
from typing import Dict, Any, List
from jarvis.data.schemas import MarketRegime, RegimeOutput

class StrategySelector:
    """Selects and ranks candidate trading strategies based on current market regime."""
    
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
            weights["TREND_PULLBACK"] = 0.45
            weights["TREND_FOLLOWING"] = 0.35
            weights["BREAKOUT_EXPANSION"] = 0.10
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.05
            weights["RANGE_MEAN_REVERSION"] = 0.03
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.02

        elif r == MarketRegime.BREAKOUT:
            weights["BREAKOUT_EXPANSION"] = 0.55
            weights["TREND_FOLLOWING"] = 0.25
            weights["TREND_PULLBACK"] = 0.10
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.05
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.03
            weights["RANGE_MEAN_REVERSION"] = 0.02

        elif r == MarketRegime.RANGE or r == MarketRegime.LOW_VOLATILITY:
            weights["RANGE_MEAN_REVERSION"] = 0.50
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.10
            weights["TREND_PULLBACK"] = 0.05
            weights["TREND_FOLLOWING"] = 0.03
            weights["BREAKOUT_EXPANSION"] = 0.02

        elif r == MarketRegime.REVERSAL or r == MarketRegime.TRANSITION:
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.45
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.35
            weights["RANGE_MEAN_REVERSION"] = 0.10
            weights["TREND_PULLBACK"] = 0.05
            weights["BREAKOUT_EXPANSION"] = 0.03
            weights["TREND_FOLLOWING"] = 0.02

        elif r == MarketRegime.HIGH_VOLATILITY or r == MarketRegime.EVENT_RISK:
            # Defensive flat distribution
            weights = {k: 0.166 for k in weights}

        total = sum(weights.values())
        return {k: round(v / total, 3) for k, v in weights.items()}
