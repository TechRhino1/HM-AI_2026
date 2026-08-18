from typing import Dict, Any

class MarketRegimeEngine:
    def classify_regime(
        self,
        structure: Dict[str, Any],
        trend: Dict[str, Any],
        volatility: Dict[str, Any],
        liquidity: Dict[str, Any]
    ) -> Dict[str, Any]:
        trend_score = trend.get("trend_score", 0)
        vol_state = volatility.get("state", "NORMAL")
        adx = trend.get("adx", 0)
        bos = structure.get("bos", False)
        bos_type = structure.get("bos_type", "")
        choch = structure.get("choch", False)
        sweep = liquidity.get("sweep_detected", False)

        # Default state
        regime = "UNCLEAR_INDETERMINATE"
        confidence = 50.0

        if vol_state == "EXTREME":
            regime = "HIGH_VOLATILITY_SHOCK"
            confidence = 90.0
        elif trend_score >= 60 and adx >= 25:
            regime = "STRONG_TREND_BULLISH"
            confidence = min(85.0 + (trend_score - 60) * 0.3, 98.0)
        elif trend_score <= -60 and adx >= 25:
            regime = "STRONG_TREND_BEARISH"
            confidence = min(85.0 + (abs(trend_score) - 60) * 0.3, 98.0)
        elif bos and vol_state in ["HIGH", "NORMAL"]:
            if bos_type == "BEARISH" or trend_score < 0:
                regime = "BREAKOUT_EXPANSION_BEARISH"
                confidence = 88.0
            elif bos_type == "BULLISH" or trend_score > 0:
                regime = "BREAKOUT_EXPANSION_BULLISH"
                confidence = 88.0
            else:
                regime = "BREAKOUT_EXPANSION"
                confidence = 80.0
        elif trend_score >= 25:
            regime = "MODERATE_TREND_BULLISH"
            confidence = 75.0
        elif trend_score <= -25:
            regime = "MODERATE_TREND_BEARISH"
            confidence = 75.0
        elif sweep or choch:
            regime = "ACCUMULATION_DISTRIBUTION"
            confidence = 78.0
        elif vol_state in ["VERY_LOW", "LOW"] and adx < 20:
            regime = "CONSOLIDATION_COMPRESSION"
            confidence = 82.0
        elif abs(trend_score) < 20 and adx < 20:
            regime = "RANGE_BOUND"
            confidence = 75.0

        return {
            "regime": regime,
            "confidence": round(confidence, 1),
            "trend_score": trend_score,
            "volatility_state": vol_state,
            "adx": adx,
            "bias": "BULLISH" if "BULLISH" in regime else ("BEARISH" if "BEARISH" in regime else "NEUTRAL")
        }
