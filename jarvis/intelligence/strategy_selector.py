"""
JARVIS AI 4.0 — Dynamic Context-Aware Strategy Selection Engine.
Features:
- Micro-Account Adaptive Sizing & Execution (< $100 Equity)
- Context-Aware Bayesian Probability Weighting Engine driven by Sweep Detection, Volume Delta, and ADX Slope.
"""
from typing import Dict, Any, List, Optional
import logging
import numpy as np

logger = logging.getLogger("JARVIS_StrategySelector")

from jarvis.data.schemas import MarketRegime, RegimeOutput, MarketContext
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.data.symbol_registry import resolve as resolve_symbol


class StrategySelector:
    """Selects and ranks candidate trading strategies with dynamic context-aware Bayesian weighting."""
    
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
        """
        Calculate context-aware Bayesian posterior probabilities across candidate strategies.
        Eliminates static tables with dynamic likelihood updating.
        """
        r = regime.primary_regime

        # 1. MICRO-ACCOUNT ADAPTIVE MODE (Active ONLY when Equity < $100.00)
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

        # 2. STANDARD INSTITUTIONAL MODE (Equity >= $100.00)
        # 2.1 Asset-Class Profile Identification
        symbol_name = ""
        asset_class = "UNKNOWN"
        if context and hasattr(context, "symbol"):
            symbol_name = str(context.symbol).upper()
            try:
                spec = resolve_symbol(context.symbol)
                asset_class = getattr(spec, "asset_class", "").upper()
            except Exception:
                pass

        is_jpy = "JPY" in symbol_name
        is_crypto = (asset_class == "CRYPTO") or any(k in symbol_name for k in ["BTC", "ETH", "SOL"])
        is_gold = any(k in symbol_name for k in ["XAU", "GOLD"])
        is_oil = any(k in symbol_name for k in ["WTI", "OIL", "CRUDE"])
        is_commodity = (asset_class == "COMMODITY") or is_gold or is_oil
        is_index = (asset_class == "INDEX") or any(k in symbol_name for k in ["US500", "NAS100", "US30", "SPX", "NDX", "DJ"])
        is_gbp = "GBP" in symbol_name
        is_forex_major = (asset_class == "FOREX") and not is_jpy and not is_gbp

        # 2.2 Bayesian Prior Probability Distribution
        prior_weights = {
            "MICRO_ACCOUNT_ADAPTIVE": 0.0,
            "TREND_FOLLOWING": 1.0,
            "TREND_PULLBACK": 1.0,
            "BREAKOUT_EXPANSION": 0.0 if (is_forex_major or is_gbp) else 1.0,
            "LIQUIDITY_SWEEP_REVERSAL": 1.0,
            "RANGE_MEAN_REVERSION": 1.0,
            "CHOCH_STRUCTURAL_REVERSAL": 1.0
        }

        # Asset-Class Prior Calibration
        if is_index:
            # Equity Indices: Strong Trend Continuation (2.5), Pullbacks (2.2), and Breakouts (1.8)
            prior_weights["TREND_FOLLOWING"] = 2.5
            prior_weights["TREND_PULLBACK"] = 2.2
            prior_weights["BREAKOUT_EXPANSION"] = 1.8
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 1.2
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 1.2
            prior_weights["RANGE_MEAN_REVERSION"] = 0.4
        elif is_jpy:
            # USDJPY: Persistent trend continuation (2.4) and pullbacks (2.2)
            prior_weights["TREND_FOLLOWING"] = 2.4
            prior_weights["TREND_PULLBACK"] = 2.2
            prior_weights["RANGE_MEAN_REVERSION"] = 1.1
            prior_weights["BREAKOUT_EXPANSION"] = 0.0
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 1.0
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 1.2
        elif is_gold or is_crypto:
            # Gold & Crypto: Liquidity sweeps (2.8) and CHOCH reversals (2.5) beat fakeouts
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 2.8
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 2.5
            prior_weights["TREND_PULLBACK"] = 2.2
            prior_weights["TREND_FOLLOWING"] = 0.15
            prior_weights["BREAKOUT_EXPANSION"] = 0.4
            prior_weights["RANGE_MEAN_REVERSION"] = 0.5
        elif is_oil:
            # Crude Oil (WTI): Supply/Demand zone sweeps (2.4), pullbacks (2.2), range reversion (1.6)
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 2.4
            prior_weights["TREND_PULLBACK"] = 2.2
            prior_weights["RANGE_MEAN_REVERSION"] = 1.6
            prior_weights["TREND_FOLLOWING"] = 1.2
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 1.5
            prior_weights["BREAKOUT_EXPANSION"] = 0.8
        elif is_gbp:
            # Cable: London sweep reversals (2.5), range mean reversion (2.0), no naked breakouts
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 2.5
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 2.2
            prior_weights["RANGE_MEAN_REVERSION"] = 2.0
            prior_weights["TREND_PULLBACK"] = 1.8
            prior_weights["TREND_FOLLOWING"] = 0.2
            prior_weights["BREAKOUT_EXPANSION"] = 0.0
        elif is_forex_major:
            # EURUSD, AUDUSD, USDCHF: Pullback (2.0), Range Reversion (1.8), Sweep (1.6)
            prior_weights["TREND_PULLBACK"] = 2.0
            prior_weights["RANGE_MEAN_REVERSION"] = 1.8
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = 1.6
            prior_weights["TREND_FOLLOWING"] = 1.0
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = 1.2
            prior_weights["BREAKOUT_EXPANSION"] = 0.0

        # 2.3 Regime Bayesian Likelihood Updating
        reg_conf = getattr(regime, "confidence", 0.75)

        if r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
            prior_weights["TREND_FOLLOWING"] *= (1.8 + reg_conf)
            prior_weights["TREND_PULLBACK"] *= (2.0 + reg_conf)
            prior_weights["BREAKOUT_EXPANSION"] *= (1.2 if not is_forex_major else 0.0)
            prior_weights["RANGE_MEAN_REVERSION"] = 0.0
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= 0.3
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= 0.5

        elif r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY, MarketRegime.CONSOLIDATION, MarketRegime.COMPRESSION]:
            prior_weights["RANGE_MEAN_REVERSION"] *= (2.2 + reg_conf)
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= (1.8 + reg_conf)
            prior_weights["TREND_FOLLOWING"] = 0.0
            prior_weights["TREND_PULLBACK"] = 0.0
            prior_weights["BREAKOUT_EXPANSION"] = 0.0
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= 0.4

        elif r in [MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY, MarketRegime.POST_BREAKOUT]:
            if not is_forex_major:
                prior_weights["BREAKOUT_EXPANSION"] *= (2.4 + reg_conf)
            prior_weights["TREND_PULLBACK"] *= (1.8 + reg_conf)
            prior_weights["TREND_FOLLOWING"] *= (1.4 + reg_conf)
            prior_weights["RANGE_MEAN_REVERSION"] = 0.0
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= 0.6
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= 0.5

        elif r in [MarketRegime.REVERSAL, MarketRegime.TRANSITION, MarketRegime.LIQUIDITY_SWEEP]:
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= (2.2 + reg_conf)
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= (2.2 + reg_conf)
            prior_weights["TREND_PULLBACK"] *= 0.4
            prior_weights["TREND_FOLLOWING"] = 0.0
            prior_weights["RANGE_MEAN_REVERSION"] *= 0.3

        # 2.4 Context-Aware Bayesian Likelihood Factors
        if context:
            st = context.structure
            mom = context.momentum
            vol = context.volatility
            liq = context.liquidity

            # A. ADX Level & Slope Evidence
            adx_val = getattr(mom, "adx", 20.0)
            adx_slope = getattr(mom, "slope", 0.0)
            slope_boost = 1.25 if adx_slope > 0.05 else (0.85 if adx_slope < -0.05 else 1.0)

            if adx_val >= 25.0:
                prior_weights["TREND_PULLBACK"] *= (1.4 * slope_boost)
                prior_weights["TREND_FOLLOWING"] *= (1.3 * slope_boost)
                if adx_val >= 28.0 and not is_forex_major:
                    prior_weights["BREAKOUT_EXPANSION"] *= (1.4 * slope_boost)
                prior_weights["RANGE_MEAN_REVERSION"] *= 0.2
            elif adx_val < 20.0:
                prior_weights["RANGE_MEAN_REVERSION"] *= 1.6
                prior_weights["BREAKOUT_EXPANSION"] = 0.0
                prior_weights["TREND_FOLLOWING"] *= 0.3

            # B. Liquidity Sweep Detection & Magnitude Evidence
            if getattr(liq, "sweep_detected", False):
                sweep_mag = getattr(liq, "sweep_magnitude", 1.0)
                sweep_factor = 1.0 + min(2.5, max(0.5, sweep_mag))
                prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= (2.0 * sweep_factor)
                prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= (1.5 * sweep_factor)
                prior_weights["TREND_FOLLOWING"] *= 0.2

            # C. Order Flow Volume Delta Alignment Evidence
            of_data = getattr(context, "order_flow", {})
            if isinstance(of_data, dict):
                delta_score = float(of_data.get("delta_score", 0.0))
                if abs(delta_score) >= 25.0:
                    if not is_forex_major:
                        prior_weights["BREAKOUT_EXPANSION"] *= 1.3
                    prior_weights["TREND_FOLLOWING"] *= 1.3
                    prior_weights["TREND_PULLBACK"] *= 1.3
                if of_data.get("absorption_trap"):
                    prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= 1.6
                    prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= 1.4

            # D. Structural Inversion (CHoCH / BOS)
            if getattr(st, "choch", False):
                prior_weights["CHOCH_STRUCTURAL_REVERSAL"] *= 2.0
                prior_weights["LIQUIDITY_SWEEP_REVERSAL"] *= 1.5
            if getattr(st, "bos", False) and adx_val >= 22.0:
                prior_weights["TREND_PULLBACK"] *= 1.5
                prior_weights["TREND_FOLLOWING"] *= 1.3

            # E. Volatility State Constraints
            vol_state = getattr(vol, "state", "NORMAL").upper()
            if vol_state in ("COMPRESSION", "LOW_VOLATILITY"):
                if not is_commodity:
                    prior_weights["RANGE_MEAN_REVERSION"] *= 1.5
                prior_weights["BREAKOUT_EXPANSION"] = 0.0
            elif vol_state in ("EXPANSION", "EXTREME") and not is_forex_major:
                prior_weights["BREAKOUT_EXPANSION"] *= 1.5

        # 2.5 Strict Strategy Blacklists & Safeguards
        # Zero out BREAKOUT_EXPANSION unless momentum ADX >= 28 and BOS confirmed
        if context:
            adx_val = getattr(context.momentum, "adx", 0.0) if hasattr(context, "momentum") else 0.0
            bos_val = bool(getattr(context.structure, "bos", False)) if hasattr(context, "structure") else False
            if not (adx_val >= 28.0 and bos_val):
                prior_weights["BREAKOUT_EXPANSION"] = 0.0

        # Eliminate BREAKOUT_EXPANSION on Forex majors and GBP
        if is_forex_major or is_gbp:
            prior_weights["BREAKOUT_EXPANSION"] = 0.0

        # Master-Trader: For XAUUSD, BTCUSD, GBPUSD - zero out naked TREND_FOLLOWING
        # unless liquidity sweep detected or (BOS confirmed with strong trend_score >= 30.0)
        if is_commodity or is_crypto or is_gbp:
            sweep_detected = False
            bos_and_trend = False
            if context:
                sweep_detected = bool(getattr(context.liquidity, "sweep_detected", False)) if hasattr(context, "liquidity") else False
                bos = bool(getattr(context.structure, "bos", False)) if hasattr(context, "structure") else False
                trend_score = abs(float(getattr(context.momentum, "trend_score", 0.0))) if hasattr(context, "momentum") else 0.0
                bos_and_trend = bos and (trend_score >= 30.0)

            if not (sweep_detected or bos_and_trend):
                prior_weights["TREND_FOLLOWING"] = 0.0

        # Master-Trader Strategy Weighting Calibration:
        # For XAUUSD, BTCUSD, GBPUSD: Elevate LIQUIDITY_SWEEP_REVERSAL (2.8), CHOCH (2.5), and TREND_PULLBACK (2.0)
        # For USDJPY: Retain strong TREND_FOLLOWING (2.2) and TREND_PULLBACK (2.0)
        if is_jpy:
            prior_weights["TREND_FOLLOWING"] = max(prior_weights.get("TREND_FOLLOWING", 0.0), 2.2)
            prior_weights["TREND_PULLBACK"] = max(prior_weights.get("TREND_PULLBACK", 0.0), 2.0)
        elif is_commodity or is_crypto or is_gbp:
            prior_weights["LIQUIDITY_SWEEP_REVERSAL"] = max(prior_weights.get("LIQUIDITY_SWEEP_REVERSAL", 0.0), 2.8)
            prior_weights["CHOCH_STRUCTURAL_REVERSAL"] = max(prior_weights.get("CHOCH_STRUCTURAL_REVERSAL", 0.0), 2.5)
            prior_weights["TREND_PULLBACK"] = min(prior_weights.get("TREND_PULLBACK", 0.0), 2.0)

        # Hard blacklisting by regime
        if r in [MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY]:
            prior_weights["TREND_FOLLOWING"] = 0.0
            prior_weights["BREAKOUT_EXPANSION"] = 0.0
        elif r in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR]:
            prior_weights["RANGE_MEAN_REVERSION"] = 0.0

        # 2.6 Reinforcement Learning Bandit Boosts
        bandit_boosts = self.bandit.get_strategy_boosts()
        for s in prior_weights:
            prior_weights[s] *= bandit_boosts.get(s, 1.0)

        # 2.7 Posterior Probability Normalization
        total = sum(prior_weights.values())
        if total > 0:
            return {k: round(v / total, 3) for k, v in prior_weights.items()}
        return {k: 0.0 for k in prior_weights}
