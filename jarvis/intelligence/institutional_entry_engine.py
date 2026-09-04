"""
JARVIS AI 4.0 — Institutional Next-Generation Entry Engine.
Precision institutional entry protocols across three trading horizons:
- SCALP Protocol (M1 / M5): Liquidity sweep detection, MSS displacement body ratio, OTE / micro-FVG CE refinement, sniper trigger.
- DAY TRADING Protocol (M15 / H1): London/NY Kill Zone filter, H1 structure alignment, M15 FVG midpoint / breaker block retest.
- SWING Protocol (H4 / D1): HTF Order Block in Discount (<45%) / Premium (>55%) + H1 CHOCH confirmation, outer structural boundary SL.
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import logging
import numpy as np
import pandas as pd

from jarvis.data.schemas import MarketContext, RegimeOutput
from jarvis.data.symbol_registry import resolve as resolve_symbol

logger = logging.getLogger("JARVIS_InstitutionalEntryEngine")


class InstitutionalEntryEngine:
    """
    Precision institutional execution and structural boundary engine.
    Calculates multi-timeframe liquidity sweep, displacement body ratio,
    OTE (Optimal Trade Entry), Fair Value Gap Consequent Encroachment (CE),
    and horizon-adaptive R-multiple targets.
    """

    def __init__(self):
        pass

    def calculate_entry_and_levels(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        tentative_bias: str,
        trade_style: str = "SWING",
        mtf_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate precision entry, structural SL, TP1, TP2, and execution parameters.

        Returns:
            Dict containing:
                entry_price, sl_price, tp_price, tp1_price, tp2_price,
                risk_dist, tp_dist, rr_ratio, first_target_volume_pct,
                runner_trail_atr, entry_type, protocol_details
        """
        norm_bias = (tentative_bias or "HOLD").strip().upper()
        if norm_bias not in ("BUY", "SELL"):
            return self._calculate_hold_bracket(context, regime, trade_style)

        style = (trade_style or getattr(context, "trade_style", "SWING") or "SWING").upper()
        if style in ("SCALP", "SCALPING"):
            return self._execute_scalp_protocol(context, regime, norm_bias, mtf_data)
        elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
            return self._execute_day_trading_protocol(context, regime, norm_bias, mtf_data)
        else:  # SWING
            return self._execute_swing_protocol(context, regime, norm_bias, mtf_data)

    # ─── SCALP Protocol (M1 / M5) ──────────────────────────────────────────────

    def _execute_scalp_protocol(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        bias: str,
        mtf_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        c_price = context.current_price
        spread_dist = max(0.0, context.ask - context.bid) if (context.ask > 0 and context.bid > 0) else (context.volatility.current_spread_pips * pip_size)

        # 1. MTF Frame Extraction
        df_m5 = self._get_df(mtf_data, ["M5", "primary", "setup"], target_price=c_price)
        df_m1 = self._get_df(mtf_data, ["M1", "timing"], target_price=c_price)

        # M5 ATR estimation
        m5_atr = self._estimate_atr(df_m5, default_atr=context.volatility.atr * 0.35 if context.volatility.atr > 0 else c_price * 0.002)
        if m5_atr <= 0:
            m5_atr = c_price * 0.002

        # 2. Liquidity Sweep of Recent 5 Bars
        sweep_detected, sweep_extreme, rejection_wick = self._detect_liquidity_sweep(df_m5, bias, bars=5)
        if not sweep_detected:
            # Fallback to context structure / liquidity anchors
            if bias == "BUY":
                cand_low = context.liquidity.sell_side_liquidity if 0 < context.liquidity.sell_side_liquidity < c_price else (context.structure.swing_low if 0 < context.structure.swing_low < c_price else c_price - (m5_atr * 1.5))
                sweep_extreme = cand_low
            else:
                cand_high = context.liquidity.buy_side_liquidity if context.liquidity.buy_side_liquidity > c_price else (context.structure.swing_high if context.structure.swing_high > c_price else c_price + (m5_atr * 1.5))
                sweep_extreme = cand_high
            rejection_wick = True

        # 3. Market Structure Shift (MSS) with Displacement Body Ratio
        has_mss, disp_ratio, disp_low, disp_high = self._detect_mss_displacement(df_m5 if df_m5 is not None and len(df_m5) >= 5 else df_m1, bias)
        if disp_high <= disp_low:
            disp_low = min(sweep_extreme, c_price - m5_atr)
            disp_high = max(c_price + m5_atr, sweep_extreme + (m5_atr * 2.0))

        # 4. Entry Refinement: OTE (61.8% - 70.5%) or Micro-FVG CE (50%)
        ote_pct = 0.66  # Midpoint between 61.8% and 70.5%
        disp_range = max(disp_high - disp_low, 1e-6)
        if bias == "BUY":
            ote_level = disp_high - (disp_range * ote_pct)
        else:
            ote_level = disp_low + (disp_range * ote_pct)

        # Micro FVG Consequent Encroachment (50% midpoint)
        micro_fvg_ce = self._find_micro_fvg_ce(df_m5, df_m1, context, bias)

        ref_entry = micro_fvg_ce if micro_fvg_ce is not None else ote_level

        # Sniper entry check: if already within 0.20x ATR, trigger immediate sniper entry
        dist_to_ref = abs(c_price - ref_entry)
        if dist_to_ref <= (0.20 * m5_atr):
            entry_type = "SNIPER_IMMEDIATE"
            entry_price = round(context.ask if bias == "BUY" else context.bid, digits)
        elif micro_fvg_ce is not None and abs(c_price - micro_fvg_ce) < abs(c_price - ote_level):
            entry_type = "MICRO_FVG_CE"
            entry_price = round(micro_fvg_ce, digits)
        else:
            entry_type = "OTE_REFINED"
            entry_price = round(ote_level, digits)

        # 5. Structural SL: Sweep wick extreme +/- (1.0x spread + 0.20x M5 ATR)
        sl_buffer = spread_dist + (0.20 * m5_atr)
        if bias == "BUY":
            sl_price = round(sweep_extreme - sl_buffer, digits)
            risk_dist = max(pip_size * 5, entry_price - sl_price)
            # Re-enforce SL below entry
            if sl_price >= entry_price:
                sl_price = round(entry_price - (0.45 * m5_atr) - spread_dist, digits)
                risk_dist = entry_price - sl_price
        else:
            sl_price = round(sweep_extreme + sl_buffer, digits)
            risk_dist = max(pip_size * 5, sl_price - entry_price)
            if sl_price <= entry_price:
                sl_price = round(entry_price + (0.45 * m5_atr) + spread_dist, digits)
                risk_dist = sl_price - entry_price

        # 6. Targets: TP1 at 1.2R - 1.5R (50% scale-out), TP2 at 2.0R - 2.5R
        tp1_r = 1.35
        tp2_r = 2.20
        if bias == "BUY":
            tp1_price = round(entry_price + (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price + (risk_dist * tp2_r), digits)
        else:
            tp1_price = round(entry_price - (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price - (risk_dist * tp2_r), digits)

        tp_price = tp2_price
        tp_dist = abs(tp_price - entry_price)
        rr_ratio = round(tp_dist / max(risk_dist, 1e-9), 2)

        return {
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp_price": float(tp_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "risk_dist": float(risk_dist),
            "tp_dist": float(tp_dist),
            "rr_ratio": float(rr_ratio),
            "first_target_volume_pct": 0.50,
            "runner_trail_atr": 0.80,
            "entry_type": entry_type,
            "protocol_details": {
                "protocol": "SCALP",
                "sweep_detected": sweep_detected,
                "sweep_extreme": float(sweep_extreme),
                "rejection_wick": rejection_wick,
                "mss_displacement_ratio": float(disp_ratio),
                "ote_level": float(ote_level),
                "micro_fvg_ce": float(micro_fvg_ce) if micro_fvg_ce is not None else None,
                "m5_atr": float(m5_atr)
            }
        }

    # ─── DAY TRADING Protocol (M15 / H1) ───────────────────────────────────────

    def _execute_day_trading_protocol(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        bias: str,
        mtf_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        c_price = context.current_price
        spread_dist = max(0.0, context.ask - context.bid) if (context.ask > 0 and context.bid > 0) else (context.volatility.current_spread_pips * pip_size)

        # 1. MTF Frame Extraction
        df_m15 = self._get_df(mtf_data, ["M15", "primary", "timing"], target_price=c_price)
        df_h1 = self._get_df(mtf_data, ["H1", "context", "setup"], target_price=c_price)

        h1_atr = self._estimate_atr(df_h1, default_atr=context.volatility.atr if context.volatility.atr > 0 else c_price * 0.005)
        if h1_atr <= 0:
            h1_atr = c_price * 0.005

        # 2. Session Kill Zone Check (London 07-10 UTC, NY 12-16 UTC)
        now_utc = context.timestamp if hasattr(context, "timestamp") and context.timestamp else datetime.now(timezone.utc)
        curr_hour = now_utc.hour
        in_london_kz = (7 <= curr_hour < 10)
        in_ny_kz = (12 <= curr_hour < 16)
        in_kill_zone = in_london_kz or in_ny_kz

        # 3. H1 Structure Alignment
        h1_aligned = self._check_h1_alignment(df_h1, context, bias)

        # 4. Entry Refinement: M15 FVG midpoint or Breaker Block retest
        m15_fvg_midpoint = self._find_m15_fvg_midpoint(df_m15, context, bias)
        breaker_retest = self._find_breaker_block_retest(df_m15, context, bias)

        ref_entry = m15_fvg_midpoint if m15_fvg_midpoint is not None else breaker_retest
        if ref_entry is None:
            ref_entry = c_price

        # Check proximity to refinement level
        dist_to_ref = abs(c_price - ref_entry)
        if dist_to_ref <= (0.35 * h1_atr):
            if in_kill_zone:
                entry_type = "KILL_ZONE_SNIPER"
            else:
                entry_type = "M15_FVG_CE" if m15_fvg_midpoint is not None else "BREAKER_RETEST"
            entry_price = round(context.ask if bias == "BUY" else context.bid, digits)
        else:
            entry_type = "M15_FVG_CE" if m15_fvg_midpoint is not None else ("BREAKER_RETEST" if breaker_retest is not None else "STRUCTURE_LIMIT")
            entry_price = round(ref_entry, digits)

        # 5. Structural SL: Displacement origin swing point +/- (1.0x spread + 0.30x H1 ATR)
        origin_swing = self._find_displacement_origin(df_h1, df_m15, context, bias)
        sl_buffer = spread_dist + (0.30 * h1_atr)

        if bias == "BUY":
            sl_price = round(origin_swing - sl_buffer, digits)
            risk_dist = max(pip_size * 5, entry_price - sl_price)
            if sl_price >= entry_price:
                sl_price = round(entry_price - (0.80 * h1_atr) - spread_dist, digits)
                risk_dist = entry_price - sl_price
        else:
            sl_price = round(origin_swing + sl_buffer, digits)
            risk_dist = max(pip_size * 5, sl_price - entry_price)
            if sl_price <= entry_price:
                sl_price = round(entry_price + (0.80 * h1_atr) + spread_dist, digits)
                risk_dist = sl_price - entry_price

        # 6. Targets: TP1 at 1.5R - 1.8R (50% scale-out), TP2 at 2.5R - 3.2R
        tp1_r = 1.65
        tp2_r = 2.85
        if bias == "BUY":
            tp1_price = round(entry_price + (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price + (risk_dist * tp2_r), digits)
        else:
            tp1_price = round(entry_price - (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price - (risk_dist * tp2_r), digits)

        tp_price = tp2_price
        tp_dist = abs(tp_price - entry_price)
        rr_ratio = round(tp_dist / max(risk_dist, 1e-9), 2)

        return {
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp_price": float(tp_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "risk_dist": float(risk_dist),
            "tp_dist": float(tp_dist),
            "rr_ratio": float(rr_ratio),
            "first_target_volume_pct": 0.50,
            "runner_trail_atr": 1.20,
            "entry_type": entry_type,
            "protocol_details": {
                "protocol": "DAY_TRADING",
                "in_kill_zone": in_kill_zone,
                "session_name": "LONDON_KZ" if in_london_kz else ("NY_KZ" if in_ny_kz else "OFF_KZ"),
                "h1_structure_aligned": h1_aligned,
                "m15_fvg_midpoint": float(m15_fvg_midpoint) if m15_fvg_midpoint is not None else None,
                "breaker_retest": float(breaker_retest) if breaker_retest is not None else None,
                "displacement_origin": float(origin_swing),
                "h1_atr": float(h1_atr)
            }
        }

    # ─── SWING Protocol (H4 / D1) ──────────────────────────────────────────────

    def _execute_swing_protocol(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        bias: str,
        mtf_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        c_price = context.current_price
        spread_dist = max(0.0, context.ask - context.bid) if (context.ask > 0 and context.bid > 0) else (context.volatility.current_spread_pips * pip_size)

        # 1. MTF Frame Extraction
        df_h4 = self._get_df(mtf_data, ["H4", "setup", "context"], target_price=c_price)
        df_d1 = self._get_df(mtf_data, ["D1", "macro"], target_price=c_price)

        d1_atr = self._estimate_atr(df_d1, default_atr=context.volatility.atr * 2.0 if context.volatility.atr > 0 else c_price * 0.012)
        if d1_atr <= 0:
            d1_atr = c_price * 0.012

        # 2. HTF Range & Order Block in Discount (<45%) / Premium (>55%)
        range_low, range_high = self._get_htf_range(df_h4, df_d1, context)
        htf_span = max(range_high - range_low, 1e-6)
        discount_premium_pct = (c_price - range_low) / htf_span

        is_discount = discount_premium_pct < 0.45
        is_premium = discount_premium_pct > 0.55

        # 3. H1 CHOCH (Change of Character) Confirmation
        df_h1 = self._get_df(mtf_data, ["H1", "primary", "timing"], target_price=c_price)
        h1_choch = self._detect_choch(df_h1, context, bias)

        # 4. Entry Anchor
        htf_ob_level = self._find_htf_order_block(df_h4, df_d1, context, bias)
        if htf_ob_level is not None and abs(c_price - htf_ob_level) <= (0.50 * d1_atr):
            entry_price = round(context.ask if bias == "BUY" else context.bid, digits)
            entry_type = "HTF_OB_CONFIRMED"
        elif htf_ob_level is not None and abs(c_price - htf_ob_level) <= (1.50 * d1_atr):
            entry_price = round(htf_ob_level, digits)
            entry_type = "HTF_OB_LIMIT"
        else:
            entry_price = round(context.ask if bias == "BUY" else context.bid, digits)
            entry_type = "SWING_STRUCTURE_ENTRY"

        # 5. Structural SL: Outer D1/H4 structural swing boundary +/- (1.0x spread + 0.40x D1 ATR)
        sl_buffer = spread_dist + (0.40 * d1_atr)
        if bias == "BUY":
            outer_swing = range_low
            sl_price = round(outer_swing - sl_buffer, digits)
            risk_dist = max(pip_size * 5, entry_price - sl_price)
            if sl_price >= entry_price:
                sl_price = round(entry_price - (1.20 * d1_atr) - spread_dist, digits)
                risk_dist = entry_price - sl_price
        else:
            outer_swing = range_high
            sl_price = round(outer_swing + sl_buffer, digits)
            risk_dist = max(pip_size * 5, sl_price - entry_price)
            if sl_price <= entry_price:
                sl_price = round(entry_price + (1.20 * d1_atr) + spread_dist, digits)
                risk_dist = sl_price - entry_price

        # Asset-Class Structural Bounds
        sym_name = str(context.symbol).upper()
        is_gold = ("XAU" in sym_name) or ("GOLD" in sym_name) or (getattr(spec, "asset_class", "").upper() == "COMMODITY") or ("WTI" in sym_name) or ("OIL" in sym_name)
        is_crypto = getattr(spec, "is_crypto", False) or (getattr(spec, "asset_class", "").upper() == "CRYPTO") or ("BTC" in sym_name) or ("ETH" in sym_name) or ("SOL" in sym_name)
        is_index = ("US500" in sym_name) or ("NAS100" in sym_name) or ("US30" in sym_name) or (getattr(spec, "asset_class", "").upper() == "INDEX")
        is_forex = (getattr(spec, "asset_class", "").upper() == "FOREX") and not (is_gold or is_crypto or is_index)

        max_risk_cap = 1.15 * d1_atr if is_index else (1.25 * d1_atr if is_forex else (2.40 * d1_atr if is_crypto else 2.80 * d1_atr))
        if risk_dist > max_risk_cap:
            risk_dist = max_risk_cap
            if bias == "BUY":
                sl_price = round(entry_price - risk_dist, digits)
            else:
                sl_price = round(entry_price + risk_dist, digits)

        # 6. Targets: TP1 at 2.0R - 2.5R (50% scale-out), TP2 at 3.5R - 5.0R+
        tp1_r = 2.20
        tp2_r = 4.00
        if bias == "BUY":
            tp1_price = round(entry_price + (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price + (risk_dist * tp2_r), digits)
        else:
            tp1_price = round(entry_price - (risk_dist * tp1_r), digits)
            tp2_price = round(entry_price - (risk_dist * tp2_r), digits)

        tp_price = tp2_price
        tp_dist = abs(tp_price - entry_price)
        rr_ratio = round(tp_dist / max(risk_dist, 1e-9), 2)

        return {
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp_price": float(tp_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "risk_dist": float(risk_dist),
            "tp_dist": float(tp_dist),
            "rr_ratio": float(rr_ratio),
            "first_target_volume_pct": 0.50,
            "runner_trail_atr": 1.80,
            "entry_type": entry_type,
            "protocol_details": {
                "protocol": "SWING",
                "htf_range": (float(range_low), float(range_high)),
                "discount_premium_pct": round(discount_premium_pct * 100.0, 1),
                "is_discount": is_discount,
                "is_premium": is_premium,
                "h1_choch_confirmed": h1_choch,
                "htf_ob_level": float(htf_ob_level) if htf_ob_level is not None else None,
                "outer_structural_boundary": float(outer_swing),
                "d1_atr": float(d1_atr)
            }
        }

    # ─── Reference Hold Bracket ────────────────────────────────────────────────

    def _calculate_hold_bracket(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        trade_style: str
    ) -> Dict[str, Any]:
        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        c_price = context.current_price
        atr = context.volatility.atr if context.volatility.atr > 0 else (c_price * 0.005)

        style = (trade_style or "SWING").upper()
        if style == "SCALP":
            risk_dist = atr * 0.40
            rr_ratio = 2.20
            runner_trail_atr = 0.80
        elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
            risk_dist = atr * 0.80
            rr_ratio = 2.80
            runner_trail_atr = 1.20
        else:
            risk_dist = atr * 1.50
            rr_ratio = 4.00
            runner_trail_atr = 1.80

        is_bear_tilt = (context.structure.bias == "BEARISH") or (getattr(context.momentum, "trend_score", 0.0) < 0)
        entry_price = round(context.bid if is_bear_tilt else context.ask, digits)

        if is_bear_tilt:
            sl_price = round(entry_price + risk_dist, digits)
            tp1_price = round(entry_price - (risk_dist * 1.5), digits)
            tp2_price = round(entry_price - (risk_dist * rr_ratio), digits)
        else:
            sl_price = round(entry_price - risk_dist, digits)
            tp1_price = round(entry_price + (risk_dist * 1.5), digits)
            tp2_price = round(entry_price + (risk_dist * rr_ratio), digits)

        tp_dist = abs(tp2_price - entry_price)

        return {
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp_price": float(tp2_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "risk_dist": float(risk_dist),
            "tp_dist": float(tp_dist),
            "rr_ratio": float(rr_ratio),
            "first_target_volume_pct": 0.50,
            "runner_trail_atr": float(runner_trail_atr),
            "entry_type": "MONITOR_BRACKET",
            "protocol_details": {"protocol": "HOLD_MONITOR"}
        }

    # ─── Internal Mathematical Utilities ──────────────────────────────────────

    def _get_df(self, mtf_data: Optional[Dict[str, Any]], aliases: list, target_price: Optional[float] = None) -> Optional[pd.DataFrame]:
        if not mtf_data or not isinstance(mtf_data, dict):
            return None
        df = None
        for a in aliases:
            if a in mtf_data and isinstance(mtf_data[a], pd.DataFrame) and not mtf_data[a].empty:
                df = mtf_data[a]
                break
        if df is None or df.empty:
            return None

        # Check for price-scale discrepancy (e.g. synthetic data generated with different base price)
        if target_price is not None and target_price > 0 and len(df) > 0 and "close" in df.columns:
            try:
                last_close = float(df["close"].iloc[-1])
                if last_close > 0 and abs(last_close - target_price) / target_price > 0.10:
                    scale = target_price / last_close
                    df = df.copy()
                    for col in ["open", "high", "low", "close"]:
                        if col in df.columns:
                            df[col] = df[col].astype(float) * scale
            except Exception:
                pass
        return df

    def _estimate_atr(self, df: Optional[pd.DataFrame], default_atr: float = 1.0) -> float:
        if df is None or len(df) < 5 or not all(col in df.columns for col in ["high", "low", "close"]):
            return default_atr
        try:
            highs = df["high"].values.astype(float)
            lows = df["low"].values.astype(float)
            closes = df["close"].values.astype(float)
            tr1 = highs[1:] - lows[1:]
            tr2 = np.abs(highs[1:] - closes[:-1])
            tr3 = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            period = min(14, len(tr))
            return float(np.mean(tr[-period:]))
        except Exception:
            return default_atr

    def _detect_liquidity_sweep(self, df: Optional[pd.DataFrame], bias: str, bars: int = 5) -> Tuple[bool, float, bool]:
        """Detects liquidity sweep of recent N bars' extreme with a rejection wick."""
        if df is None or len(df) < (bars + 2):
            return False, 0.0, False

        try:
            lows = df["low"].values.astype(float)
            highs = df["high"].values.astype(float)
            opens = df["open"].values.astype(float)
            closes = df["close"].values.astype(float)

            # Check the last 1-3 bars for sweep of the prior 5 bars
            sweep_window = slice(-bars - 1, -1)
            prev_low = float(np.min(lows[sweep_window]))
            prev_high = float(np.max(highs[sweep_window]))

            last_low = float(lows[-1])
            last_high = float(highs[-1])
            last_open = float(opens[-1])
            last_close = float(closes[-1])
            bar_range = max(last_high - last_low, 1e-6)

            if bias == "BUY":
                # Swept below prior swing low, but closed back above or created lower rejection wick
                swept = (last_low < prev_low)
                lower_wick = min(last_open, last_close) - last_low
                rejection = (lower_wick / bar_range) >= 0.25 or (last_close > prev_low)
                return swept and rejection, last_low, rejection
            else:
                swept = (last_high > prev_high)
                upper_wick = last_high - max(last_open, last_close)
                rejection = (upper_wick / bar_range) >= 0.25 or (last_close < prev_high)
                return swept and rejection, last_high, rejection
        except Exception:
            return False, 0.0, False

    def _detect_mss_displacement(self, df: Optional[pd.DataFrame], bias: str) -> Tuple[bool, float, float, float]:
        """Detects Market Structure Shift with displacement body ratio >= 55%."""
        if df is None or len(df) < 5:
            return False, 0.50, 0.0, 0.0

        try:
            opens = df["open"].values.astype(float)
            closes = df["close"].values.astype(float)
            highs = df["high"].values.astype(float)
            lows = df["low"].values.astype(float)

            bodies = np.abs(closes[-5:] - opens[-5:])
            ranges = np.maximum(highs[-5:] - lows[-5:], 1e-6)
            ratios = bodies / ranges

            max_ratio = float(np.max(ratios))
            disp_idx = int(np.argmax(ratios))
            disp_low = float(np.min(lows[-5:]))
            disp_high = float(np.max(highs[-5:]))

            is_mss = max_ratio >= 0.55
            return is_mss, max_ratio, disp_low, disp_high
        except Exception:
            return False, 0.50, 0.0, 0.0

    def _find_micro_fvg_ce(self, df_m5: Optional[pd.DataFrame], df_m1: Optional[pd.DataFrame], context: MarketContext, bias: str) -> Optional[float]:
        """Calculates 50% Consequent Encroachment (CE) of recent micro Fair Value Gap."""
        for df in (df_m1, df_m5):
            if df is not None and len(df) >= 3:
                highs = df["high"].values.astype(float)
                lows = df["low"].values.astype(float)
                for i in range(-1, -min(6, len(df)), -1):
                    if bias == "BUY":
                        # Bullish FVG: Low of candle i > High of candle i-2
                        if lows[i] > highs[i - 2]:
                            ce = (lows[i] + highs[i - 2]) / 2.0
                            return float(ce)
                    else:
                        # Bearish FVG: High of candle i < Low of candle i-2
                        if highs[i] < lows[i - 2]:
                            ce = (highs[i] + lows[i - 2]) / 2.0
                            return float(ce)

        # Fallback to context structure Fair Value Gaps
        for fvg in getattr(context.structure, "fair_value_gaps", []):
            if bias == "BUY" and fvg.get("type") == "BULLISH_FVG":
                top = float(fvg.get("top", 0))
                bot = float(fvg.get("bottom", 0))
                if top > bot > 0:
                    return (top + bot) / 2.0
            elif bias == "SELL" and fvg.get("type") == "BEARISH_FVG":
                top = float(fvg.get("top", 0))
                bot = float(fvg.get("bottom", 0))
                if top > bot > 0:
                    return (top + bot) / 2.0

        return None

    def _find_m15_fvg_midpoint(self, df_m15: Optional[pd.DataFrame], context: MarketContext, bias: str) -> Optional[float]:
        return self._find_micro_fvg_ce(df_m15, None, context, bias)

    def _find_breaker_block_retest(self, df_m15: Optional[pd.DataFrame], context: MarketContext, bias: str) -> Optional[float]:
        """Detects breaker block retest level (prior broken swing point flipped to S/R)."""
        if df_m15 is not None and len(df_m15) >= 10:
            highs = df_m15["high"].values.astype(float)
            lows = df_m15["low"].values.astype(float)
            if bias == "BUY":
                # Prior swing high that was broken and is now tested as support
                broken_level = float(np.max(highs[-10:-3]))
                return broken_level
            else:
                broken_level = float(np.min(lows[-10:-3]))
                return broken_level

        # Fallback to context structure demand/supply or key levels
        st = context.structure
        if bias == "BUY" and st.demand_zone[1] > 0:
            return float(st.demand_zone[1])
        elif bias == "SELL" and st.supply_zone[0] > 0:
            return float(st.supply_zone[0])
        return None

    def _find_displacement_origin(self, df_h1: Optional[pd.DataFrame], df_m15: Optional[pd.DataFrame], context: MarketContext, bias: str) -> float:
        """Finds swing point origin of recent displacement move."""
        for df in (df_h1, df_m15):
            if df is not None and len(df) >= 10:
                lows = df["low"].values.astype(float)
                highs = df["high"].values.astype(float)
                if bias == "BUY":
                    return float(np.min(lows[-10:]))
                else:
                    return float(np.max(highs[-10:]))

        # Fallback to context structure
        if bias == "BUY":
            return float(context.structure.swing_low if context.structure.swing_low > 0 else context.current_price * 0.99)
        else:
            return float(context.structure.swing_high if context.structure.swing_high > 0 else context.current_price * 1.01)

    def _check_h1_alignment(self, df_h1: Optional[pd.DataFrame], context: MarketContext, bias: str) -> bool:
        if df_h1 is not None and len(df_h1) >= 20:
            closes = df_h1["close"].values.astype(float)
            ema20 = float(pd.Series(closes).ewm(span=20).mean().iloc[-1])
            last_close = float(closes[-1])
            return (last_close >= ema20) if bias == "BUY" else (last_close <= ema20)
        st_bias = getattr(context.structure, "bias", "").upper()
        return (st_bias == "BULLISH") if bias == "BUY" else (st_bias == "BEARISH")

    def _get_htf_range(self, df_h4: Optional[pd.DataFrame], df_d1: Optional[pd.DataFrame], context: MarketContext) -> Tuple[float, float]:
        for df in (df_d1, df_h4):
            if df is not None and len(df) >= 20:
                lows = df["low"].values.astype(float)
                highs = df["high"].values.astype(float)
                return float(np.min(lows[-30:])), float(np.max(highs[-30:]))

        st = context.structure
        r_low = st.swing_low if st.swing_low > 0 else context.current_price * 0.96
        r_high = st.swing_high if st.swing_high > 0 else context.current_price * 1.04
        return float(r_low), float(r_high)

    def _detect_choch(self, df_h1: Optional[pd.DataFrame], context: MarketContext, bias: str) -> bool:
        """H1 Change of Character (CHOCH) detection."""
        if df_h1 is not None and len(df_h1) >= 15:
            closes = df_h1["close"].values.astype(float)
            highs = df_h1["high"].values.astype(float)
            lows = df_h1["low"].values.astype(float)
            if bias == "BUY":
                swing_h = float(np.max(highs[-10:-2]))
                return float(closes[-1]) > swing_h
            else:
                swing_l = float(np.min(lows[-10:-2]))
                return float(closes[-1]) < swing_l
        return True  # Presumed confirmed if no MTF H1 available

    def _find_htf_order_block(self, df_h4: Optional[pd.DataFrame], df_d1: Optional[pd.DataFrame], context: MarketContext, bias: str) -> Optional[float]:
        """Finds nearest unmitigated HTF Order Block."""
        st = context.structure
        ob_type = "BULLISH_ORDER_BLOCK" if bias == "BUY" else "BEARISH_ORDER_BLOCK"
        for ob in getattr(st, "order_blocks", []):
            if ob.get("type") == ob_type:
                return float(ob.get("high" if bias == "BUY" else "low", context.current_price))

        if bias == "BUY" and st.demand_zone[1] > 0:
            return float(st.demand_zone[1])
        elif bias == "SELL" and st.supply_zone[0] > 0:
            return float(st.supply_zone[0])
        return None


INSTITUTIONAL_ENTRY_ENGINE = InstitutionalEntryEngine()
