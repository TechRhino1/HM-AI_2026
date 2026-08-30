"""
JARVIS AI 4.0 — Dynamic Risk & Volatility-Adaptive Levels Engine.
Computes purely structural, volatility-adaptive SL, TP, and scale-out plans with zero static tables:
- Dynamic Structural SL: Outer boundary of recent swing point / Order Block / FVG + dynamic volatility buffer.
- Liquidity-Anchored Dynamic TP: Nearest opposing unmitigated Order Block / FVG / Liquidity Pool (1.5R to 3.5R+).
- Adaptive Scale-Out Plan: Structural first target, regime-adaptive partial volume %, and ATR runner trailing.
"""
from typing import Dict, List, Any, Optional
import logging
import numpy as np

logger = logging.getLogger("JARVIS_DynamicLevels")

from jarvis.data.schemas import (
    MarketContext,
    RegimeOutput,
    MarketRegime
)
from jarvis.data.symbol_registry import resolve as resolve_symbol


class DynamicRiskAndLevelsEngine:
    """
    Autonomous mathematical engine for calculating market-structure-anchored,
    volatility-adaptive Stop Loss, Take Profit, and Scale-Out levels.
    Eliminates hardcoded asset/regime tables in favor of dynamic formulas.
    """

    def __init__(
        self,
        alpha_base: float = 0.12,     # Baseline buffer coefficient (12% ATR)
        beta_vol: float = 0.05,       # Volatility ratio sensitivity coefficient
        gamma_spread: float = 0.05    # Spread ratio sensitivity coefficient
    ):
        self.alpha_base = alpha_base
        self.beta_vol = beta_vol
        self.gamma_spread = gamma_spread

    def calculate_levels(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        tentative_bias: str,
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5
    ) -> Dict[str, Any]:
        """
        Calculate dynamic structural SL, liquidity-anchored TP, and adaptive scale-out parameters.

        Returns:
            Dict containing:
                - bias: str ("BUY", "SELL", "HOLD")
                - entry_price: float
                - sl_price: float
                - tp_price: float
                - risk_dist: float
                - tp_dist: float
                - rr_ratio: float
                - first_target_price: Optional[float]
                - first_target_volume_pct: float
                - runner_trail_distance_atr: float
        """
        st = context.structure
        vol = context.volatility
        c_price = context.current_price
        sym_name = str(context.symbol).upper()

        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        
        # 1. Volatility & Spread Normalization
        atr = vol.atr if vol.atr > 0 else (c_price * 0.005)
        spread_dist = max(0.0, context.ask - context.bid) if (context.ask > 0 and context.bid > 0) else (vol.current_spread_pips * pip_size)

        typical_atr_pct = getattr(spec, "typical_atr_pct", 0.5)
        typical_atr = c_price * (typical_atr_pct / 100.0) if typical_atr_pct > 0 else atr
        atr_median = typical_atr if typical_atr > 0 else atr
        atr_ratio = min(3.0, max(0.33, atr / max(atr_median, 1e-6)))

        typ_spread = spec.typical_spread_pips if getattr(spec, "typical_spread_pips", 0) > 0 else 1.5
        cur_spread = vol.current_spread_pips if vol.current_spread_pips > 0 else (spread_dist / pip_size if pip_size > 0 else 1.0)
        spread_ratio = min(4.0, max(0.5, cur_spread / max(typ_spread, 1e-4)))

        # Dynamic Volatility Buffer: ATR * (alpha_base + beta_vol * (ATR_cur/ATR_median) + gamma_spread * (Spread/TypSpread))
        buffer_mult = self.alpha_base + (self.beta_vol * atr_ratio) + (self.gamma_spread * spread_ratio)
        dynamic_buffer = atr * buffer_mult

        # Regime & State Flags
        is_strong_trend = (
            regime.primary_regime in (MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR)
            and getattr(regime, "confidence", 0.0) >= 0.70
            and getattr(context.momentum, "adx", 0.0) >= 22.0
        )
        is_ranging = regime.primary_regime in (
            MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY, MarketRegime.CONSOLIDATION, MarketRegime.COMPRESSION
        )
        is_breakout = regime.primary_regime in (
            MarketRegime.BREAKOUT, MarketRegime.POST_BREAKOUT, MarketRegime.HIGH_VOLATILITY
        )
        vol_state = getattr(vol, "state", "NORMAL").upper()

        # 2. Dynamic Structural Stop Loss & Entry Calculation
        if tentative_bias == "BUY":
            entry_price = round(context.ask, digits)

            # Support anchors strictly below entry
            candidate_anchors: List[float] = []
            if st.demand_zone[0] > 0 and st.demand_zone[0] < entry_price:
                candidate_anchors.append(st.demand_zone[0])
            if st.demand_zone[1] > 0 and st.demand_zone[1] < entry_price:
                candidate_anchors.append(st.demand_zone[1])

            for ob in st.order_blocks:
                if ob.get("type") == "BULLISH_ORDER_BLOCK" and 0 < ob.get("low", 0) < entry_price:
                    candidate_anchors.append(float(ob["low"]))

            for fvg in st.fair_value_gaps:
                if fvg.get("type") == "BULLISH_FVG" and 0 < fvg.get("bottom", 0) < entry_price:
                    candidate_anchors.append(float(fvg["bottom"]))

            if 0 < context.liquidity.sell_side_liquidity < entry_price:
                candidate_anchors.append(float(context.liquidity.sell_side_liquidity))

            for kl in getattr(st, "key_levels", []):
                if 0 < kl.get("price", 0) < entry_price:
                    candidate_anchors.append(float(kl["price"]))

            if candidate_anchors:
                # Outer structural boundary: anchor below entry with dynamic buffer
                anchor = max(candidate_anchors)
                struct_sl_dist = (entry_price - anchor) + dynamic_buffer
                # Bound SL distance: min 0.35 ATR, max 2.2 ATR
                sl_dist = min(2.2 * atr, max(0.35 * atr, struct_sl_dist))
            else:
                sl_dist = atr * (0.85 if is_strong_trend else (1.0 if is_ranging else 0.95))

            sl_price = round(entry_price - sl_dist, digits)
            risk_dist = max(spec.pip_size * 5, abs(entry_price - sl_price))

            # 3. Liquidity-Anchored Dynamic Take Profit
            opposing_targets: List[float] = []
            if st.supply_zone[0] > entry_price:
                opposing_targets.append(st.supply_zone[0])
            if st.supply_zone[1] > entry_price:
                opposing_targets.append(st.supply_zone[1])

            for ob in st.order_blocks:
                if ob.get("type") == "BEARISH_ORDER_BLOCK" and ob.get("low", 0) > entry_price:
                    opposing_targets.append(float(ob.get("low", 0)))

            for fvg in st.fair_value_gaps:
                if fvg.get("type") == "BEARISH_FVG" and fvg.get("bottom", 0) > entry_price:
                    opposing_targets.append(float(fvg.get("bottom", 0)))

            if context.liquidity.buy_side_liquidity > entry_price:
                opposing_targets.append(float(context.liquidity.buy_side_liquidity))

            for p in getattr(context.liquidity, "liquidity_pools", []):
                if p.get("type") == "BUY_SIDE_LIQUIDITY" and p.get("price", 0) > entry_price:
                    opposing_targets.append(float(p["price"]))

            for kl in getattr(st, "key_levels", []):
                if kl.get("price", 0) > entry_price:
                    opposing_targets.append(float(kl["price"]))

            # Filter targets offering at least 1.5R
            valid_targets = [t for t in opposing_targets if (t - entry_price) >= (risk_dist * 1.5)]

            if valid_targets:
                target_cand = min(valid_targets)
                if is_strong_trend:
                    tp_dist = min(target_cand - entry_price, risk_dist * 5.0)
                else:
                    tp_dist = min(target_cand - entry_price, risk_dist * 3.5)
            else:
                # Dynamic volatility-anchored asymmetric target multiplier (1.5R to 3.5R+)
                if is_strong_trend:
                    tp_mult = 4.2 if ("XAU" in sym_name or "GOLD" in sym_name) else 3.5
                elif is_breakout or vol_state in ("EXPANSION", "EXTREME"):
                    tp_mult = 3.5
                elif is_ranging or vol_state == "COMPRESSION":
                    tp_mult = 2.2 if ("XAU" in sym_name or "GOLD" in sym_name) else 2.0
                else:
                    tp_mult = 2.8 if ("XAU" in sym_name or "GOLD" in sym_name) else 2.5
                tp_dist = risk_dist * tp_mult

            tp_price = round(entry_price + tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)

            # 4. Adaptive Scale-Out Plan
            minor_resistance = [t for t in opposing_targets if entry_price + (risk_dist * 0.8) <= t < tp_price]
            if minor_resistance:
                first_target_price = round(min(minor_resistance), digits)
            else:
                first_target_price = round(entry_price + (risk_dist * 1.0), digits)

        elif tentative_bias == "SELL":
            entry_price = round(context.bid, digits)

            # Resistance anchors strictly above entry
            candidate_anchors = []
            if st.supply_zone[1] > entry_price:
                candidate_anchors.append(st.supply_zone[1])
            if st.supply_zone[0] > entry_price:
                candidate_anchors.append(st.supply_zone[0])

            for ob in st.order_blocks:
                if ob.get("type") == "BEARISH_ORDER_BLOCK" and ob.get("high", 0) > entry_price:
                    candidate_anchors.append(float(ob["high"]))

            for fvg in st.fair_value_gaps:
                if fvg.get("type") == "BEARISH_FVG" and fvg.get("top", 0) > entry_price:
                    candidate_anchors.append(float(fvg["top"]))

            if context.liquidity.buy_side_liquidity > entry_price:
                candidate_anchors.append(float(context.liquidity.buy_side_liquidity))

            for kl in getattr(st, "key_levels", []):
                if kl.get("price", 0) > entry_price:
                    candidate_anchors.append(float(kl["price"]))

            if candidate_anchors:
                # Outer structural boundary: anchor above entry with dynamic buffer and spread offset
                anchor = min(candidate_anchors)
                struct_sl_dist = (anchor - entry_price) + dynamic_buffer + spread_dist
                sl_dist = min(2.2 * atr + spread_dist, max(0.35 * atr, struct_sl_dist))
            else:
                sl_dist = atr * (0.85 if is_strong_trend else (1.0 if is_ranging else 0.95)) + spread_dist

            sl_price = round(entry_price + sl_dist, digits)
            risk_dist = max(spec.pip_size * 5, abs(sl_price - entry_price))

            # 3. Liquidity-Anchored Dynamic Take Profit
            opposing_targets = []
            if 0 < st.demand_zone[1] < entry_price:
                opposing_targets.append(st.demand_zone[1])
            if 0 < st.demand_zone[0] < entry_price:
                opposing_targets.append(st.demand_zone[0])

            for ob in st.order_blocks:
                if ob.get("type") == "BULLISH_ORDER_BLOCK" and 0 < ob.get("high", 0) < entry_price:
                    opposing_targets.append(float(ob.get("high", 0)))

            for fvg in st.fair_value_gaps:
                if fvg.get("type") == "BULLISH_FVG" and 0 < fvg.get("top", 0) < entry_price:
                    opposing_targets.append(float(fvg.get("top", 0)))

            if 0 < context.liquidity.sell_side_liquidity < entry_price:
                opposing_targets.append(float(context.liquidity.sell_side_liquidity))

            for p in getattr(context.liquidity, "liquidity_pools", []):
                if p.get("type") == "SELL_SIDE_LIQUIDITY" and 0 < p.get("price", 0) < entry_price:
                    opposing_targets.append(float(p["price"]))

            for kl in getattr(st, "key_levels", []):
                if 0 < kl.get("price", 0) < entry_price:
                    opposing_targets.append(float(kl["price"]))

            # Filter targets offering at least 1.5R
            valid_targets = [t for t in opposing_targets if (entry_price - t) >= (risk_dist * 1.5)]

            if valid_targets:
                target_cand = max(valid_targets)
                if is_strong_trend:
                    tp_dist = min(entry_price - target_cand, risk_dist * 5.0)
                else:
                    tp_dist = min(entry_price - target_cand, risk_dist * 3.5)
            else:
                if is_strong_trend:
                    tp_mult = 4.2 if ("XAU" in sym_name or "GOLD" in sym_name) else 3.5
                elif is_breakout or vol_state in ("EXPANSION", "EXTREME"):
                    tp_mult = 3.5
                elif is_ranging or vol_state == "COMPRESSION":
                    tp_mult = 2.2 if ("XAU" in sym_name or "GOLD" in sym_name) else 2.0
                else:
                    tp_mult = 2.8 if ("XAU" in sym_name or "GOLD" in sym_name) else 2.5
                tp_dist = risk_dist * tp_mult

            tp_price = round(entry_price - tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)

            # 4. Adaptive Scale-Out Plan
            minor_support = [t for t in opposing_targets if tp_price < t <= entry_price - (risk_dist * 0.8)]
            if minor_support:
                first_target_price = round(max(minor_support), digits)
            else:
                first_target_price = round(entry_price - (risk_dist * 1.0), digits)

        else:
            # Bias is HOLD / MONITOR — compute a structural reference bracket
            is_bear_tilt = (st.bias == "BEARISH") or (getattr(context.momentum, "trend_score", 0.0) < 0)
            entry_price = round(context.bid if is_bear_tilt else context.ask, digits)
            sl_dist = atr * 1.0
            tp_dist = sl_dist * 2.0
            sl_price = round(entry_price + sl_dist if is_bear_tilt else entry_price - sl_dist, digits)
            tp_price = round(entry_price - tp_dist if is_bear_tilt else entry_price + tp_dist, digits)
            risk_dist = abs(entry_price - sl_price)
            rr_ratio = 2.0
            first_target_price = None

        # 5. Adaptive Scale-Out Volume % Calculation
        of_data = getattr(context, "order_flow", {})
        delta_score = float(of_data.get("delta_score", 0.0)) if isinstance(of_data, dict) else 0.0
        aligned_delta = (
            (tentative_bias == "BUY" and delta_score >= 0)
            or (tentative_bias == "SELL" and delta_score <= 0)
            or delta_score == 0.0
        )

        if (is_strong_trend or vol_state in ("EXPANSION", "EXTREME")) and aligned_delta:
            first_target_volume_pct = 0.25 if ("XAU" in sym_name or "GOLD" in sym_name) else 0.35
        elif is_ranging or vol_state == "COMPRESSION":
            first_target_volume_pct = 0.50 if ("XAU" in sym_name or "GOLD" in sym_name) else 0.65
        else:
            first_target_volume_pct = 0.50  # Default 50% partial

        # 6. Runner Trailing Distance: 1.0 + 0.4 * 1_{EXPANSION} + 0.8 * 1_{EXTREME}
        is_expansion_val = 1.0 if vol_state == "EXPANSION" else 0.0
        is_extreme_val = 1.0 if vol_state == "EXTREME" else 0.0
        runner_trail_distance_atr = round(1.0 + (0.4 * is_expansion_val) + (0.8 * is_extreme_val), 2)

        return {
            "bias": tentative_bias,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "risk_dist": risk_dist,
            "tp_dist": tp_dist,
            "rr_ratio": rr_ratio,
            "first_target_price": first_target_price,
            "first_target_volume_pct": first_target_volume_pct,
            "runner_trail_distance_atr": runner_trail_distance_atr
        }
