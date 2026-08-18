import pandas as pd
from typing import Dict, Any, List

class FairValueGapEngine:
    def analyze_fvgs(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < 5:
            return {"fvg_detected": False, "fvg_type": "NONE", "fvg_zone": (0.0, 0.0)}

        # Check last 3 completed candles for FVG
        c1 = df.iloc[-4]
        c2 = df.iloc[-3]
        c3 = df.iloc[-2]
        latest_price = df.iloc[-1]["close"]

        bullish_fvg = c3["low"] > c1["high"]
        bearish_fvg = c3["high"] < c1["low"]

        fvg_detected = False
        fvg_type = "NONE"
        fvg_zone = (0.0, 0.0)

        if bullish_fvg:
            fvg_detected = True
            fvg_type = "BULLISH_FVG"
            fvg_zone = (c1["high"], c3["low"])
        elif bearish_fvg:
            fvg_detected = True
            fvg_type = "BEARISH_FVG"
            fvg_zone = (c3["high"], c1["low"])

        # Check if latest price is currently filling/mitigating the FVG
        price_in_zone = False
        if fvg_detected:
            if fvg_type == "BULLISH_FVG" and (fvg_zone[0] <= latest_price <= fvg_zone[1]):
                price_in_zone = True
            elif fvg_type == "BEARISH_FVG" and (fvg_zone[1] <= latest_price <= fvg_zone[0]):
                price_in_zone = True

        return {
            "fvg_detected": fvg_detected,
            "fvg_type": fvg_type,
            "fvg_zone": fvg_zone,
            "price_in_fvg_zone": price_in_zone
        }
