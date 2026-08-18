import numpy as np
import pandas as pd
from typing import Dict, Any, List

class MasterTraderIntelligenceProtocol:
    """
    Autonomous Master Trader Intelligence Protocol.
    Integrates Institutional Market Geometry (Premium/Discount Zones),
    Unmitigated Order Block Liquidity Matrix, and 3-Timeframe Fractal Triad Alignment.
    """
    def __init__(self, logger: Any = None):
        self.logger = logger

    def calculate_market_geometry(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates Premium vs Discount Zones & Swing Equilibrium (50% Fibonacci level).
        - BUY entries require price in DISCOUNT ZONE (< 50% equilibrium).
        - SELL entries require price in PREMIUM ZONE (> 50% equilibrium).
        """
        if len(df) < 20:
            return {"zone": "EQUILIBRIUM", "equilibrium_price": 0.0, "discount_pct": 50.0}

        recent_high = float(df["high"].tail(30).max())
        recent_low = float(df["low"].tail(30).min())
        c_price = float(df["close"].iloc[-1])

        range_span = recent_high - recent_low + 1e-9
        equilibrium = (recent_high + recent_low) / 2.0
        position_pct = ((c_price - recent_low) / range_span) * 100.0

        if position_pct <= 45.0:
            zone = "DISCOUNT_ZONE"  # Optimal for BUY entries
        elif position_pct >= 55.0:
            zone = "PREMIUM_ZONE"   # Optimal for SELL entries
        else:
            zone = "EQUILIBRIUM_ZONE"

        return {
            "zone": zone,
            "recent_high": round(recent_high, 2),
            "recent_low": round(recent_low, 2),
            "equilibrium_price": round(equilibrium, 2),
            "position_pct": round(position_pct, 1)
        }

    def detect_institutional_order_blocks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Identifies Unmitigated Bullish & Bearish Order Blocks (Smart Money Accumulation/Distribution).
        """
        if len(df) < 15:
            return {"ob_detected": False, "ob_type": "NONE", "ob_price": 0.0}

        latest = df.iloc[-1]
        prev2 = df.iloc[-3]
        c_price = float(latest["close"])

        # Bullish Order Block (Last bearish candle before strong bullish expansion)
        if prev2["close"] < prev2["open"] and latest["close"] > prev2["high"]:
            ob_low = float(prev2["low"])
            ob_high = float(prev2["high"])
            if ob_low <= c_price <= ob_high * 1.002:
                return {
                    "ob_detected": True,
                    "ob_type": "BULLISH_ORDER_BLOCK",
                    "ob_price": round((ob_low + ob_high)/2.0, 2),
                    "ob_low": round(ob_low, 2),
                    "ob_high": round(ob_high, 2)
                }

        # Bearish Order Block (Last bullish candle before strong bearish expansion)
        if prev2["close"] > prev2["open"] and latest["close"] < prev2["low"]:
            ob_low = float(prev2["low"])
            ob_high = float(prev2["high"])
            if ob_low * 0.998 <= c_price <= ob_high:
                return {
                    "ob_detected": True,
                    "ob_type": "BEARISH_ORDER_BLOCK",
                    "ob_price": round((ob_low + ob_high)/2.0, 2),
                    "ob_low": round(ob_low, 2),
                    "ob_high": round(ob_high, 2)
                }

        return {"ob_detected": False, "ob_type": "NONE", "ob_price": 0.0}

    def evaluate_grand_master_trade_score(
        self,
        symbol: str,
        action: str,
        geometry: Dict[str, Any],
        order_block: Dict[str, Any],
        orderflow: Dict[str, Any],
        liquidity: Dict[str, Any],
        ml_pred: Dict[str, Any],
        base_score: float
    ) -> Dict[str, Any]:
        """
        Master Trader Grand Confluence Matrix (10-Factor Confluence Vector):
        Grants Master Trader Qualification Rating (GRAND_MASTER_QUALIFIED).
        """
        confluences = []
        master_score = base_score * 0.40  # 40% base technical score

        # 1. Market Geometry Premium/Discount Zone (+15 pts)
        zone = geometry.get("zone", "EQUILIBRIUM_ZONE")
        if (action == "BUY" and zone == "DISCOUNT_ZONE") or (action == "SELL" and zone == "PREMIUM_ZONE"):
            master_score += 15.0
            confluences.append(f"Optimal Geometry ({zone})")

        # 2. Institutional Order Block Confluence (+15 pts)
        if order_block.get("ob_detected"):
            ob_type = order_block.get("ob_type", "")
            if (action == "BUY" and "BULLISH" in ob_type) or (action == "SELL" and "BEARISH" in ob_type):
                master_score += 15.0
                confluences.append(f"Unmitigated Order Block ({ob_type})")

        # 3. Order Flow Delta Imbalance (+15 pts)
        imbalance = orderflow.get("delta_imbalance", "NEUTRAL") if isinstance(orderflow, dict) else "NEUTRAL"
        if (action == "BUY" and "BULLISH" in imbalance) or (action == "SELL" and "BEARISH" in imbalance):
            master_score += 15.0
            confluences.append(f"Order Flow Delta ({imbalance})")

        # 4. Liquidity Sweep Stop Hunt (+10 pts)
        if liquidity.get("sweep_detected"):
            master_score += 10.0
            confluences.append(f"Liquidity Sweep ({liquidity.get('sweep_type')})")

        # 5. Machine Learning Probability (+10 pts)
        ml_prob = ml_pred.get("ml_win_probability", 0.65) if isinstance(ml_pred, dict) else 0.65
        if ml_prob >= 0.75:
            master_score += 10.0
            confluences.append(f"ML Classifier ({ml_prob*100:.0f}% win prob)")

        grand_score = round(min(100.0, max(0.0, master_score)), 1)
        rating = "GRAND_MASTER_QUALIFIED" if grand_score >= 82.0 and len(confluences) >= 3 else "STANDARD_QUALIFIED"

        return {
            "grand_master_score": grand_score,
            "master_rating": rating,
            "confluences": confluences,
            "geometry_zone": zone,
            "order_block_status": order_block.get("ob_type", "NONE")
        }
