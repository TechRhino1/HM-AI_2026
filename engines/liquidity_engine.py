import numpy as np
import pandas as pd
from typing import Dict, Any, List

class LiquidityEngine:
    def analyze_liquidity(self, df: pd.DataFrame, swing_highs: List[Dict[str, Any]], swing_lows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(df) < 10 or not swing_highs or not swing_lows:
            return {"sweep_detected": False, "sweep_type": "NONE", "equal_highs": False, "equal_lows": False}

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        recent_sh = swing_highs[-1]["price"] if swing_highs else 0.0
        recent_sl = swing_lows[-1]["price"] if swing_lows else 0.0

        # Check for Liquidity Sweep of Swing High (Bullish Trap -> Bearish Sweep)
        bullish_sweep = False
        if latest["high"] > recent_sh and latest["close"] < recent_sh:
            wick_top = latest["high"] - max(latest["open"], latest["close"])
            body = abs(latest["close"] - latest["open"])
            if wick_top > body * 1.5:
                bullish_sweep = True  # High swept, rejected back down

        # Check for Liquidity Sweep of Swing Low (Bearish Trap -> Bullish Sweep)
        bearish_sweep = False
        if latest["low"] < recent_sl and latest["close"] > recent_sl:
            wick_bot = min(latest["open"], latest["close"]) - latest["low"]
            body = abs(latest["close"] - latest["open"])
            if wick_bot > body * 1.5:
                bearish_sweep = True  # Low swept, rejected back up

        sweep_detected = bullish_sweep or bearish_sweep
        sweep_type = "BEARISH_SWEEP" if bullish_sweep else ("BULLISH_SWEEP" if bearish_sweep else "NONE")

        return {
            "sweep_detected": sweep_detected,
            "sweep_type": sweep_type,
            "recent_swing_high": recent_sh,
            "recent_swing_low": recent_sl
        }
