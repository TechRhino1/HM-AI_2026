"""
JARVIS AI 3.0 — Volatility & Spread Protection Engine.
Computes ATR, Bollinger bandwidth, volatility regime states (Compression, Normal, Expansion, Extreme), and spread feasibility.
"""
import numpy as np
import pandas as pd
from jarvis.data.schemas import VolatilityContext

class VolatilityEngine:
    def __init__(self, atr_period: int = 14, bb_period: int = 20, bb_std: float = 2.0):
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.bb_std = bb_std

    def analyze_volatility(
        self,
        df: pd.DataFrame,
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0
    ) -> VolatilityContext:
        if len(df) < self.bb_period:
            return VolatilityContext(
                atr=0.0,
                atr_percent=0.0,
                state="NORMAL",
                bollinger_bandwidth=0.0,
                current_spread_pips=current_spread_pips,
                max_allowed_spread_pips=max_allowed_spread_pips,
                is_excessive_spread=current_spread_pips > max_allowed_spread_pips
            )

        high = df["high"]
        low = df["low"]
        close = df["close"]
        close_prev = close.shift(1)

        # True Range
        tr = np.maximum(high - low, np.maximum(np.abs(high - close_prev), np.abs(low - close_prev)))
        atr_series = tr.rolling(window=self.atr_period, min_periods=1).mean()
        current_atr = float(atr_series.iloc[-1])
        current_price = float(close.iloc[-1])
        atr_pct = (current_atr / (current_price + 1e-9)) * 100.0

        # Bollinger Bandwidth
        sma = close.rolling(window=self.bb_period).mean()
        std = close.rolling(window=self.bb_period).std()
        upper_bb = sma + (std * self.bb_std)
        lower_bb = sma - (std * self.bb_std)
        bb_bandwidth = float(((upper_bb.iloc[-1] - lower_bb.iloc[-1]) / (sma.iloc[-1] + 1e-9)) * 100.0)

        # Historical baseline comparisons
        atr_historical_median = float(atr_series.tail(100).median()) if len(atr_series) >= 20 else current_atr
        vol_ratio = current_atr / (atr_historical_median + 1e-9)

        if vol_ratio > 2.5:
            state = "EXTREME"
        elif vol_ratio > 1.4:
            state = "EXPANSION"
        elif vol_ratio < 0.65:
            state = "COMPRESSION"
        else:
            state = "NORMAL"

        is_excessive_spread = current_spread_pips > max_allowed_spread_pips

        return VolatilityContext(
            atr=round(current_atr, 4),
            atr_percent=round(atr_pct, 4),
            state=state,
            bollinger_bandwidth=round(bb_bandwidth, 3),
            current_spread_pips=round(current_spread_pips, 2),
            max_allowed_spread_pips=max_allowed_spread_pips,
            is_excessive_spread=is_excessive_spread
        )
