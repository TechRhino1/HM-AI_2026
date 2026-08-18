import numpy as np
import pandas as pd
from typing import Dict, Any

class MultiFactorTrendEngine:
    def __init__(self, ema_fast: int = 20, ema_med: int = 50, ema_slow: int = 200, adx_period: int = 14, rsi_period: int = 14):
        self.ema_fast = ema_fast
        self.ema_med = ema_med
        self.ema_slow = ema_slow
        self.adx_period = adx_period
        self.rsi_period = rsi_period

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_med"] = df["close"].ewm(span=self.ema_med, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        # ATR calculation
        high = df["high"]
        low = df["low"]
        close_prev = df["close"].shift(1)
        tr = np.maximum(high - low, np.maximum(np.abs(high - close_prev), np.abs(low - close_prev)))
        df["atr"] = tr.rolling(14).mean()

        # ADX calculation
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr_smooth = tr.rolling(self.adx_period).sum()
        plus_di = 100 * (pd.Series(plus_dm).rolling(self.adx_period).sum() / (tr_smooth + 1e-9))
        minus_di = 100 * (pd.Series(minus_dm).rolling(self.adx_period).sum() / (tr_smooth + 1e-9))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        df["adx"] = dx.rolling(self.adx_period).mean()
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di

        # RSI calculation
        delta = df["close"].diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain).rolling(self.rsi_period).mean()
        avg_loss = pd.Series(loss).rolling(self.rsi_period).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    def analyze_trend(self, df: pd.DataFrame, htf_bias: str = "NEUTRAL") -> Dict[str, Any]:
        if len(df) < self.ema_slow:
            return {"trend_score": 0, "classification": "NEUTRAL", "adx": 0, "rsi": 50, "strength": "WEAK"}

        df_ind = self.calculate_indicators(df)
        row = df_ind.iloc[-1]
        close = row["close"]
        ema_f = row["ema_fast"]
        ema_m = row["ema_med"]
        ema_s = row["ema_slow"]
        adx = row["adx"]
        plus_di = row["plus_di"]
        minus_di = row["minus_di"]
        rsi = row["rsi"]

        score = 0.0

        # 1. EMA Stack Score (+40 max)
        if close > ema_f > ema_m > ema_s:
            score += 40
        elif close > ema_f > ema_m:
            score += 25
        elif close > ema_f:
            score += 10
        elif close < ema_f < ema_m < ema_s:
            score -= 40
        elif close < ema_f < ema_m:
            score -= 25
        elif close < ema_f:
            score -= 10

        # 2. Price Slope Score (+20 max)
        window = 10
        y = df_ind["close"].iloc[-window:].values
        x = np.arange(window)
        slope = np.polyfit(x, y, 1)[0]
        normal_slope = (slope / close) * 1000
        score += np.clip(normal_slope * 10, -20, 20)

        # 3. ADX & RSI Direction Score (+20 max)
        if adx > 22:
            if plus_di > minus_di and rsi > 50:
                score += 20
            elif minus_di > plus_di and rsi < 50:
                score -= 20
        elif adx > 15:
            if plus_di > minus_di:
                score += 10
            else:
                score -= 10

        # 4. Higher Timeframe Alignment Score (+20 max)
        if htf_bias == "BULLISH":
            score += 20
        elif htf_bias == "BEARISH":
            score -= 20

        final_score = int(np.clip(score, -100, 100))

        classification = "NEUTRAL"
        if final_score >= 55:
            classification = "STRONG_BULLISH"
        elif final_score >= 25:
            classification = "MODERATE_BULLISH"
        elif final_score <= -55:
            classification = "STRONG_BEARISH"
        elif final_score <= -25:
            classification = "MODERATE_BEARISH"

        strength = "STRONG" if adx > 25 else ("MODERATE" if adx > 18 else "WEAK")

        return {
            "trend_score": final_score,
            "classification": classification,
            "adx": round(float(adx), 1),
            "rsi": round(float(rsi), 1),
            "strength": strength,
            "close": float(close),
            "ema_fast": float(ema_f),
            "ema_med": float(ema_m),
            "ema_slow": float(ema_s)
        }
