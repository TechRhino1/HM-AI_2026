"""
JARVIS AI 3.0 — Dynamic Context-Aware Strategy Selection Engine.
Features:
- Micro-Account Adaptive Sizing & Execution (< $100 Equity)
- Standard Institutional Multi-Strategy Suite (>= $100 Equity - Fully Preserved)
"""
from typing import Dict, Any, List, Optional
from jarvis.data.schemas import MarketRegime, RegimeOutput, MarketContext
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.data.symbol_registry import resolve as resolve_symbol

class StrategySelector:
    """Selects and ranks candidate trading strategies with dynamic context awareness & reinforcement learning."""
    
    STRATEGIES = [
        "MICRO_ACCOUNT_ADAPTIVE",
        "TREND_FOLLOWING",
        "TREND_PULLBACK",
        "BREAKOUT_EXPANSION",
        "LIQUIDITY_SWEEP_REVERSAL",
        "RANGE_MEAN_REVERSION",
        "CHOCH_STRUCTURAL_REVERSAL"
    ]

    def __init__(self, bandit: Optional[StrategyBandit] = None):
        self.bandit = bandit or StrategyBandit()

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
        bandit_boosts = self.bandit.get_strategy_boosts()
        weights = {
            "MICRO_ACCOUNT_ADAPTIVE": 0.00,
            "TREND_FOLLOWING": 0.15 * bandit_boosts.get("TREND_FOLLOWING", 1.0),
            "TREND_PULLBACK": 0.15 * bandit_boosts.get("TREND_PULLBACK", 1.0),
            "BREAKOUT_EXPANSION": 0.15 * bandit_boosts.get("BREAKOUT_EXPANSION", 1.0),
            "LIQUIDITY_SWEEP_REVERSAL": 0.15 * bandit_boosts.get("LIQUIDITY_SWEEP_REVERSAL", 1.0),
            "RANGE_MEAN_REVERSION": 0.20 * bandit_boosts.get("RANGE_MEAN_REVERSION", 1.0),
            "CHOCH_STRUCTURAL_REVERSAL": 0.20 * bandit_boosts.get("CHOCH_STRUCTURAL_REVERSAL", 1.0)
        }

        # First normalization after bandit boosts
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        # =========================================================================
        # 2.5. ASSET-CLASS SPECIFIC STRATEGY PROFILES
        # Core insight: Gold trends, Forex mean-reverts, BTC swings.
        # One-size-fits-all is why Forex loses with trend-following.
        # =========================================================================
        asset_class = "UNKNOWN"
        if context and hasattr(context, "symbol"):
            try:
                spec = resolve_symbol(context.symbol)
                asset_class = getattr(spec, "asset_class", "").upper()
            except Exception:
                pass

        if asset_class == "FOREX" and r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY]:
            # Forex in range → 75% mean reversion, 25% liquidity sweep reversal
            weights["RANGE_MEAN_REVERSION"] = 0.75
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.25
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.00
            weights["TREND_FOLLOWING"] = 0.00
            weights["TREND_PULLBACK"] = 0.00
            weights["BREAKOUT_EXPANSION"] = 0.00
            weights["MICRO_ACCOUNT_ADAPTIVE"] = 0.00
            total = sum(weights.values())
            if total > 0:
                return {k: round(v / total, 3) for k, v in weights.items()}

        elif asset_class == "FOREX" and r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
            # Forex in trend → strictly trade pullbacks to institutional discount/premium & sweeps (never chase breakouts)
            weights["TREND_PULLBACK"] = 0.60
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.25
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.15
            weights["TREND_FOLLOWING"] = 0.00
            weights["RANGE_MEAN_REVERSION"] = 0.00
            weights["BREAKOUT_EXPANSION"] = 0.00
            weights["MICRO_ACCOUNT_ADAPTIVE"] = 0.00
            total = sum(weights.values())
            if total > 0:
                return {k: round(v / total, 3) for k, v in weights.items()}

        elif asset_class == "COMMODITY" and r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
            # Gold in trend → heavy trend-following (Gold's natural behavior)
            weights["TREND_FOLLOWING"] = 0.50
            weights["TREND_PULLBACK"] = 0.30
            weights["BREAKOUT_EXPANSION"] = 0.15
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.05
            weights["RANGE_MEAN_REVERSION"] = 0.00
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.00
            weights["MICRO_ACCOUNT_ADAPTIVE"] = 0.00

        elif asset_class == "CRYPTO":
            # BTC → balanced swing/momentum with higher conviction thresholds
            weights["TREND_FOLLOWING"] = 0.30
            weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.25
            weights["BREAKOUT_EXPANSION"] = 0.20
            weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.15
            weights["TREND_PULLBACK"] = 0.10
            weights["RANGE_MEAN_REVERSION"] = 0.00
            weights["MICRO_ACCOUNT_ADAPTIVE"] = 0.00

        if context:
            st = context.structure
            mom = context.momentum
            vol = context.volatility
            liq = context.liquidity

            # A. Structural Inversion (CHoCH) -> Priority #1 Reversal
            if st.choch and r in [MarketRegime.REVERSAL, MarketRegime.TRANSITION, MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
                weights["CHOCH_STRUCTURAL_REVERSAL"] += 0.60
                weights["LIQUIDITY_SWEEP_REVERSAL"] += 0.25
                weights["TREND_PULLBACK"] = 0.05
                weights["TREND_FOLLOWING"] = 0.05

            # B. Volatility Compression / Low ADX Range -> Range Mean Reversion & Sweeps
            elif r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY] or vol.state == "COMPRESSION" or mom.adx < 18:
                weights["RANGE_MEAN_REVERSION"] += 0.60
                weights["LIQUIDITY_SWEEP_REVERSAL"] += 0.30
                weights["TREND_PULLBACK"] = 0.05
                weights["BREAKOUT_EXPANSION"] = 0.00
                weights["TREND_FOLLOWING"] = 0.00

            # C. Established Sustained Trend -> Trend Pullback vs Trend Following (Avoid Counter-Trend Sweeps)
            elif r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
                if abs(mom.trend_score) > 40 and mom.adx > 22:
                    weights["TREND_FOLLOWING"] += 0.55
                    weights["TREND_PULLBACK"] += 0.35
                    weights["BREAKOUT_EXPANSION"] += 0.10
                    weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.00
                else:
                    weights["TREND_PULLBACK"] += 0.55
                    weights["TREND_FOLLOWING"] += 0.35
                    weights["BREAKOUT_EXPANSION"] += 0.10
                    weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.00

            # D. Institutional Liquidity Sweep (Inside Range or at Extremes)
            elif liq.sweep_detected or (st.discount_premium_zone == "PREMIUM" and mom.rsi > 70) or (st.discount_premium_zone == "DISCOUNT" and mom.rsi < 30):
                weights["LIQUIDITY_SWEEP_REVERSAL"] += 0.55
                weights["CHOCH_STRUCTURAL_REVERSAL"] += 0.25
                weights["RANGE_MEAN_REVERSION"] += 0.15
                weights["TREND_PULLBACK"] = 0.05

            # E. Break of Structure with Momentum Confirmation -> Breakout Expansion
            elif (st.bos and (mom.adx >= 22 or r == MarketRegime.BREAKOUT)) or (mom.adx >= 28 and abs(mom.trend_score) >= 55):
                weights["BREAKOUT_EXPANSION"] += 0.50
                weights["TREND_FOLLOWING"] += 0.30
                weights["TREND_PULLBACK"] = 0.15
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.05
        else:
            if r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
                weights["TREND_FOLLOWING"] = 0.40
                weights["TREND_PULLBACK"] = 0.40
                weights["BREAKOUT_EXPANSION"] = 0.15
            elif r == MarketRegime.BREAKOUT:
                weights["BREAKOUT_EXPANSION"] = 0.65
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.20
            elif r in [MarketRegime.REVERSAL, MarketRegime.TRANSITION]:
                weights["CHOCH_STRUCTURAL_REVERSAL"] = 0.50
                weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30
            elif r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY]:
                weights["RANGE_MEAN_REVERSION"] = 0.60
                weights["LIQUIDITY_SWEEP_REVERSAL"] = 0.30

        # Regime-conditional blacklisting
        if r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY]:
            weights["TREND_FOLLOWING"] = 0.0
            weights["BREAKOUT_EXPANSION"] = 0.0
        elif r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
            weights["RANGE_MEAN_REVERSION"] = 0.0

        total = sum(weights.values())
        if total > 0:
            return {k: round(v / total, 3) for k, v in weights.items()}
        return {k: 0.0 for k in weights}
