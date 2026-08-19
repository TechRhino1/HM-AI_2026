"""
JARVIS AI 3.0 — Market Structure Analyst Agent.
Features:
- Fast Intraday Structure Inversion & Breakdown Detection (M5/M15 CHoCH & BOS)
- Strict Institutional Premium vs Discount Equilibrium Filtering
- Order Block & Liquidity Pool Boundary Mapping
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
        vol = context.volatility
        c_price = context.current_price
        evidence = []
        risk_factors = []

        score = 50.0
        bias = st.bias

        # 1. Structural Geometry: Higher-Highs / Higher-Lows vs Lower-Highs / Lower-Lows
        if st.higher_highs and st.higher_lows:
            score += 20.0
            evidence.append("Sustained Higher-High and Higher-Low market geometry.")
        elif st.lower_highs and st.lower_lows:
            score += 20.0
            evidence.append("Sustained Lower-High and Lower-Low market geometry.")

        # 2. Fast Change of Character (CHoCH) & Break of Structure (BOS)
        if st.choch:
            score += 35.0
            if st.choch_type == "BEARISH":
                evidence.append("⚡ FAST INVERSION: Bearish Change of Character (CHoCH) breakdown below swing low.")
            elif st.choch_type == "BULLISH":
                evidence.append("⚡ FAST INVERSION: Bullish Change of Character (CHoCH) breakout above swing high.")

        if st.bos:
            score += 15.0
            if st.bos_type == "BEARISH":
                evidence.append("Confirmed Bearish Break of Structure (BOS) expansion.")
            elif st.bos_type == "BULLISH":
                evidence.append("Confirmed Bullish Break of Structure (BOS) expansion.")

        # 3. Institutional Premium / Discount Zone Awareness
        # Premium/Discount is a risk signal, not a bias override.
        # The Quality Gate has its own independent Premium/Discount check.
        if st.discount_premium_zone == "PREMIUM":
            if bias == "BULLISH":
                risk_factors.append("⚠️ Price in PREMIUM zone — upside may be limited. Monitor for rejection.")
                score -= 10.0
            else:
                score += 15.0
                evidence.append("Institutional Sell Alignment: Price positioned in optimal PREMIUM supply zone for shorting.")
        elif st.discount_premium_zone == "DISCOUNT":
            if bias == "BEARISH":
                risk_factors.append("⚠️ Price in DISCOUNT zone — downside may be limited. Monitor for bounce.")
                score -= 10.0
            else:
                score += 15.0
                evidence.append("Institutional Buy Alignment: Price positioned in optimal DISCOUNT demand zone for longing.")

        # 4. Multi-timeframe trend alignment check
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
            metadata={"demand_zone": st.demand_zone, "supply_zone": st.supply_zone, "zone": st.discount_premium_zone, "choch": st.choch}
        )
