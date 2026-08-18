import numpy as np
import pandas as pd
from typing import Dict, Any, List

class WyckoffAMDPhaseEngine:
    """
    ICT / Wyckoff Accumulation-Manipulation-Distribution (AMD) Institutional Phase Engine.
    Dynamically classifies the current market cycle into:
    1. ACCUMULATION: Liquidity building & range compression.
    2. MANIPULATION (Judas Swing / Spring / Upthrust): Stop hunting liquidity pools (BSL/SSL).
    3. DISTRIBUTION (Expansion): Institutional trend displacement with FVG & BOS.
    4. RE_ACCUMULATION / RE_DISTRIBUTION: Mid-trend continuation mitigation.
    
    Selects tailored strategies for each phase to maximize profitability and R:R ratios.
    """
    def __init__(self, logger: Any = None):
        self.logger = logger

    def analyze_amd_phase(
        self,
        df: pd.DataFrame,
        structure: Dict[str, Any],
        trend: Dict[str, Any],
        volatility: Dict[str, Any],
        orderflow: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        if len(df) < 20:
            return {
                "phase": "ACCUMULATION",
                "phase_detail": "INSUFFICIENT_DATA",
                "confidence": 50.0,
                "strategy": "DEFENSIVE_HOLD",
                "action": "HOLD",
                "target_pool": 0.0,
                "manipulation_level": 0.0,
                "rationale": ["Awaiting more historical bars for phase classification."]
            }

        latest = df.iloc[-1]
        c_price = float(latest["close"])
        c_close = float(latest["close"])
        c_high = float(latest["high"])
        c_low = float(latest["low"])
        c_open = float(latest["open"])
        c_range = c_high - c_low + 1e-9

        # Lookback 24 bars (e.g. 24 hours on H1 or full day range)
        window = df.tail(24)
        range_high = float(window["high"].max())
        range_low = float(window["low"].min())
        range_span = range_high - range_low + 1e-9
        range_mid = (range_high + range_low) / 2.0

        adx = trend.get("adx", 20.0)
        trend_score = trend.get("trend_score", 0)
        vol_state = volatility.get("state", "NORMAL")
        atr = volatility.get("atr", 0.0)
        bos = structure.get("bos", False)
        choch = structure.get("choch", False)
        swing_highs = structure.get("swing_highs", [])
        swing_lows = structure.get("swing_lows", [])

        of_imbalance = orderflow.get("delta_imbalance", "NEUTRAL") if isinstance(orderflow, dict) else "NEUTRAL"
        cvd_trend = orderflow.get("cvd_trend", "FLAT") if isinstance(orderflow, dict) else "FLAT"

        # Rejection wick calculation on latest candle
        upper_wick = c_high - max(c_open, c_close)
        lower_wick = min(c_open, c_close) - c_low
        upper_wick_ratio = upper_wick / c_range
        lower_wick_ratio = lower_wick / c_range

        phase = "ACCUMULATION"
        phase_detail = "RANGE_BUILDING"
        confidence = 70.0
        strategy_name = "ACCUMULATION_RANGE_FADE"
        recommended_action = "HOLD"
        target_pool = range_high if c_price < range_mid else range_low
        manipulation_level = 0.0
        rationale = []

        # Extract numeric prices from swing points
        sh_prices = [float(s["price"]) if isinstance(s, dict) else float(s) for s in swing_highs]
        sl_prices = [float(s["price"]) if isinstance(s, dict) else float(s) for s in swing_lows]

        # =========================================================================
        # 1. DETECT MANIPULATION PHASE (Judas Swing / Spring / Upthrust)
        # =========================================================================
        # Bullish Spring / SSL Liquidity Hunt: Wick pierced range low / swing low & rejected up
        is_spring = False
        if sl_prices and len(sl_prices) >= 2 and c_low < min(sl_prices[-2:]) and c_close > min(sl_prices[-2:]):
            if lower_wick_ratio >= 0.35 or of_imbalance == "BULLISH_ORDER_FLOW":
                is_spring = True
                manipulation_level = min(sl_prices[-2:])

        elif c_low < (range_low - atr * 0.1) and c_close >= range_low:
            if lower_wick_ratio >= 0.35:
                is_spring = True
                manipulation_level = range_low

        # Bearish Upthrust / BSL Liquidity Hunt: Wick pierced range high / swing high & rejected down
        is_upthrust = False
        if sh_prices and len(sh_prices) >= 2 and c_high > max(sh_prices[-2:]) and c_close < max(sh_prices[-2:]):
            if upper_wick_ratio >= 0.35 or of_imbalance == "BEARISH_ORDER_FLOW":
                is_upthrust = True
                manipulation_level = max(sh_prices[-2:])

        elif c_high > (range_high + atr * 0.1) and c_close <= range_high:
            if upper_wick_ratio >= 0.35:
                is_upthrust = True
                manipulation_level = range_high

        if is_spring:
            phase = "MANIPULATION"
            phase_detail = "BULLISH_SPRING_SSL_SWEEP"
            confidence = 88.0
            strategy_name = "WYCKOFF_SPRING_MANIPULATION_BUY"
            recommended_action = "BUY"
            target_pool = range_high
            rationale.append(f"Institutional Spring (SSL Hunt) at {manipulation_level:.2f}. Lower wick rejection: {lower_wick_ratio*100:.0f}%. Targeting Buy-Side Liquidity pool ({range_high:.2f}).")

        elif is_upthrust:
            phase = "MANIPULATION"
            phase_detail = "BEARISH_UPTHRUST_BSL_SWEEP"
            confidence = 88.0
            strategy_name = "WYCKOFF_UPTHRUST_MANIPULATION_SELL"
            recommended_action = "SELL"
            target_pool = range_low
            rationale.append(f"Institutional Judas Swing / Upthrust (BSL Hunt) at {manipulation_level:.2f}. Upper wick rejection: {upper_wick_ratio*100:.0f}%. Targeting Sell-Side Liquidity pool ({range_low:.2f}).")

        # =========================================================================
        # 2. DETECT DISTRIBUTION / EXPANSION PHASE (True Institutional Trend)
        # =========================================================================
        elif bos or (adx >= 25 and abs(trend_score) >= 50):
            if trend_score > 0 or structure.get("bos_type") == "BULLISH":
                phase = "DISTRIBUTION"
                phase_detail = "BULLISH_TREND_EXPANSION"
                confidence = 92.0
                strategy_name = "AMD_DISTRIBUTION_MOMENTUM_BUY"
                recommended_action = "BUY"
                target_pool = round(c_price + (atr * 3.5), 2)
                rationale.append(f"Institutional Distribution expansion active (ADX: {adx:.1f}, Trend: +{trend_score}). Entering on FVG / EMA discount mitigation.")
            else:
                phase = "DISTRIBUTION"
                phase_detail = "BEARISH_TREND_EXPANSION"
                confidence = 92.0
                strategy_name = "AMD_DISTRIBUTION_MOMENTUM_SELL"
                recommended_action = "SELL"
                target_pool = round(c_price - (atr * 3.5), 2)
                rationale.append(f"Institutional Distribution downward displacement active (ADX: {adx:.1f}, Trend: {trend_score}). Entering on FVG / EMA premium mitigation.")

        # =========================================================================
        # 3. DETECT RE-ACCUMULATION / RE-DISTRIBUTION (Continuation)
        # =========================================================================
        elif choch:
            phase = "RE_ACCUMULATION" if trend_score > 0 else "RE_DISTRIBUTION"
            phase_detail = "STRUCTURAL_TRANSITION_CHOCH"
            confidence = 80.0
            strategy_name = "STRUCTURAL_CHOCH_REVERSAL"
            recommended_action = "BUY" if trend_score > 0 else "SELL"
            target_pool = range_high if trend_score > 0 else range_low
            rationale.append(f"Change of Character (CHoCH) detected. Transitioning into {phase} phase.")

        # =========================================================================
        # 4. ACCUMULATION PHASE (Range Compression / Liquidity Building)
        # =========================================================================
        else:
            phase = "ACCUMULATION"
            phase_detail = "CONSOLIDATION_COMPRESSION"
            confidence = 75.0
            if range_span >= (atr * 2.0):
                # Wide range -> mean reversion between boundaries
                if c_price <= (range_low + atr * 0.5):
                    strategy_name = "ACCUMULATION_DEMAND_BOUNCE"
                    recommended_action = "BUY"
                    target_pool = range_high
                    rationale.append(f"Price at lower accumulation boundary ({range_low:.2f}). Buying support targeting upper range ({range_high:.2f}).")
                elif c_price >= (range_high - atr * 0.5):
                    strategy_name = "ACCUMULATION_SUPPLY_FADE"
                    recommended_action = "SELL"
                    target_pool = range_low
                    rationale.append(f"Price at upper accumulation boundary ({range_high:.2f}). Selling resistance targeting lower range ({range_low:.2f}).")
                else:
                    strategy_name = "ACCUMULATION_WAIT_FOR_MANIPULATION"
                    recommended_action = "HOLD"
                    rationale.append(f"Price at accumulation equilibrium ({range_mid:.2f}). Holding for Judas Swing / Manipulation trigger.")
            else:
                strategy_name = "ACCUMULATION_WAIT_FOR_MANIPULATION"
                recommended_action = "HOLD"
                rationale.append("Tight consolidation compression. Institutional liquidity pools forming; awaiting manipulation breakout.")

        return {
            "phase": phase,
            "phase_detail": phase_detail,
            "confidence": round(confidence, 1),
            "strategy": strategy_name,
            "recommended_action": recommended_action,
            "target_pool": round(target_pool, 2),
            "manipulation_level": round(manipulation_level, 2),
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
            "range_mid": round(range_mid, 2),
            "rationale": rationale
        }
