import numpy as np
import pandas as pd
from typing import Dict, List, Any

class MarketStructureEngine:
    def __init__(self, pivot_window: int = 5):
        self.pivot_window = pivot_window

    def analyze_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.pivot_window * 2 + 1:
            return {"bias": "NEUTRAL", "bos": False, "choch": False, "swing_highs": [], "swing_lows": []}

        df = df.copy()
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        swing_highs = []
        swing_lows = []

        # Find pivot highs and lows
        w = self.pivot_window
        for i in range(w, len(df) - w):
            if highs[i] == max(highs[i - w:i + w + 1]):
                swing_highs.append({"index": i, "price": highs[i], "time": df["time"].iloc[i]})
            if lows[i] == min(lows[i - w:i + w + 1]):
                swing_lows.append({"index": i, "price": lows[i], "time": df["time"].iloc[i]})

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {"bias": "NEUTRAL", "bos": False, "choch": False, "swing_highs": swing_highs, "swing_lows": swing_lows}

        recent_sh = swing_highs[-1]["price"]
        prev_sh = swing_highs[-2]["price"]
        recent_sl = swing_lows[-1]["price"]
        prev_sl = swing_lows[-2]["price"]
        latest_close = closes[-1]

        # Determine Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), Lower Lows (LL)
        hh = recent_sh > prev_sh
        hl = recent_sl > prev_sl
        lh = recent_sh < prev_sh
        ll = recent_sl < prev_sl

        bos_bullish = latest_close > recent_sh
        bos_bearish = latest_close < recent_sl
        choch_bullish = (lh and ll) and (latest_close > recent_sh)
        choch_bearish = (hh and hl) and (latest_close < recent_sl)

        bias = "NEUTRAL"
        if hh and hl:
            bias = "BULLISH"
        elif lh and ll:
            bias = "BEARISH"
        elif bos_bullish or choch_bullish:
            bias = "BULLISH"
        elif bos_bearish or choch_bearish:
            bias = "BEARISH"

        # Supply / Demand Zones
        demand_zone = (recent_sl, recent_sl * 1.003) if recent_sl else (0.0, 0.0)
        supply_zone = (recent_sh * 0.997, recent_sh) if recent_sh else (0.0, 0.0)

        # Equal Highs / Lows (Liquidity pools)
        eq_highs = abs(recent_sh - prev_sh) / recent_sh < 0.0015
        eq_lows = abs(recent_sl - prev_sl) / recent_sl < 0.0015

        return {
            "bias": bias,
            "bos": bos_bullish or bos_bearish,
            "bos_type": "BULLISH" if bos_bullish else ("BEARISH" if bos_bearish else "NONE"),
            "choch": choch_bullish or choch_bearish,
            "choch_type": "BULLISH" if choch_bullish else ("BEARISH" if choch_bearish else "NONE"),
            "recent_swing_high": recent_sh,
            "recent_swing_low": recent_sl,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "demand_zone": demand_zone,
            "supply_zone": supply_zone,
            "liquidity_equal_highs": eq_highs,
            "liquidity_equal_lows": eq_lows,
            "higher_highs": hh,
            "higher_lows": hl,
            "lower_highs": lh,
            "lower_lows": ll
        }
