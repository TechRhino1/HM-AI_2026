"""
JARVIS AI 3.0 — Multi-Factor Momentum & Trend Dynamics Engine.
Calculates RSI, ADX, DI+/DI-, EMA alignments, Momentum slope, Acceleration/Deceleration, and Divergence.
"""
import numpy as np
import pandas as pd
from jarvis.data.schemas import MomentumContext

class MomentumEngine:
    def __init__(self, ema_fast: int = 20, ema_med: int = 50, ema_slow: int = 200, rsi_period: int = 14, adx_period: int = 14):
        self.ema_fast = ema_fast
        self.ema_med = ema_med
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.adx_period = adx_period

    def analyze_momentum(self, df: pd.DataFrame) -> MomentumContext:
        if len(df) < self.ema_slow:
            # If not enough bars for EMA 200, calculate on available length with fallbacks
            min_len = max(self.rsi_period, self.adx_period) + 5
            if len(df) < min_len:
                return MomentumContext()

        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        c_price = float(close.iloc[-1])

        # EMAs
        span_fast = min(self.ema_fast, len(df))
        span_med = min(self.ema_med, len(df))
        span_slow = min(self.ema_slow, len(df))

        ema_f = close.ewm(span=span_fast, adjust=False).mean()
        ema_m = close.ewm(span=span_med, adjust=False).mean()
        ema_s = close.ewm(span=span_slow, adjust=False).mean()

        # ATR & ADX
        close_prev = close.shift(1)
        tr = np.maximum(high - low, np.maximum(np.abs(high - close_prev), np.abs(low - close_prev)))
        
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr_smooth = tr.rolling(window=self.adx_period, min_periods=1).sum()
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=self.adx_period, min_periods=1).sum() / (tr_smooth + 1e-9))
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=self.adx_period, min_periods=1).sum() / (tr_smooth + 1e-9))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(window=self.adx_period, min_periods=1).mean()

        # RSI 14
        delta = close.diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain, index=df.index).rolling(window=self.rsi_period, min_periods=1).mean()
        avg_loss = pd.Series(loss, index=df.index).rolling(window=self.rsi_period, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))

        cur_rsi = float(rsi_series.iloc[-1])
        cur_adx = float(adx.iloc[-1])
        cur_plus_di = float(plus_di.iloc[-1])
        cur_minus_di = float(minus_di.iloc[-1])
        cur_ema_f = float(ema_f.iloc[-1])
        cur_ema_m = float(ema_m.iloc[-1])
        cur_ema_s = float(ema_s.iloc[-1])

        # Trend Score calculation (-100 to +100)
        score = 0.0
        # 1. EMA stack
        if c_price > cur_ema_f > cur_ema_m > cur_ema_s:
            score += 45.0
        elif c_price > cur_ema_f > cur_ema_m:
            score += 30.0
        elif c_price > cur_ema_f:
            score += 15.0
        elif c_price < cur_ema_f < cur_ema_m < cur_ema_s:
            score -= 45.0
        elif c_price < cur_ema_f < cur_ema_m:
            score -= 30.0
        elif c_price < cur_ema_f:
            score -= 15.0

        # 2. ADX & Direction
        if cur_adx >= 22.0:
            if cur_plus_di > cur_minus_di:
                score += 25.0
            else:
                score -= 25.0

        # 3. Slope
        window_slope = min(10, len(df))
        y = close.iloc[-window_slope:].values
        x = np.arange(window_slope)
        slope = np.polyfit(x, y, 1)[0]
        norm_slope = (slope / c_price) * 1000.0
        score += np.clip(norm_slope * 15.0, -30.0, 30.0)

        final_trend_score = int(np.clip(score, -100, 100))

        # Momentum acceleration / deceleration
        diff_recent = close.iloc[-1] - close.iloc[-3] if len(df) >= 3 else 0.0
        diff_prior = close.iloc[-3] - close.iloc[-6] if len(df) >= 6 else 0.0
        if abs(diff_recent) > abs(diff_prior) * 1.3:
            acceleration = "ACCELERATING"
        elif abs(diff_recent) < abs(diff_prior) * 0.7:
            acceleration = "DECELERATING"
        elif (cur_rsi > 78 and final_trend_score > 60) or (cur_rsi < 22 and final_trend_score < -60):
            acceleration = "EXHAUSTION"
        else:
            acceleration = "STEADY"

        # RSI Divergence detection
        divergence = "NONE"
        if len(df) >= 20:
            p_recent_low = low.iloc[-10:].min()
            p_prior_low = low.iloc[-20:-10].min()
            rsi_recent_low = rsi_series.iloc[-10:].min()
            rsi_prior_low = rsi_series.iloc[-20:-10].min()

            if p_recent_low < p_prior_low and rsi_recent_low > rsi_prior_low + 3.0:
                divergence = "BULLISH_DIVERGENCE"

            p_recent_high = high.iloc[-10:].max()
            p_prior_high = high.iloc[-20:-10].max()
            rsi_recent_high = rsi_series.iloc[-10:].max()
            rsi_prior_high = rsi_series.iloc[-20:-10].max()

            if p_recent_high > p_prior_high and rsi_recent_high < rsi_prior_high - 3.0:
                divergence = "BEARISH_DIVERGENCE"

        return MomentumContext(
            rsi=round(cur_rsi, 1),
            adx=round(cur_adx, 1),
            plus_di=round(cur_plus_di, 1),
            minus_di=round(cur_minus_di, 1),
            trend_score=final_trend_score,
            slope=round(float(norm_slope), 3),
            divergence=divergence,
            acceleration=acceleration
        )
