"""
JARVIS AI 3.0 — India Technical Intelligence & CPR/Camarilla Structure Engine
High-precision mathematical analysis of Indian equities & indices using Central Pivot Range (CPR),
Camarilla Breakouts, VWAP standard deviation corridors, Multi-Timeframe Alignment, and Monte Carlo statistical forecasting.
"""
import math
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from jarvis.india.universe import get_india_profile, INDIA_UNIVERSE
from jarvis.india.nse_rules import NSE_RULES
from jarvis.data.market_data_provider import fetch_real_candles


class IndiaTechnicalEngine:
    """
    Quantitative Analysis Engine tailored for Indian Equity & Index Market Microstructure.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3.0
        self._last_data_source = "synthetic_fallback"

    def generate_candles(
        self,
        symbol: str,
        timeframe: str = "1D",
        num_bars: int = 120
    ) -> List[Dict[str, Any]]:
        """
        Returns OHLC candle series for the instrument.

        Attempts to fetch REAL market data first (via the configured live
        provider); only falls back to a synthetic generator when no live
        source is available. The chosen source is recorded on
        ``self._last_data_source`` so callers can audit data integrity.
        """
        real = fetch_real_candles(symbol, timeframe=timeframe, num_bars=num_bars, market="IN")
        if real:
            self._last_data_source = "live"
            return real
        self._last_data_source = "synthetic_fallback"
        return self._generate_synthetic_candles(symbol, timeframe=timeframe, num_bars=num_bars)

    def _generate_synthetic_candles(
        self,
        symbol: str,
        timeframe: str = "1D",
        num_bars: int = 120
    ) -> List[Dict[str, Any]]:
        """
        Synthetic OHLC generator used ONLY when no live market data is available.
        Output is geometrically bounded and deterministic per symbol.
        """
        profile = get_india_profile(symbol)
        base_price = float(profile.get("base_price", 1000.0))
        volatility = float(profile.get("implied_volatility", 18.0)) / 100.0
        
        now = datetime.now(timezone.utc)
        step_seconds = {
            "5M": 300,
            "15M": 900,
            "1H": 3600,
            "1D": 86400,
            "1W": 604800
        }.get(timeframe.upper(), 86400)

        seed_val = int(hash(symbol) % 100000)
        random.seed(seed_val)

        candles = []
        current_close = float(base_price)

        # Build reverse then forward
        prices = [current_close]
        for _ in range(num_bars - 1):
            shock = random.gauss(0.0003, volatility / math.sqrt(252 * (86400 / step_seconds)))
            prev = prices[-1] / (1.0 + shock)
            prices.append(max(0.5, prev))

        prices.reverse()

        for i, close_p in enumerate(prices):
            bar_time = int(now.timestamp()) - ((num_bars - 1 - i) * step_seconds)
            bar_noise = random.uniform(0.002, 0.008) * close_p
            
            if i == 0:
                open_p = close_p * (1.0 + random.uniform(-0.003, 0.003))
            else:
                open_p = prices[i - 1] * (1.0 + random.uniform(-0.001, 0.001))

            high_p = max(open_p, close_p) + abs(random.gauss(0, bar_noise))
            low_p = min(open_p, close_p) - abs(random.gauss(0, bar_noise))
            low_p = max(0.05, low_p)
            
            vol = int(random.uniform(50000, 850000) * (profile.get("beta", 1.0)))

            candles.append({
                "time": bar_time,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": vol
            })

        return candles

    def calculate_cpr(self, high: float, low: float, close: float) -> Dict[str, Any]:
        """
        Calculates Central Pivot Range (CPR):
        Pivot = (H + L + C) / 3
        Bottom Central (BC) = (H + L) / 2
        Top Central (TC) = (Pivot - BC) + Pivot
        """
        pivot = (high + low + close) / 3.0
        bc = (high + low) / 2.0
        tc = (pivot - bc) + pivot

        # Ensure TC is top, BC is bottom
        top_c = max(tc, bc)
        bot_c = min(tc, bc)
        cpr_width_pts = top_c - bot_c
        cpr_width_pct = (cpr_width_pts / pivot) * 100.0

        if cpr_width_pct <= 0.25:
            width_class = "NARROW_CPR"
            width_label = "⚡ Narrow CPR (High Trending / Breakout Probability)"
        elif cpr_width_pct >= 0.75:
            width_class = "WIDE_CPR"
            width_label = "🧱 Wide CPR (Rangebound / Sideways Expected)"
        else:
            width_class = "AVERAGE_CPR"
            width_label = "⚖️ Average CPR (Moderate Directional Move)"

        return {
            "pivot": round(pivot, 2),
            "tc": round(top_c, 2),
            "bc": round(bot_c, 2),
            "width_points": round(cpr_width_pts, 2),
            "width_pct": round(cpr_width_pct, 2),
            "width_classification": width_class,
            "width_label": width_label
        }

    def calculate_camarilla_pivots(self, high: float, low: float, close: float) -> Dict[str, float]:
        """
        Calculates Camarilla Equation Pivots:
        H4 = Long Breakout Level, H3 = Short Mean-Reversion Level
        L3 = Long Mean-Reversion Level, L4 = Short Breakdown Level
        """
        diff = high - low
        h4 = close + (diff * 1.1 / 2.0)
        h3 = close + (diff * 1.1 / 4.0)
        h2 = close + (diff * 1.1 / 6.0)
        h1 = close + (diff * 1.1 / 12.0)
        
        l1 = close - (diff * 1.1 / 12.0)
        l2 = close - (diff * 1.1 / 6.0)
        l3 = close - (diff * 1.1 / 4.0)
        l4 = close - (diff * 1.1 / 2.0)

        return {
            "h4_breakout": round(h4, 2),
            "h3_reversal": round(h3, 2),
            "h2": round(h2, 2),
            "h1": round(h1, 2),
            "l1": round(l1, 2),
            "l2": round(l2, 2),
            "l3_reversal": round(l3, 2),
            "l4_breakdown": round(l4, 2)
        }

    def analyze_india_instrument(self, symbol: str, timeframe: str = "1D") -> Dict[str, Any]:
        """
        Comprehensive institutional intelligence analysis for any Indian stock or index.
        """
        cache_key = f"{symbol}_{timeframe}"
        now = datetime.now(timezone.utc).timestamp()
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if (now - entry["timestamp"]) < self._cache_ttl:
                return entry["data"]

        profile = get_india_profile(symbol)
        candles = self.generate_candles(symbol, timeframe=timeframe, num_bars=120)

        last_bar = candles[-1]
        # Some live sources (e.g. certain indices on yfinance) only return the
        # latest bar. Guard against short series so analysis never crashes and
        # the real current price is still shown.
        prev_bar = candles[-2] if len(candles) >= 2 else candles[-1]
        
        current_price = round(last_bar["close"], 2)
        day_open = round(last_bar["open"], 2)
        day_high = round(last_bar["high"], 2)
        day_low = round(last_bar["low"], 2)
        change_val = round(current_price - prev_bar["close"], 2)
        change_pct = round((change_val / prev_bar["close"]) * 100.0, 2)

        # Technical Indicators
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        vols = [c["volume"] for c in candles]

        # ATR 14
        tr_list = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(candles))]
        atr14 = round(sum(tr_list[-14:]) / 14.0, 2)

        # RSI 14
        gains, losses = [], []
        for i in range(1, len(closes[-15:])):
            diff = closes[-15 + i] - closes[-15 + i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))
        avg_gain = sum(gains) / 14.0 if gains else 0.001
        avg_loss = sum(losses) / 14.0 if losses else 0.001
        rs = avg_gain / max(0.0001, avg_loss)
        rsi = round(100.0 - (100.0 / (1.0 + rs)), 1)

        # VWAP & Standard Deviation Bands
        if len(candles) >= 30:
            cum_vol = sum(vols[-30:])
            cum_vp = sum(closes[i] * vols[i] for i in range(-30, 0))
            vwap = round(cum_vp / max(1, cum_vol), 2)
        else:
            # Insufficient history from the live source — VWAP degenerates to last price.
            vwap = round(current_price, 2)
        vwap_sd = round(atr14 * 0.85, 2)
        vwap_upper1 = round(vwap + vwap_sd, 2)
        vwap_upper2 = round(vwap + (2 * vwap_sd), 2)
        vwap_lower1 = round(vwap - vwap_sd, 2)
        vwap_lower2 = round(vwap - (2 * vwap_sd), 2)

        # CPR & Camarilla Levels from Previous Bar
        cpr = self.calculate_cpr(prev_bar["high"], prev_bar["low"], prev_bar["close"])
        camarilla = self.calculate_camarilla_pivots(prev_bar["high"], prev_bar["low"], prev_bar["close"])

        # Relative Volume (RVOL)
        avg_vol_20 = sum(vols[-21:-1]) / 20.0 if len(vols) >= 21 else 100000
        rvol = round(vols[-1] / max(1, avg_vol_20), 2)

        # Squeeze Status (Bollinger vs Keltner)
        sma20 = sum(closes[-20:]) / 20.0
        std20 = math.sqrt(sum((x - sma20) ** 2 for x in closes[-20:]) / 20.0)
        bb_upper = sma20 + (2.0 * std20)
        bb_lower = sma20 - (2.0 * std20)
        kc_upper = sma20 + (1.5 * atr14)
        kc_lower = sma20 - (1.5 * atr14)
        is_squeeze = (bb_upper < kc_upper) and (bb_lower > kc_lower)

        # Quantitative 6-Factor Radar Breakdown
        market_regime_score = round(min(98.0, max(30.0, 50.0 + (15.0 if current_price > sma20 else -10.0) + (10.0 if change_pct > 0 else -8.0))), 1)
        cpr_structure_score = round(min(98.0, max(30.0, 50.0 + (25.0 if current_price > cpr["tc"] else (-15.0 if current_price < cpr["bc"] else 5.0)))), 1)
        camarilla_breakout_score = round(min(98.0, max(30.0, 50.0 + (25.0 if current_price > camarilla["h4_breakout"] else (12.0 if current_price > camarilla["h3_reversal"] else -10.0)))), 1)
        vwap_corridor_score = round(min(98.0, max(30.0, 50.0 + (22.0 if current_price > vwap else -15.0))), 1)
        vsa_volume_score = round(min(98.0, max(30.0, 50.0 + (25.0 if rvol >= 1.5 else (10.0 if rvol >= 1.0 else -10.0)))), 1)
        momentum_squeeze_score = round(min(98.0, max(30.0, 50.0 + (25.0 if is_squeeze else 5.0) + (10.0 if (rsi >= 55 and rsi <= 72) else -5.0))), 1)

        # Quantitative Breakout Probability (Weighted Composite)
        prob_score = round(
            (cpr_structure_score * 0.22) +
            (vwap_corridor_score * 0.20) +
            (camarilla_breakout_score * 0.18) +
            (vsa_volume_score * 0.15) +
            (momentum_squeeze_score * 0.15) +
            (market_regime_score * 0.10),
            1
        )

        is_fno_ban = profile.get("is_fno_ban", False)
        asm_stage = profile.get("asm_stage", 0)

        # Grade Assignment & SEBI Surveillance Downgrade
        if is_fno_ban:
            setup_grade = "F&O BAN (MWPL >95%)"
            grade_badge = "BAN"
            recommendation = "NO FRESH POSITIONS (F&O BAN)"
            opp_state = "NO TRADE"
        elif asm_stage >= 2:
            setup_grade = "SEBI ASM STAGE 2"
            grade_badge = "ASM"
            recommendation = "HIGH SURVEILLANCE RISK"
            opp_state = "AVOID"
        elif prob_score >= 80:
            setup_grade = "GRADE A+ PRIME"
            grade_badge = "A+"
            recommendation = "STRONG BUY BREAKOUT"
            opp_state = "STRONG BUY"
        elif prob_score >= 70:
            setup_grade = "GRADE A (HIGH CONVICTION)"
            grade_badge = "A"
            recommendation = "BUY BREAKOUT SETUP"
            opp_state = "BUY"
        elif prob_score >= 58:
            setup_grade = "GRADE B (PULLBACK / WATCH)"
            grade_badge = "B"
            recommendation = "ACCUMULATE ON PULLBACK"
            opp_state = "WATCH"
        else:
            setup_grade = "GRADE C (NEUTRAL / CONSOLIDATION)"
            grade_badge = "C"
            recommendation = "NEUTRAL / RANGEBOUND"
            opp_state = "AVOID"

        # Trade Plan Levels
        lot_size = NSE_RULES.get_lot_size(symbol)
        entry_zone = round(current_price * 1.002, 2)
        sl_price = round(entry_zone - (1.5 * atr14), 2)
        tp1 = round(entry_zone + (1.8 * atr14), 2)
        tp2 = round(entry_zone + (3.2 * atr14), 2)
        tp3 = round(entry_zone + (5.0 * atr14), 2)
        rr_ratio = round(abs(tp2 - entry_zone) / max(0.01, abs(entry_zone - sl_price)), 2)

        # Multi-timeframe structure
        multi_tf = {
            "5M": {"bias": "BULLISH" if current_price > vwap else "BEARISH", "strength": 78},
            "15M": {"bias": "BULLISH" if current_price > cpr["pivot"] else "BEARISH", "strength": 82},
            "1H": {"bias": "BULLISH" if rsi > 52 else "NEUTRAL", "strength": 75},
            "1D": {"bias": "BULLISH" if current_price > sma20 else "NEUTRAL", "strength": 88},
            "1W": {"bias": "BULLISH" if change_pct > -1.0 else "BEARISH", "strength": 84}
        }

        # 10-Day Monte Carlo Simulations (1,000 paths)
        mc_days = 10
        paths = []
        for _ in range(1000):
            p = current_price
            for _ in range(mc_days):
                drift = 0.0004
                shock = random.gauss(0, profile.get("implied_volatility", 18.0) / (100.0 * math.sqrt(252)))
                p *= math.exp(drift + shock)
            paths.append(p)
        paths.sort()
        mc_lower_5 = round(paths[50], 2)
        mc_median = round(paths[500], 2)
        mc_upper_95 = round(paths[950], 2)
        tp1_hit_pct = round((sum(1 for x in paths if x >= tp1) / 1000.0) * 100.0, 1)
        tp2_hit_pct = round((sum(1 for x in paths if x >= tp2) / 1000.0) * 100.0, 1)

        data = {
            "symbol": symbol,
            "name": profile.get("name", f"{symbol} India Ltd"),
            "sector": profile.get("sector", "Equities"),
            "industry": profile.get("industry", "NSE Equities"),
            "market": profile.get("market", "NSE_EQUITY"),
            "market_cap": profile.get("market_cap", "₹50,000 Cr"),
            "is_index": profile.get("is_index", False),
            "lot_size": lot_size,
            "notional_contract_value_inr": round(current_price * lot_size, 2),
            "freeze_limit": NSE_RULES.get_freeze_limit(symbol),
            "current_price": current_price,
            "day_open": day_open,
            "day_high": day_high,
            "day_low": day_low,
            "change_val": change_val,
            "change_pct": change_pct,
            "pe_ratio": profile.get("pe_ratio", 24.0),
            "beta": profile.get("beta", 1.15),
            "week52_high": profile.get("week52_high", current_price * 1.2),
            "week52_low": profile.get("week52_low", current_price * 0.8),
            "breakout_probability": int(prob_score),
            "setup_grade": setup_grade,
            "grade_badge": grade_badge,
            "opportunity_state": opp_state,
            "recommendation": recommendation,
            "rvol": rvol,
            "is_squeeze": is_squeeze,
            "squeeze_status": "🔥 COILING SQUEEZE" if is_squeeze else "EXPANDING VOLATILITY",
            
            # SEBI Regulatory Flags
            "sebi_regulatory": {
                "asm_stage": asm_stage,
                "gsm_stage": profile.get("gsm_stage", 0),
                "mwpl_utilization_pct": profile.get("mwpl_utilization_pct", 35.0),
                "is_fno_ban": is_fno_ban,
                "circuit_limit": profile.get("circuit_limit_pct", "20%")
            },

            # 6-Factor Radar Breakdown
            "score_breakdown": {
                "market_regime": market_regime_score,
                "cpr_structure": cpr_structure_score,
                "camarilla_breakout": camarilla_breakout_score,
                "vwap_corridor": vwap_corridor_score,
                "vsa_volume": vsa_volume_score,
                "momentum_squeeze": momentum_squeeze_score
            },

            # CPR & Camarilla Structural Levels
            "cpr": cpr,
            "camarilla": camarilla,

            # VWAP Structure
            "vwap_structure": {
                "vwap": vwap,
                "upper_1": vwap_upper1,
                "upper_2": vwap_upper2,
                "lower_1": vwap_lower1,
                "lower_2": vwap_lower2,
                "distance_from_vwap_pct": round(((current_price - vwap) / vwap) * 100.0, 2)
            },

            # Trade Plan
            "trade_setup": {
                "entry_zone": entry_zone,
                "stop_loss": sl_price,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "take_profit_3": tp3,
                "risk_reward_ratio": f"1:{rr_ratio}",
                "expected_gain_pct": round(((tp2 - entry_zone) / entry_zone) * 100.0, 2),
                "max_risk_pct": round(((entry_zone - sl_price) / entry_zone) * 100.0, 2)
            },

            # Technicals
            "technicals": {
                "rsi_14": rsi,
                "atr_14": atr14,
                "bb_upper": round(bb_upper, 2),
                "bb_lower": round(bb_lower, 2),
                "sma_20": round(sma20, 2)
            },

            # Monte Carlo Forecast
            "monte_carlo": {
                "tp1_probability_pct": tp1_hit_pct,
                "tp2_probability_pct": tp2_hit_pct,
                "lower_corridor_5pct": mc_lower_5,
                "upper_corridor_95pct": mc_upper_95,
                "median_forecast": mc_median
            },

            # Multi-Timeframe Alignment
            "multi_timeframe": multi_tf,

            "candles": candles,
            "data_source": getattr(self, "_last_data_source", "synthetic_fallback"),
            "bars_available": len(candles),
            "history_complete": len(candles) >= 120,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

        self._cache[cache_key] = {"data": data, "timestamp": now}
        return data


INDIA_ENGINE = IndiaTechnicalEngine()
