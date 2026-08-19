"""
JARVIS AI 3.0 — Advanced Institutional Market Structure Engine.
Detects Swing Pivots (HH, HL, LH, LL), BOS, CHoCH, Order Blocks, Fair Value Gaps (FVG), and Premium/Discount Zones.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from jarvis.data.schemas import StructureContext

class MarketStructureEngine:
    def __init__(self, pivot_window: int = 5):
        self.pivot_window = pivot_window

    def analyze_structure(self, df: pd.DataFrame) -> StructureContext:
        if len(df) < self.pivot_window * 2 + 3:
            return StructureContext(bias="NEUTRAL")

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        opens = df["open"].values
        times = df["time"].values if "time" in df else list(range(len(df)))

        swing_highs = []
        swing_lows = []
        w = self.pivot_window

        # Identify swing pivots
        for i in range(w, len(df) - w):
            if highs[i] == max(highs[i - w:i + w + 1]):
                swing_highs.append({"index": i, "price": float(highs[i]), "time": times[i]})
            if lows[i] == min(lows[i - w:i + w + 1]):
                swing_lows.append({"index": i, "price": float(lows[i]), "time": times[i]})

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return StructureContext(bias="NEUTRAL")

        recent_sh = swing_highs[-1]["price"]
        prev_sh = swing_highs[-2]["price"]
        recent_sl = swing_lows[-1]["price"]
        prev_sl = swing_lows[-2]["price"]
        latest_close = float(closes[-1])

        hh = recent_sh > prev_sh
        hl = recent_sl > prev_sl
        lh = recent_sh < prev_sh
        ll = recent_sl < prev_sl

        bos_bullish = latest_close > recent_sh
        bos_bearish = latest_close < recent_sl
        choch_bullish = (lh and ll) and (latest_close > recent_sh)
        choch_bearish = (hh and hl) and (latest_close < recent_sl)

        bias = "NEUTRAL"
        if hh and hl:
            bias = "BULLISH"
        elif lh and ll:
            bias = "BEARISH"
        elif bos_bullish or choch_bullish:
            bias = "BULLISH"
        elif bos_bearish or choch_bearish:
            bias = "BEARISH"

        # Premium / Discount / Equilibrium Zones
        recent_max = float(highs[-30:].max()) if len(highs) >= 30 else float(highs.max())
        recent_min = float(lows[-30:].min()) if len(lows) >= 30 else float(lows.min())
        equilibrium = (recent_max + recent_min) / 2.0
        range_span = recent_max - recent_min + 1e-9
        position_pct = ((latest_close - recent_min) / range_span) * 100.0

        if position_pct <= 45.0:
            discount_premium_zone = "DISCOUNT"
        elif position_pct >= 55.0:
            discount_premium_zone = "PREMIUM"
        else:
            discount_premium_zone = "EQUILIBRIUM"

        # Supply / Demand Zones
        demand_zone = (round(recent_sl, 4), round(recent_sl * 1.003, 4))
        supply_zone = (round(recent_sh * 0.997, 4), round(recent_sh, 4))

        # Detect Institutional Order Blocks
        order_blocks = []
        for i in range(max(2, len(df) - 15), len(df) - 1):
            # Bullish OB: Bearish candle followed by strong bullish breakout
            if closes[i] < opens[i] and closes[i + 1] > highs[i]:
                order_blocks.append({
                    "type": "BULLISH_ORDER_BLOCK",
                    "high": round(float(highs[i]), 4),
                    "low": round(float(lows[i]), 4),
                    "mid": round(float((highs[i] + lows[i]) / 2.0), 4),
                    "index": i
                })
            # Bearish OB: Bullish candle followed by strong bearish breakdown
            elif closes[i] > opens[i] and closes[i + 1] < lows[i]:
                order_blocks.append({
                    "type": "BEARISH_ORDER_BLOCK",
                    "high": round(float(highs[i]), 4),
                    "low": round(float(lows[i]), 4),
                    "mid": round(float((highs[i] + lows[i]) / 2.0), 4),
                    "index": i
                })

        # Detect Fair Value Gaps (FVG)
        fair_value_gaps = []
        for i in range(max(2, len(df) - 20), len(df)):
            # Bullish FVG: Low of candle i > High of candle i-2
            if lows[i] > highs[i - 2]:
                fair_value_gaps.append({
                    "type": "BULLISH_FVG",
                    "top": round(float(lows[i]), 4),
                    "bottom": round(float(highs[i - 2]), 4),
                    "size": round(float(lows[i] - highs[i - 2]), 4),
                    "index": i
                })
            # Bearish FVG: High of candle i < Low of candle i-2
            elif highs[i] < lows[i - 2]:
                fair_value_gaps.append({
                    "type": "BEARISH_FVG",
                    "top": round(float(lows[i - 2]), 4),
                    "bottom": round(float(highs[i]), 4),
                    "size": round(float(lows[i - 2] - highs[i]), 4),
                    "index": i
                })

        # Horizontal S/R Clustering (Key Levels)
        all_swings = [s["price"] for s in swing_highs] + [s["price"] for s in swing_lows]
        key_levels = []
        visited = set()
        for p in all_swings:
            if p in visited:
                continue
            # cluster within 0.2%
            cluster = [x for x in all_swings if abs(x - p) / (p + 1e-9) <= 0.002]
            if len(cluster) >= 3:
                level_price = sum(cluster) / len(cluster)
                if not any(abs(level_price - k["price"]) / (k["price"] + 1e-9) <= 0.002 for k in key_levels):
                    key_levels.append({"price": round(level_price, 4), "touches": len(cluster)})
            for c in cluster:
                visited.add(c)

        return StructureContext(
            bias=bias,
            higher_highs=hh,
            higher_lows=hl,
            lower_highs=lh,
            lower_lows=ll,
            bos=bos_bullish or bos_bearish,
            bos_type="BULLISH" if bos_bullish else ("BEARISH" if bos_bearish else "NONE"),
            choch=choch_bullish or choch_bearish,
            choch_type="BULLISH" if choch_bullish else ("BEARISH" if choch_bearish else "NONE"),
            demand_zone=demand_zone,
            supply_zone=supply_zone,
            equilibrium_price=round(equilibrium, 4),
            discount_premium_zone=discount_premium_zone,
            order_blocks=order_blocks[-4:],
            fair_value_gaps=fair_value_gaps[-4:],
            key_levels=key_levels
        )
