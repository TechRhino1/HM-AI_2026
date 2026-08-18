"""
JARVIS AI 3.0 — Market Structure Analyst Agent.
Answers: What is current structure? Where are key swing points? Has BOS/CHoCH occurred? What invalidates structure?
"""
import time
from typing import Dict, Any
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class StructureAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__(AnalystRole.STRUCTURE)

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        st = context.structure
        evidence = []
        risk_factors = []

        score = 50.0
        bias = st.bias

        if st.higher_highs and st.higher_lows:
            score += 25.0
            evidence.append("Sustained Higher-High and Higher-Low market geometry.")
        elif st.lower_highs and st.lower_lows:
            score += 25.0
            evidence.append("Sustained Lower-High and Lower-Low market geometry.")

        if st.bos:
            score += 15.0
            evidence.append(f"Confirmed Break of Structure (BOS: {st.bos_type}).")
        elif st.choch:
            score += 10.0
            evidence.append(f"Early Change of Character reversal (CHoCH: {st.choch_type}).")

        # Premium / Discount Zone alignment
        if bias == "BULLISH":
            if st.discount_premium_zone == "DISCOUNT":
                score += 10.0
                evidence.append("Price positioned in optimal DISCOUNT zone for buying.")
            elif st.discount_premium_zone == "PREMIUM":
                risk_factors.append("Warning: Price in PREMIUM zone; buying carries overextension risk.")
        elif bias == "BEARISH":
            if st.discount_premium_zone == "PREMIUM":
                score += 10.0
                evidence.append("Price positioned in optimal PREMIUM zone for selling.")
            elif st.discount_premium_zone == "DISCOUNT":
                risk_factors.append("Warning: Price in DISCOUNT zone; selling carries overextension risk.")

        # Multi-timeframe alignment
        mtf = context.mtf_alignment
        if mtf.get("H4") == bias and mtf.get("D1") == bias:
            score += 10.0
            evidence.append("Macro timeframe trend confluence (D1 & H4 aligned).")
        elif mtf.get("H4") != bias and mtf.get("H4") != "NEUTRAL":
            risk_factors.append(f"Higher timeframe structural divergence (H4 is {mtf.get('H4')}).")

        final_score = min(100.0, max(0.0, score))
        confidence = min(0.95, max(0.40, final_score / 100.0))
        elapsed = (time.perf_counter() - t0) * 1000.0

        return AnalystReport(
            role=self.role,
            symbol=context.symbol,
            bias=bias,
            score=round(final_score, 1),
            confidence=round(confidence, 2),
            evidence=evidence,
            risk_factors=risk_factors,
            execution_time_ms=round(elapsed, 2),
            metadata={"demand_zone": st.demand_zone, "supply_zone": st.supply_zone, "zone": st.discount_premium_zone}
        )
