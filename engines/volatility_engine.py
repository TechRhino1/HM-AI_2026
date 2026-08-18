import numpy as np
import pandas as pd
from typing import Dict, Any

class VolatilityEngine:
    def __init__(self, atr_period: int = 14, hist_period: int = 50):
        self.atr_period = atr_period
        self.hist_period = hist_period

    def analyze_volatility(self, df: pd.DataFrame, current_spread_pips: float = 0.0, max_allowed_spread: float = 35.0) -> Dict[str, Any]:
        if len(df) < self.hist_period:
            return {
                "state": "NORMAL",
                "atr": 0.0,
                "atr_pct": 0.0,
                "volatility_ratio": 1.0,
                "is_excessive_spread": False
            }

        high = df["high"]
        low = df["low"]
        close = df["close"]
        close_prev = close.shift(1)

        tr = np.maximum(high - low, np.maximum(np.abs(high - close_prev), np.abs(low - close_prev)))
        atr_series = tr.rolling(self.atr_period).mean()
        atr_hist_series = tr.rolling(self.hist_period).mean()

        current_atr = float(atr_series.iloc[-1])
        hist_atr = float(atr_hist_series.iloc[-1]) if float(atr_hist_series.iloc[-1]) > 0 else current_atr

        latest_close = float(close.iloc[-1])
        atr_pct = (current_atr / latest_close) * 100 if latest_close > 0 else 0.0
        vol_ratio = current_atr / (hist_atr + 1e-9)

        state = "NORMAL"
        if vol_ratio > 2.2:
            state = "EXTREME"
        elif vol_ratio > 1.4:
            state = "HIGH"
        elif vol_ratio < 0.6:
            state = "VERY_LOW"
        elif vol_ratio < 0.8:
            state = "LOW"

        is_excessive_spread = current_spread_pips > max_allowed_spread

        return {
            "state": state,
            "atr": round(current_atr, 4),
            "atr_pct": round(atr_pct, 3),
            "volatility_ratio": round(vol_ratio, 2),
            "current_spread_pips": current_spread_pips,
            "max_allowed_spread": max_allowed_spread,
            "is_excessive_spread": is_excessive_spread
        }
