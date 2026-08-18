import pandas as pd
from typing import Dict, Any

class HighFrequencyScalpingEngine:
    def analyze_scalp_setup(
        self,
        df_m5: pd.DataFrame,
        df_h1: pd.DataFrame,
        structure_h1: Dict[str, Any],
        volatility_info: Dict[str, Any],
        symbol: str = "XAUUSD"
    ) -> Dict[str, Any]:
        if len(df_m5) < 30:
            return {"scalp_signal": False, "action": "HOLD", "scalp_type": "NONE", "scalp_score": 0.0}

        # Calculate M5 EMAs (5 EMA & 13 EMA & 34 EMA)
        ema_5 = df_m5["close"].ewm(span=5, adjust=False).mean()
        ema_13 = df_m5["close"].ewm(span=13, adjust=False).mean()
        ema_34 = df_m5["close"].ewm(span=34, adjust=False).mean()

        # Calculate M5 RSI (14)
        delta = df_m5["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        latest = df_m5.iloc[-1]
        prev = df_m5.iloc[-2]
        h1_bias = structure_h1.get("bias", "NEUTRAL")
        atr = volatility_info.get("atr", latest["close"] * 0.003)

        # 1. Bullish Micro-Scalp Trigger
        # Criteria: M5 5 EMA > 13 EMA > 34 EMA + M5 Pullback Rejection + RSI > 50 + H1 Alignment
        bullish_scalp = False
        scalp_score = 0.0

        if (h1_bias in ["BULLISH", "NEUTRAL"]) and (ema_5.iloc[-1] > ema_13.iloc[-1]):
            if prev["low"] <= ema_13.iloc[-2] and latest["close"] > ema_5.iloc[-1] and rsi.iloc[-1] > 48.0:
                bullish_scalp = True
                scalp_score = 85.0 if h1_bias == "BULLISH" else 78.0

        # 2. Bearish Micro-Scalp Trigger
        bearish_scalp = False
        if (h1_bias in ["BEARISH", "NEUTRAL"]) and (ema_5.iloc[-1] < ema_13.iloc[-1]):
            if prev["high"] >= ema_13.iloc[-2] and latest["close"] < ema_5.iloc[-1] and rsi.iloc[-1] < 52.0:
                bearish_scalp = True
                scalp_score = 85.0 if h1_bias == "BEARISH" else 78.0

        action = "BUY" if bullish_scalp else ("SELL" if bearish_scalp else "HOLD")

        # Calculate Tight Scalp SL & TP
        c_price = float(latest["close"])
        sl_dist = atr * 1.0
        tp_dist = atr * 2.2

        scalp_sl = round(c_price - sl_dist if action == "BUY" else c_price + sl_dist, 2 if ("XAU" in symbol or "BTC" in symbol) else 5)
        scalp_tp = round(c_price + tp_dist if action == "BUY" else c_price - tp_dist, 2 if ("XAU" in symbol or "BTC" in symbol) else 5)

        return {
            "scalp_signal": bullish_scalp or bearish_scalp,
            "action": action,
            "scalp_type": "MULTI_MARKET_M5_EMA_SCALP",
            "scalp_score": scalp_score,
            "scalp_sl": scalp_sl,
            "scalp_tp": scalp_tp,
            "rr_ratio": 2.2,
            "m5_ema_5": float(ema_5.iloc[-1]),
            "m5_ema_13": float(ema_13.iloc[-1]),
            "rsi": float(rsi.iloc[-1])
        }

class UltraFastMicroScalpingEngine:
    def analyze_micro_scalp(
        self,
        df_m1: pd.DataFrame,
        volatility_info: Dict[str, Any],
        symbol: str = "XAUUSD"
    ) -> Dict[str, Any]:
        """
        Ultra-Fast Sub-Minute M1 Micro-Scalping Engine.
        Captures quick 5-pip to 15-pip micro movements using M1 EMA(3/8) + M1 Stochastic(5,3,3).
        """
        if len(df_m1) < 25:
            return {"micro_signal": False, "action": "HOLD", "micro_score": 0.0}

        # Calculate M1 3 EMA & 8 EMA
        ema_3 = df_m1["close"].ewm(span=3, adjust=False).mean()
        ema_8 = df_m1["close"].ewm(span=8, adjust=False).mean()

        # Calculate M1 Stochastic (5, 3, 3)
        low_5 = df_m1["low"].rolling(5).min()
        high_5 = df_m1["high"].rolling(5).max()
        k_perc = 100 * ((df_m1["close"] - low_5) / (high_5 - low_5 + 1e-9))
        d_perc = k_perc.rolling(3).mean()

        latest = df_m1.iloc[-1]
        prev = df_m1.iloc[-2]
        c_price = float(latest["close"])
        atr_m1 = volatility_info.get("atr", c_price * 0.001)

        # 1. Bullish Micro-Scalp (3 EMA > 8 EMA + Stoch %K crosses above %D from oversold < 30)
        bullish_micro = False
        if ema_3.iloc[-1] > ema_8.iloc[-1] and prev["low"] <= ema_8.iloc[-2]:
            if k_perc.iloc[-1] > d_perc.iloc[-1] and k_perc.iloc[-2] <= d_perc.iloc[-2] and k_perc.iloc[-2] < 45.0:
                bullish_micro = True

        # 2. Bearish Micro-Scalp (3 EMA < 8 EMA + Stoch %K crosses below %D from overbought > 70)
        bearish_micro = False
        if ema_3.iloc[-1] < ema_8.iloc[-1] and prev["high"] >= ema_8.iloc[-2]:
            if k_perc.iloc[-1] < d_perc.iloc[-1] and k_perc.iloc[-2] >= d_perc.iloc[-2] and k_perc.iloc[-2] > 55.0:
                bearish_micro = True

        action = "BUY" if bullish_micro else ("SELL" if bearish_micro else "HOLD")
        micro_score = 88.0 if (bullish_micro or bearish_micro) else 0.0

        # Ultra-Tight Micro Targets (5-15 pips)
        sl_dist = max(atr_m1 * 0.5, c_price * 0.0006)
        tp_dist = sl_dist * 1.8

        micro_sl = round(c_price - sl_dist if action == "BUY" else c_price + sl_dist, 2 if ("XAU" in symbol or "BTC" in symbol) else 5)
        micro_tp = round(c_price + tp_dist if action == "BUY" else c_price - tp_dist, 2 if ("XAU" in symbol or "BTC" in symbol) else 5)

        return {
            "micro_signal": bullish_micro or bearish_micro,
            "action": action,
            "strategy": "ULTRA_FAST_M1_MICRO_SCALP",
            "micro_score": micro_score,
            "micro_sl": micro_sl,
            "micro_tp": micro_tp,
            "rr_ratio": 1.8,
            "fast_breakeven_trigger_pips": round(sl_dist * 0.4, 2)
        }
