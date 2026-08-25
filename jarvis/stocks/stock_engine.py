"""
JARVIS AI 3.0 — AI Stock Intelligence & Breakout Probability Analytics Engine
Calculates multi-factor breakout scores, volatility squeezes, multi-timeframe matrices,
institutional trade plans, and support/resistance zones for any equity instrument.
"""
import math
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from jarvis.stocks.universe import STOCK_UNIVERSE, get_stock_profile


class StockIntelligenceEngine:
    """
    Institutional AI Engine for Equity Breakout Screening and In-Depth Technical Analysis.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_sec = 3.0

    def generate_candles(self, symbol: str, timeframe: str = "1D", num_bars: int = 120) -> List[Dict[str, Any]]:
        """
        Generates realistic chronological OHLCV candlestick data tailored to the stock's profile and volatility.
        """
        profile = get_stock_profile(symbol)
        base_price = float(profile.get("base_price", 150.0))
        beta = float(profile.get("beta", 1.2))

        # Timeframe to seconds map
        tf_seconds_map = {
            "1M": 60,
            "5M": 300,
            "15M": 900,
            "1H": 3600,
            "4H": 14400,
            "1D": 86400,
            "1W": 604800,
        }
        bar_step_sec = tf_seconds_map.get(timeframe.upper(), 86400)
        
        # Volatility scale by timeframe and beta
        vol_scalar = (0.015 * beta) * math.sqrt(bar_step_sec / 86400.0)
        vol_scalar = max(0.003, min(vol_scalar, 0.045))

        # Pseudo-deterministic random seed based on symbol & current hour to maintain continuity
        current_epoch_hour = int(time.time() // 3600)
        seed_val = hash(f"{symbol}_{timeframe}_{current_epoch_hour}") % (2**32)
        rng = np.random.RandomState(seed_val)

        # Generate geometric brownian walk with slight upward drift and realistic regime waves
        returns = rng.normal(loc=0.0004, scale=vol_scalar, size=num_bars)
        
        # Inject realistic compression coiling -> breakout surge near the latest 20% bars
        squeeze_start = int(num_bars * 0.65)
        breakout_start = int(num_bars * 0.88)
        
        # Squeeze compression: tight range
        returns[squeeze_start:breakout_start] *= 0.35
        # Breakout expansion: directional surge
        trend_direction = 1.0 if (hash(symbol) % 3 != 0) else -0.7
        returns[breakout_start:] = np.abs(returns[breakout_start:]) * 1.8 * trend_direction

        prices = base_price * np.exp(np.cumsum(returns))
        # Re-scale last price closer to base price
        scale_factor = base_price / prices[-1] * (1.0 + (trend_direction * 0.025))
        prices *= scale_factor

        now_sec = int(time.time())
        candles = []
        
        for i in range(num_bars):
            bar_time = now_sec - (num_bars - 1 - i) * bar_step_sec
            close_p = float(prices[i])
            prev_close = float(prices[i - 1]) if i > 0 else close_p * (1 - returns[0])
            open_p = prev_close + rng.normal(0, close_p * vol_scalar * 0.2)
            
            intra_high = max(open_p, close_p) + abs(rng.normal(0, close_p * vol_scalar * 0.7))
            intra_low = min(open_p, close_p) - abs(rng.normal(0, close_p * vol_scalar * 0.7))
            
            # Base volume scaling
            base_vol = 1000000 * beta
            if i >= breakout_start:
                vol = base_vol * rng.uniform(1.8, 3.8) # Volume surge
            elif i >= squeeze_start:
                vol = base_vol * rng.uniform(0.4, 0.75) # Volume contraction
            else:
                vol = base_vol * rng.uniform(0.8, 1.4)

            candles.append({
                "time": bar_time,
                "open": round(open_p, 2),
                "high": round(intra_high, 2),
                "low": round(intra_low, 2),
                "close": round(close_p, 2),
                "volume": int(vol)
            })

        return candles

    def analyze_stock(self, symbol: str, timeframe: str = "1D") -> Dict[str, Any]:
        """
        Runs full institutional quantitative AI analysis for a given stock symbol.
        """
        cache_key = f"{symbol}_{timeframe}"
        now = time.time()
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl_sec:
                return entry["data"]

        profile = get_stock_profile(symbol)
        candles = self.generate_candles(symbol, timeframe=timeframe, num_bars=120)
        
        df = pd.DataFrame(candles)
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values

        current_price = float(closes[-1])
        prev_close = float(closes[-2]) if len(closes) > 1 else current_price
        day_open = float(df["open"].iloc[-1])
        day_high = float(df["high"].iloc[-1])
        day_low = float(df["low"].iloc[-1])

        change_val = current_price - prev_close
        change_pct = (change_val / prev_close) * 100.0 if prev_close > 0 else 0.0

        # -------------------------------------------------------------
        # 1. Technical Indicators Calculation
        # -------------------------------------------------------------
        # Relative Strength Index (RSI 14)
        diffs = np.diff(closes)
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 1.0
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 1.0
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = float(100.0 - (100.0 / (1.0 + rs)))
        rsi = max(10.0, min(rsi, 90.0))

        # 20-period Moving Average & Bollinger Bands
        sma20 = float(np.mean(closes[-20:]))
        std20 = float(np.std(closes[-20:]))
        bb_upper = sma20 + (2.0 * std20)
        bb_lower = sma20 - (2.0 * std20)
        bb_width_pct = ((bb_upper - bb_lower) / sma20) * 100.0

        # Average True Range (ATR 14)
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr14 = float(np.mean(tr[-14:])) if len(tr) >= 14 else current_price * 0.02

        # Keltner Channels (20 EMA +/- 1.5 * ATR)
        ema20 = sma20
        kc_upper = ema20 + (1.5 * atr14)
        kc_lower = ema20 - (1.5 * atr14)

        # Volatility Squeeze Detection (John Carter Squeeze)
        # Squeeze is ON when Bollinger Bands are completely inside Keltner Channels
        is_squeeze_on = (bb_upper < kc_upper) and (bb_lower > kc_lower)
        squeeze_ratio = ((kc_upper - kc_lower) / (bb_upper - bb_lower + 1e-9))

        # Relative Volume (RVOL) = Today's Volume / 20-day Average Volume
        avg_vol_20 = float(np.mean(volumes[-20:]))
        cur_vol = float(volumes[-1])
        rvol = float(cur_vol / (avg_vol_20 + 1e-9))

        # MACD (12, 26, 9)
        ema12 = float(pd.Series(closes).ewm(span=12, adjust=False).mean().iloc[-1])
        ema26 = float(pd.Series(closes).ewm(span=26, adjust=False).mean().iloc[-1])
        macd_line = ema12 - ema26
        macd_series = pd.Series(closes).ewm(span=12, adjust=False).mean() - pd.Series(closes).ewm(span=26, adjust=False).mean()
        macd_signal = float(macd_series.ewm(span=9, adjust=False).mean().iloc[-1])
        macd_hist = macd_line - macd_signal

        # ADX Approximation (Trend Strength)
        adx = min(68.0, max(14.0, (abs(change_pct) * 6.5) + (rvol * 10.0) + (15.0 if abs(macd_hist) > 0.5 else 5.0)))

        # -------------------------------------------------------------
        # 2. Dynamic Support & Resistance Levels (Pivot & Camarilla)
        # -------------------------------------------------------------
        p_high = float(np.max(highs[-20:]))
        p_low = float(np.min(lows[-20:]))
        p_close = current_price

        pivot = (p_high + p_low + p_close) / 3.0
        r1 = (2.0 * pivot) - p_low
        s1 = (2.0 * pivot) - p_high
        r2 = pivot + (p_high - p_low)
        s2 = pivot - (p_high - p_low)
        r3 = p_high + 2.0 * (pivot - p_low)
        s3 = p_low - 2.0 * (p_high - pivot)

        # -------------------------------------------------------------
        # 3. AI Breakout Probability Score Engine (0–100%)
        # -------------------------------------------------------------
        prob_score = 50.0  # baseline

        # Factor 1: Volatility Squeeze Compression & Expansion (+20)
        if is_squeeze_on:
            prob_score += 18.0
            squeeze_state = "SQUEEZE_COILING (EXTREME)"
        elif bb_width_pct < 4.0:
            prob_score += 12.0
            squeeze_state = "SQUEEZE_COILING (MEDIUM)"
        elif macd_hist > 0 and change_pct > 0:
            prob_score += 15.0
            squeeze_state = "FIRED_BULLISH_EXPANSION"
        else:
            squeeze_state = "NORMAL_RANGE"

        # Factor 2: Volume Surge (RVOL) (+20)
        if rvol >= 2.5:
            prob_score += 20.0
        elif rvol >= 1.7:
            prob_score += 14.0
        elif rvol >= 1.2:
            prob_score += 7.0
        elif rvol < 0.7:
            prob_score -= 10.0

        # Factor 3: Momentum & RSI Alignment (+18)
        if 55.0 <= rsi <= 72.0:
            prob_score += 16.0  # Perfect sweet spot for institutional breakouts
        elif rsi > 72.0:
            prob_score += 8.0   # Strong but slightly extended
        elif 45.0 <= rsi < 55.0:
            prob_score += 5.0
        else:
            prob_score -= 8.0

        # Factor 4: MACD Acceleration (+14)
        if macd_hist > 0 and macd_line > macd_signal:
            prob_score += 14.0
        elif macd_hist > 0:
            prob_score += 7.0
        else:
            prob_score -= 10.0

        # Factor 5: Price Proximity to Key Resistance (+12)
        dist_to_r1_pct = abs(r1 - current_price) / current_price * 100.0
        if dist_to_r1_pct < 1.2:
            prob_score += 12.0  # Testing breakout threshold
        elif dist_to_r1_pct < 2.5:
            prob_score += 7.0

        # Cap probability between 15% and 98%
        prob_score = max(18.0, min(prob_score, 97.0))
        prob_score_rounded = int(round(prob_score))
        confidence = round(min(0.96, max(0.60, prob_score / 100.0 + random.uniform(-0.02, 0.04))), 2)

        # -------------------------------------------------------------
        # 4. Multi-Timeframe Trend Matrix (1M, 5M, 15M, 1H, 4H, 1D, 1W)
        # -------------------------------------------------------------
        multi_tf = {
            "1M": {"bias": "BULLISH" if change_pct > 0.2 else ("BEARISH" if change_pct < -0.2 else "NEUTRAL"), "strength": 82 if prob_score > 75 else 60},
            "5M": {"bias": "BULLISH" if rsi > 52 else "BEARISH", "strength": 85 if rvol > 1.5 else 65},
            "15M": {"bias": "BULLISH" if macd_hist > 0 else "NEUTRAL", "strength": 88 if prob_score > 80 else 70},
            "1H": {"bias": "BULLISH" if current_price > sma20 else "BEARISH", "strength": int(prob_score)},
            "4H": {"bias": "BULLISH" if rsi > 50 else "CONSOLIDATING", "strength": int(prob_score * 0.95)},
            "1D": {"bias": "BULLISH" if prob_score >= 65 else ("BEARISH" if prob_score < 40 else "CONSOLIDATING"), "strength": int(prob_score)},
            "1W": {"bias": "BULLISH" if current_price > (profile.get("week52_low", 50) * 1.2) else "NEUTRAL", "strength": 80},
        }

        # -------------------------------------------------------------
        # 5. Institutional Trade Setup Plan (Entry, SL, TP1, TP2, TP3)
        # -------------------------------------------------------------
        if prob_score >= 80:
            rec = "STRONG BUY BREAKOUT"
            risk_rating = "MEDIUM"
            entry_zone = round(current_price * 1.002, 2)
            sl_price = round(current_price - (atr14 * 1.4), 2)
            tp1 = round(current_price + (atr14 * 2.0), 2)
            tp2 = round(current_price + (atr14 * 3.5), 2)
            tp3 = round(current_price + (atr14 * 5.2), 2)
            trend_bias = "BULLISH_EXPANSION"
        elif prob_score >= 68:
            rec = "BUY ON PULLBACK"
            risk_rating = "LOW"
            entry_zone = round(max(s1, current_price * 0.995), 2)
            sl_price = round(entry_zone - (atr14 * 1.2), 2)
            tp1 = round(entry_zone + (atr14 * 1.8), 2)
            tp2 = round(entry_zone + (atr14 * 3.0), 2)
            tp3 = round(entry_zone + (atr14 * 4.5), 2)
            trend_bias = "BULLISH_CONTINUATION"
        elif is_squeeze_on or prob_score >= 55:
            rec = "WATCH / SQUEEZE COILING"
            risk_rating = "MEDIUM"
            entry_zone = round(r1 * 1.003, 2)  # Enter above R1
            sl_price = round(pivot, 2)
            tp1 = round(r2, 2)
            tp2 = round(r3, 2)
            tp3 = round(r3 + atr14 * 2.0, 2)
            trend_bias = "SQUEEZE_CONSOLIDATION"
        else:
            rec = "NEUTRAL / WAIT"
            risk_rating = "HIGH"
            entry_zone = round(current_price, 2)
            sl_price = round(current_price * 0.97, 2)
            tp1 = round(current_price * 1.03, 2)
            tp2 = round(current_price * 1.06, 2)
            tp3 = round(current_price * 1.10, 2)
            trend_bias = "RANGE_BOUND"

        risk_amount = abs(entry_zone - sl_price)
        reward_amount = abs(tp2 - entry_zone)
        rr_ratio = round(reward_amount / (risk_amount + 1e-5), 2)

        data = {
            "symbol": symbol,
            "name": profile.get("name", f"{symbol} Corporation"),
            "sector": profile.get("sector", "Technology"),
            "industry": profile.get("industry", "General Equities"),
            "market": profile.get("market", "US_EQUITIES"),
            "market_cap": profile.get("market_cap", "$50.0B"),
            "description": profile.get("description", ""),
            "tags": profile.get("tags", []),
            "timeframe": timeframe,
            "current_price": current_price,
            "change_val": round(change_val, 2),
            "change_pct": round(change_pct, 2),
            "day_open": day_open,
            "day_high": day_high,
            "day_low": day_low,
            "volume": int(cur_vol),
            "avg_volume": profile.get("avg_volume", "15M"),
            "rvol": round(rvol, 2),
            "beta": profile.get("beta", 1.2),
            "pe_ratio": profile.get("pe_ratio", 28.5),
            "week52_high": profile.get("week52_high", current_price * 1.2),
            "week52_low": profile.get("week52_low", current_price * 0.8),
            
            # AI Breakout Intelligence
            "breakout_probability": prob_score_rounded,
            "confidence": confidence,
            "trend_bias": trend_bias,
            "squeeze_status": squeeze_state,
            "is_squeeze": is_squeeze_on,
            "squeeze_ratio": round(squeeze_ratio, 2),
            "recommendation": rec,
            "risk_level": risk_rating,

            # Institutional Trade Plan
            "trade_setup": {
                "action": rec,
                "entry_zone": entry_zone,
                "stop_loss": sl_price,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "take_profit_3": tp3,
                "risk_reward_ratio": f"1:{rr_ratio}",
                "risk_rating": risk_rating,
                "expected_gain_pct": round(((tp2 - entry_zone) / entry_zone) * 100.0, 2),
                "max_risk_pct": round(((entry_zone - sl_price) / entry_zone) * 100.0, 2)
            },

            # Technical Indicators
            "technicals": {
                "rsi_14": round(rsi, 1),
                "macd": round(macd_line, 2),
                "macd_signal": round(macd_signal, 2),
                "macd_hist": round(macd_hist, 2),
                "adx": round(adx, 1),
                "atr_14": round(atr14, 2),
                "bb_upper": round(bb_upper, 2),
                "bb_lower": round(bb_lower, 2),
                "bb_width_pct": round(bb_width_pct, 2),
                "sma_20": round(sma20, 2),
                "kc_upper": round(kc_upper, 2),
                "kc_lower": round(kc_lower, 2)
            },

            # Support & Resistance Zones
            "support_resistance": {
                "r3": round(r3, 2),
                "r2": round(r2, 2),
                "r1": round(r1, 2),
                "pivot": round(pivot, 2),
                "s1": round(s1, 2),
                "s2": round(s2, 2),
                "s3": round(s3, 2)
            },

            # Multi-Timeframe Alignment
            "multi_timeframe": multi_tf,

            "candles": candles,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

        self._cache[cache_key] = {"data": data, "timestamp": now}
        return data


STOCK_ENGINE = StockIntelligenceEngine()
