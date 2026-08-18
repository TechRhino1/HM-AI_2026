"""
JARVIS AI 3.0 — Liquidity & Order Flow Sweep Intelligence Engine.
Identifies Equal Highs/Lows, Buy-Side/Sell-Side Liquidity Pools, Liquidity Sweeps, and Stop-Run Traps.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from jarvis.data.schemas import LiquidityContext

class LiquidityEngine:
    def __init__(self, eq_threshold_pct: float = 0.15):
        self.eq_threshold_pct = eq_threshold_pct

    def analyze_liquidity(
        self,
        df: pd.DataFrame,
        pivot_window: int = 5
    ) -> LiquidityContext:
        if len(df) < pivot_window * 2 + 5:
            return LiquidityContext()

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        
        # Identify swing points
        swing_highs = []
        swing_lows = []
        for i in range(pivot_window, len(df) - pivot_window):
            if highs[i] == max(highs[i - pivot_window:i + pivot_window + 1]):
                swing_highs.append((i, float(highs[i])))
            if lows[i] == min(lows[i - pivot_window:i + pivot_window + 1]):
                swing_lows.append((i, float(lows[i])))

        if not swing_highs or not swing_lows:
            return LiquidityContext()

        recent_sh = swing_highs[-1][1]
        recent_sl = swing_lows[-1][1]
        
        # Equal Highs / Lows check
        eq_highs = False
        if len(swing_highs) >= 2:
            diff_h = abs(swing_highs[-1][1] - swing_highs[-2][1]) / (recent_sh + 1e-9) * 100.0
            eq_highs = diff_h <= self.eq_threshold_pct

        eq_lows = False
        if len(swing_lows) >= 2:
            diff_l = abs(swing_lows[-1][1] - swing_lows[-2][1]) / (recent_sl + 1e-9) * 100.0
            eq_lows = diff_l <= self.eq_threshold_pct

        # Liquidity Sweep Detection on latest 3 candles:
        # Bullish Sweep: Candle low breaks below recent swing low, but candle close is ABOVE recent swing low (Stop Hunt & Reversal)
        # Bearish Sweep: Candle high breaks above recent swing high, but candle close is BELOW recent swing high (Stop Hunt & Reversal)
        sweep_detected = False
        sweep_type = "NONE"
        sweep_level = 0.0

        latest_high = float(highs[-1])
        latest_low = float(lows[-1])
        latest_close = float(closes[-1])

        # Check latest candle and previous candle
        for idx in [-1, -2]:
            c_high = float(highs[idx])
            c_low = float(lows[idx])
            c_close = float(closes[idx])

            if c_low < recent_sl and c_close > recent_sl:
                sweep_detected = True
                sweep_type = "BULLISH_SWEEP"
                sweep_level = recent_sl
                break
            elif c_high > recent_sh and c_close < recent_sh:
                sweep_detected = True
                sweep_type = "BEARISH_SWEEP"
                sweep_level = recent_sh
                break

        pools = [
            {"type": "BUY_SIDE_LIQUIDITY", "price": round(recent_sh, 4), "status": "UNSWEPT" if not (latest_high > recent_sh) else "SWEPT"},
            {"type": "SELL_SIDE_LIQUIDITY", "price": round(recent_sl, 4), "status": "UNSWEPT" if not (latest_low < recent_sl) else "SWEPT"}
        ]

        return LiquidityContext(
            equal_highs=eq_highs,
            equal_lows=eq_lows,
            sweep_detected=sweep_detected,
            sweep_type=sweep_type,
            sweep_level=round(sweep_level, 4),
            liquidity_pools=pools,
            buy_side_liquidity=round(recent_sh, 4),
            sell_side_liquidity=round(recent_sl, 4)
        )
