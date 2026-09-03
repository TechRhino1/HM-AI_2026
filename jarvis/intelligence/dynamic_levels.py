"""
JARVIS AI 4.0 — Dynamic Risk & Volatility-Adaptive Levels Engine.
Computes purely structural, volatility-adaptive SL, TP, and scale-out plans with zero static tables:
- Dynamic Structural SL: Outer boundary of recent swing point / Order Block / FVG + dynamic volatility buffer.
- Liquidity-Anchored Dynamic TP: Nearest opposing unmitigated Order Block / FVG / Liquidity Pool (1.5R to 3.5R+).
- Adaptive Scale-Out Plan: Structural first target, regime-adaptive partial volume %, and ATR runner trailing.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger("JARVIS_DynamicLevels")

from jarvis.data.schemas import (
    MarketContext,
    RegimeOutput,
    MarketRegime
)
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.intelligence.institutional_entry_engine import InstitutionalEntryEngine, INSTITUTIONAL_ENTRY_ENGINE


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
        gamma_spread: float = 0.05,   # Spread ratio sensitivity coefficient
        institutional_engine: Optional[InstitutionalEntryEngine] = None
    ):
        self.alpha_base = alpha_base
        self.beta_vol = beta_vol
        self.gamma_spread = gamma_spread
        self.institutional_engine = institutional_engine or INSTITUTIONAL_ENTRY_ENGINE

    def calculate_levels(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        tentative_bias: str,
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5,
        trade_style: str = "SWING",
        mtf_data: Optional[Dict[str, Any]] = None
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
        style = (trade_style or getattr(context, "trade_style", "SWING") or "SWING").upper()

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

        # Anti-Wick Shield: Asset-specific buffer to absorb stop-hunts and wick probes
        is_gold = ("XAU" in sym_name) or ("GOLD" in sym_name) or (getattr(spec, "asset_class", "").upper() == "COMMODITY")
        is_crypto = getattr(spec, "is_crypto", False) or (getattr(spec, "asset_class", "").upper() == "CRYPTO") or ("BTC" in sym_name)
        anti_wick_mult = 0.35 if is_gold else (0.45 if is_crypto else 0.18)
        anti_wick_buffer = atr * anti_wick_mult
        effective_buffer = max(dynamic_buffer, anti_wick_buffer)

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
                # Anti-Wick Shield: Outer structural support boundary min(candidate_anchors)
                anchors_in_range = [a for a in candidate_anchors if (entry_price - a) <= 3.0 * atr]
                anchor = min(anchors_in_range) if anchors_in_range else min(candidate_anchors)
                struct_sl_dist = (entry_price - anchor) + effective_buffer
            else:
                struct_sl_dist = atr * (0.85 if is_strong_trend else (1.0 if is_ranging else 0.95)) + effective_buffer

            if style == "SCALP":
                sl_dist = min(0.65 * atr, max(0.20 * atr, struct_sl_dist * 0.5))
                min_target_rr = 1.3
                asym_rr = 2.0
            elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
                sl_dist = min(1.30 * atr, max(0.45 * atr, struct_sl_dist * 0.8))
                min_target_rr = 1.8
                asym_rr = 2.8
            else:  # SWING
                max_swing_sl = 2.80 * atr if (is_gold or is_crypto) else 2.50 * atr
                sl_dist = min(max_swing_sl, max(0.75 * atr, struct_sl_dist))
                min_target_rr = 2.5
                asym_rr = 4.2

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

            # Filter targets offering at least min_target_rr
            valid_targets = [t for t in opposing_targets if (t - entry_price) >= (risk_dist * min_target_rr)]

            if valid_targets:
                target_cand = min(valid_targets)
                max_tp_mult = asym_rr * (1.25 if is_strong_trend else 1.0)
                tp_dist = min(target_cand - entry_price, risk_dist * max_tp_mult)
            else:
                tp_dist = risk_dist * asym_rr

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
                # Anti-Wick Shield: Outer structural resistance boundary max(candidate_anchors)
                anchors_in_range = [a for a in candidate_anchors if (a - entry_price) <= 3.0 * atr]
                anchor = max(anchors_in_range) if anchors_in_range else max(candidate_anchors)
                struct_sl_dist = (anchor - entry_price) + effective_buffer + spread_dist
            else:
                struct_sl_dist = atr * (0.85 if is_strong_trend else (1.0 if is_ranging else 0.95)) + effective_buffer + spread_dist

            if style == "SCALP":
                sl_dist = min(0.65 * atr + spread_dist, max(0.20 * atr, struct_sl_dist * 0.5))
                min_target_rr = 1.3
                asym_rr = 2.0
            elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
                sl_dist = min(1.30 * atr + spread_dist, max(0.45 * atr, struct_sl_dist * 0.8))
                min_target_rr = 1.8
                asym_rr = 2.8
            else:  # SWING
                max_swing_sl = 2.80 * atr if (is_gold or is_crypto) else 2.50 * atr
                sl_dist = min(max_swing_sl + spread_dist, max(0.75 * atr, struct_sl_dist))
                min_target_rr = 2.5
                asym_rr = 4.2

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

            # Filter targets offering at least min_target_rr
            valid_targets = [t for t in opposing_targets if (entry_price - t) >= (risk_dist * min_target_rr)]

            if valid_targets:
                target_cand = max(valid_targets)
                max_tp_mult = asym_rr * (1.25 if is_strong_trend else 1.0)
                tp_dist = min(entry_price - target_cand, risk_dist * max_tp_mult)
            else:
                tp_dist = risk_dist * asym_rr

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
            if style == "SCALP":
                sl_dist = 0.40 * atr
                tp_dist = sl_dist * 2.0
                rr_ratio = 2.0
            elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
                sl_dist = 0.80 * atr
                tp_dist = sl_dist * 2.8
                rr_ratio = 2.8
            else:
                sl_dist = atr * 1.5
                tp_dist = sl_dist * 4.2
                rr_ratio = 4.2
            sl_price = round(entry_price + sl_dist if is_bear_tilt else entry_price - sl_dist, digits)
            tp_price = round(entry_price - tp_dist if is_bear_tilt else entry_price + tp_dist, digits)
            risk_dist = abs(entry_price - sl_price)
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

        base_result = {
            "bias": tentative_bias,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "tp1_price": first_target_price,
            "tp2_price": tp_price,
            "risk_dist": risk_dist,
            "tp_dist": tp_dist,
            "rr_ratio": rr_ratio,
            "first_target_price": first_target_price,
            "first_target_volume_pct": first_target_volume_pct,
            "runner_trail_distance_atr": runner_trail_distance_atr,
            "entry_type": "DYNAMIC_STRUCTURAL",
            "protocol_details": {"protocol": "BASELINE_DYNAMIC_LEVELS"}
        }

        # Seamless Institutional Entry Engine Integration
        if mtf_data and any(isinstance(v, pd.DataFrame) and not v.empty for v in mtf_data.values()):
            try:
                inst_res = self.institutional_engine.calculate_entry_and_levels(
                    context=context,
                    regime=regime,
                    tentative_bias=tentative_bias,
                    trade_style=style,
                    mtf_data=mtf_data
                )
                if inst_res and isinstance(inst_res, dict):
                    return {
                        "bias": tentative_bias,
                        "entry_price": inst_res.get("entry_price", entry_price),
                        "sl_price": inst_res.get("sl_price", sl_price),
                        "tp_price": inst_res.get("tp_price", tp_price),
                        "tp1_price": inst_res.get("tp1_price", first_target_price),
                        "tp2_price": inst_res.get("tp2_price", tp_price),
                        "risk_dist": inst_res.get("risk_dist", risk_dist),
                        "tp_dist": inst_res.get("tp_dist", tp_dist),
                        "rr_ratio": inst_res.get("rr_ratio", rr_ratio),
                        "first_target_price": inst_res.get("tp1_price", first_target_price),
                        "first_target_volume_pct": inst_res.get("first_target_volume_pct", first_target_volume_pct),
                        "runner_trail_distance_atr": inst_res.get("runner_trail_atr", runner_trail_distance_atr),
                        "entry_type": inst_res.get("entry_type", "INSTITUTIONAL"),
                        "protocol_details": inst_res.get("protocol_details", {})
                    }
            except Exception as e:
                logger.warning(f"InstitutionalEntryEngine execution failed: {e}. Falling back to baseline dynamic levels.")

        return base_result

    def calculate_manual_trade_levels(
        self,
        symbol: str,
        action: str,
        current_price: Optional[float] = None,
        trade_style: str = "SWING"
    ) -> Dict[str, Any]:
        """
        Calculate AI-assisted dynamic structural SL, TP1, and TP2 for manual orders.
        Anchor beyond recent swing / OB / FVG + dynamic ATR buffer.
        TP1: 1.0R - 1.2R, TP2: 2.0R - 3.5R.
        """
        norm_action = (action or "BUY").strip().upper()
        if norm_action not in ("BUY", "SELL"):
            norm_action = "BUY"

        spec = resolve_symbol(symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        spread_pips = spec.typical_spread_pips if getattr(spec, "typical_spread_pips", 0) > 0 else 2.0
        spread_dist = spread_pips * pip_size

        ctx: Optional[MarketContext] = None
        mtf_data_fetched: Optional[Dict[str, Any]] = None

        # 1. Try to retrieve context from global state manager if available
        try:
            from jarvis.application.state_manager import GLOBAL_STATE
            ctx = GLOBAL_STATE.get_market_context(symbol)
        except Exception as ex:
            logger.debug(f"Could not retrieve context from GLOBAL_STATE for {symbol}: {ex}")

        # 2. If no context in state manager, build fresh context via DataFeedEngine + MarketContextEngine
        if ctx is None or ctx.current_price <= 0:
            try:
                from jarvis.market.data_feed import DataFeedEngine
                from jarvis.market.market_context import MarketContextEngine
                df_engine = DataFeedEngine()
                mtf = df_engine.fetch_multi_timeframe(symbol, trade_style=trade_style)
                if mtf and any(not df.empty for df in mtf.values()):
                    mtf_data_fetched = mtf
                    ce = MarketContextEngine()
                    ctx = ce.build_context(
                        symbol,
                        mtf,
                        current_spread_pips=spread_pips,
                        max_allowed_spread_pips=spec.max_spread_pips,
                        trade_style=trade_style
                    )
            except Exception as ex:
                logger.debug(f"Could not build context via data feed for {symbol}: {ex}")

        # 3. Fallback synthetic context if live data is unavailable
        if ctx is None or ctx.current_price <= 0:
            price = current_price if (current_price is not None and current_price > 0) else (spec.base_price if spec.base_price > 0 else 100.0)
            typical_atr_pct = getattr(spec, "typical_atr_pct", 0.5)
            typical_atr = price * (typical_atr_pct / 100.0) if typical_atr_pct > 0 else (price * 0.005)
            atr = typical_atr if typical_atr > 0 else (price * 0.005)

            from jarvis.data.schemas import (
                StructureContext, LiquidityContext, VolatilityContext,
                MomentumContext, SessionContext
            )
            st = StructureContext(
                bias="BULLISH" if norm_action == "BUY" else "BEARISH",
                swing_high=round(price + (atr * 1.5), digits),
                swing_low=round(price - (atr * 1.5), digits),
                supply_zone=(round(price + (atr * 2.0), digits), round(price + (atr * 2.5), digits)),
                demand_zone=(round(price - (atr * 2.5), digits), round(price - (atr * 2.0), digits)),
                order_blocks=[],
                fair_value_gaps=[]
            )
            liq = LiquidityContext(
                buy_side_liquidity=round(price + (atr * 2.0), digits),
                sell_side_liquidity=round(price - (atr * 2.0), digits)
            )
            vol = VolatilityContext(
                atr=atr,
                current_spread_pips=spread_pips
            )
            mom = MomentumContext(
                trend_score=30 if norm_action == "BUY" else -30,
                adx=25.0
            )
            sess = SessionContext()
            ctx = MarketContext(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                current_price=price,
                bid=price,
                ask=price + spread_dist,
                structure=st,
                liquidity=liq,
                volatility=vol,
                momentum=mom,
                session=sess
            )

        # If custom current_price is provided, anchor the context around it
        if current_price is not None and current_price > 0:
            ctx.current_price = float(current_price)
            ctx.bid = float(current_price)
            ctx.ask = float(current_price + spread_dist)

        # 4. Classify regime or use default
        try:
            from jarvis.intelligence.regime_engine import MarketRegimeClassifier
            rc = MarketRegimeClassifier()
            regime = rc.classify_regime(ctx)
        except Exception:
            regime = RegimeOutput(
                primary_regime=MarketRegime.TREND_BULL if norm_action == "BUY" else MarketRegime.TREND_BEAR,
                probabilities={"trend_bull": 0.8, "trend_bear": 0.2} if norm_action == "BUY" else {"trend_bull": 0.2, "trend_bear": 0.8},
                confidence=0.80
            )

        # 5. Calculate structural levels using the mathematical engine
        levels = self.calculate_levels(
            context=ctx,
            regime=regime,
            tentative_bias=norm_action,
            trade_style=trade_style,
            mtf_data=mtf_data_fetched
        )

        entry = float(levels.get("entry_price", ctx.current_price))
        sl = float(levels.get("sl_price", 0.0))
        tp = float(levels.get("tp_price", 0.0))
        risk_dist = float(levels.get("risk_dist", abs(entry - sl)))
        if risk_dist <= 0:
            atr_val = ctx.volatility.atr if ctx.volatility.atr > 0 else (entry * 0.005)
            risk_dist = max(pip_size * 5, atr_val * 1.2)
            sl = round(entry - risk_dist if norm_action == "BUY" else entry + risk_dist, digits)

        rr = float(levels.get("rr_ratio", 2.0))

        # Calculate dynamic TP1 (1.0R - 1.2R) and dynamic TP2 (2.0R - 3.5R)
        first_target = levels.get("tp1_price") or levels.get("first_target_price")
        if first_target is not None and first_target > 0:
            if norm_action == "BUY" and first_target > entry:
                tp1 = round(float(first_target), digits)
            elif norm_action == "SELL" and first_target < entry:
                tp1 = round(float(first_target), digits)
            else:
                tp1 = round(entry + (risk_dist * 1.1) if norm_action == "BUY" else entry - (risk_dist * 1.1), digits)
        else:
            tp1 = round(entry + (risk_dist * 1.1) if norm_action == "BUY" else entry - (risk_dist * 1.1), digits)

        tp2 = round(tp, digits) if tp > 0 else (round(entry + (risk_dist * 2.5), digits) if norm_action == "BUY" else round(entry - (risk_dist * 2.5), digits))

        return {
            "sl": float(sl),
            "tp": float(tp2),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "risk_dist": float(risk_dist),
            "rr": float(rr),
            "entry_price": float(entry),
            "bias": norm_action,
            "entry_type": levels.get("entry_type", "MANUAL_LIMIT"),
            "protocol_details": levels.get("protocol_details", {})
        }


DYNAMIC_LEVELS_ENGINE = DynamicRiskAndLevelsEngine()

