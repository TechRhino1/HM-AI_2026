"""
JARVIS AI 3.0 — Probabilistic Causal Market Regime Classifier.
Classifies the market state into a probability distribution over distinct market regimes without future look-ahead.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np

from jarvis.data.schemas import MarketRegime, RegimeOutput, MarketContext

class MarketRegimeClassifier:
    """Causal, probabilistic regime classification engine."""
    
    def __init__(self):
        self._previous_regime: Optional[MarketRegime] = None
        self._regime_persistence: int = 0
    
    def classify_regime(self, context: MarketContext, macro_news_risk: bool = False) -> RegimeOutput:
        structure = context.structure
        momentum = context.momentum
        volatility = context.volatility
        liquidity = context.liquidity

        # Probability weights bucket initialization
        scores: Dict[str, float] = {
            MarketRegime.TREND_BULL.value: 0.05,
            MarketRegime.TREND_BEAR.value: 0.05,
            MarketRegime.WEAK_TREND.value: 0.05,
            MarketRegime.RANGE.value: 0.05,
            MarketRegime.BREAKOUT.value: 0.05,
            MarketRegime.REVERSAL.value: 0.05,
            MarketRegime.TRANSITION.value: 0.05,
            MarketRegime.HIGH_VOLATILITY.value: 0.05,
            MarketRegime.LOW_VOLATILITY.value: 0.05,
            MarketRegime.EVENT_RISK.value: 0.05
        }

        # 1. Macro News / Event Risk
        if macro_news_risk:
            scores[MarketRegime.EVENT_RISK.value] += 1.5

        # 2. Volatility State Impact
        if volatility.state == "EXTREME":
            scores[MarketRegime.HIGH_VOLATILITY.value] += 1.2
            scores[MarketRegime.BREAKOUT.value] += 0.3
        elif volatility.state == "COMPRESSION":
            scores[MarketRegime.LOW_VOLATILITY.value] += 0.9
            scores[MarketRegime.RANGE.value] += 0.6
        elif volatility.state == "EXPANSION":
            scores[MarketRegime.BREAKOUT.value] += 0.5

        # 3. Structure & BOS/CHoCH Impact
        if structure.bos:
            scores[MarketRegime.BREAKOUT.value] += 0.8
            if structure.bos_type == "BULLISH":
                scores[MarketRegime.TREND_BULL.value] += 0.6
            elif structure.bos_type == "BEARISH":
                scores[MarketRegime.TREND_BEAR.value] += 0.6
        elif structure.choch:
            scores[MarketRegime.REVERSAL.value] += 0.9
            scores[MarketRegime.TRANSITION.value] += 0.5
        elif structure.higher_highs and structure.higher_lows:
            scores[MarketRegime.TREND_BULL.value] += 0.8
        elif structure.lower_highs and structure.lower_lows:
            scores[MarketRegime.TREND_BEAR.value] += 0.8
        else:
            scores[MarketRegime.RANGE.value] += 0.4
            scores[MarketRegime.TRANSITION.value] += 0.3

        # 4. Momentum & ADX Trend Strength
        t_score = momentum.trend_score
        adx = momentum.adx
        if adx >= 25:
            # Scale score based on ADX strength (explosive momentum bonus)
            adx_multiplier = 1.0 + max(0.0, (adx - 25) / 10.0) 
            if t_score >= 50:
                scores[MarketRegime.TREND_BULL.value] += 1.5 * adx_multiplier
                if t_score >= 75:
                    scores[MarketRegime.TREND_BULL.value] += 1.0 * adx_multiplier
            elif t_score <= -50:
                scores[MarketRegime.TREND_BEAR.value] += 1.5 * adx_multiplier
                if t_score <= -75:
                    scores[MarketRegime.TREND_BEAR.value] += 1.0 * adx_multiplier
            else:
                scores[MarketRegime.WEAK_TREND.value] += 0.8
        elif adx < 18:
            scores[MarketRegime.RANGE.value] += 0.7
            scores[MarketRegime.WEAK_TREND.value] += 0.4

        # 5. Liquidity Sweeps
        if liquidity.sweep_detected:
            scores[MarketRegime.REVERSAL.value] += 0.7
            scores[MarketRegime.TRANSITION.value] += 0.3

        # Softmax normalization of probabilities
        exp_vals = np.exp(np.array(list(scores.values())))
        probs_array = exp_vals / np.sum(exp_vals)
        
        regime_probs: Dict[str, float] = {}
        for (k, _), p in zip(scores.items(), probs_array):
            regime_probs[k] = round(float(p), 3)

        # Primary regime is the argmax
        sorted_regimes = sorted(regime_probs.items(), key=lambda x: x[1], reverse=True)
        primary_str, highest_p = sorted_regimes[0]
        primary_regime = MarketRegime(primary_str)

        # Confidence metric derived from top-1 vs top-2 entropy margin
        second_p = sorted_regimes[1][1] if len(sorted_regimes) > 1 else 0.0
        confidence = min(0.98, max(0.40, round(highest_p + (highest_p - second_p) * 0.5, 2)))

        regime_transition = False
        if self._previous_regime is not None and self._previous_regime != primary_regime:
            regime_transition = True
            self._regime_persistence = 0
        elif self._previous_regime is not None and self._previous_regime == primary_regime:
            self._regime_persistence += 1

        self._previous_regime = primary_regime

        return RegimeOutput(
            primary_regime=primary_regime,
            probabilities=regime_probs,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            regime_transition=regime_transition,
            regime_persistence=self._regime_persistence
        )
