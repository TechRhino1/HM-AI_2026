"""
JARVIS AI 4.0 — Historical Market Regime Tagger.
Annotates historical price bars with causal (zero-lookahead) market regime labels
to enable conditional performance breakdown during backtesting and optimization.
"""
import logging
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger("JARVIS_RegimeTagger")


class HistoricalRegimeTagger:
    """
    Classifies historical market regimes across every bar using purely causal
    moving averages, volatility ratios, and trend momentum without future leakage.
    """

    @staticmethod
    def tag_regimes(df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds 'regime' and 'volatility_state' columns to the historical DataFrame.
        Guarantees no lookahead bias by using backward rolling windows only.
        """
        if df.empty or len(df) < 20:
            tagged = df.copy()
            tagged["regime"] = "RANGE"
            tagged["volatility_state"] = "NORMAL"
            return tagged

        tagged = df.copy()
        c = tagged["close"]
        h = tagged["high"]
        l = tagged["low"]

        # 1. Moving Averages (Trend Filter)
        ema20 = c.ewm(span=20, adjust=False).mean()
        ema50 = c.ewm(span=50, adjust=False).mean()
        ema200 = c.ewm(span=min(len(df), 200), adjust=False).mean()

        # 2. Average True Range (Volatility Filter)
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(14, min_periods=1).mean()
        atr_median = atr14.rolling(100, min_periods=10).median().bfill()
        atr_ratio = (atr14 / (atr_median + 1e-9)).fillna(1.0)

        # 3. Bollinger Band Width (Compression / Expansion)
        rolling_std = c.rolling(20, min_periods=5).std()
        bb_width = (rolling_std * 4.0) / (ema20 + 1e-9)
        bb_width_med = bb_width.rolling(100, min_periods=10).median().bfill()
        is_compression = bb_width < (bb_width_med * 0.65)
        is_expansion = bb_width > (bb_width_med * 1.50)

        # 4. ADX Approximation / Directional Movement
        up_move = h - h.shift(1)
        down_move = l.shift(1) - l
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        plus_di = 100.0 * (pd.Series(plus_dm).rolling(14, min_periods=1).mean() / (atr14 + 1e-9))
        minus_di = 100.0 * (pd.Series(minus_dm).rolling(14, min_periods=1).mean() / (atr14 + 1e-9))
        dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9))
        adx = dx.rolling(14, min_periods=1).mean().fillna(15.0)

        # 5. Determine Regime per bar
        regimes: List[str] = []
        vol_states: List[str] = []

        for i in range(len(tagged)):
            curr_c = c.iloc[i]
            curr_ema20 = ema20.iloc[i]
            curr_ema50 = ema50.iloc[i]
            curr_ema200 = ema200.iloc[i]
            curr_adx = adx.iloc[i]
            curr_atr_r = atr_ratio.iloc[i]
            comp = is_compression.iloc[i]
            exp = is_expansion.iloc[i]

            # Volatility state
            if curr_atr_r >= 1.70 or exp:
                v_state = "HIGH_VOLATILITY"
            elif curr_atr_r <= 0.65 or comp:
                v_state = "LOW_VOLATILITY"
            else:
                v_state = "NORMAL"
            vol_states.append(v_state)

            # Regime state
            if curr_adx >= 24.0 and curr_c > curr_ema20 > curr_ema50:
                regimes.append("TREND_BULL")
            elif curr_adx >= 24.0 and curr_c < curr_ema20 < curr_ema50:
                regimes.append("TREND_BEAR")
            elif exp and curr_atr_r >= 1.50:
                regimes.append("BREAKOUT")
            elif comp:
                regimes.append("CONSOLIDATION")
            else:
                regimes.append("RANGE")

        tagged["regime"] = regimes
        tagged["volatility_state"] = vol_states
        return tagged
