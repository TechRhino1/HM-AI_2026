"""
JARVIS AI 3.0 — Liquidity & Smart Money Sweep Analyst Agent.
Answers: Where is liquidity? Was liquidity swept? Is this a genuine breakout or a stop-run trap?
"""
import time
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class LiquidityAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__(AnalystRole.LIQUIDITY)

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        liq = context.liquidity
        st = context.structure
        evidence = []
        risk_factors = []

        score = 50.0
        bias = "NEUTRAL"

        if liq.sweep_detected:
            score += 30.0
            if liq.sweep_type == "BULLISH_SWEEP":
                bias = "BULLISH"
                evidence.append(f"Institutional Sell-Side Liquidity Sweep at {liq.sweep_level} with swift rejection.")
            elif liq.sweep_type == "BEARISH_SWEEP":
                bias = "BEARISH"
                evidence.append(f"Institutional Buy-Side Liquidity Sweep at {liq.sweep_level} with swift rejection.")
        else:
            if liq.equal_highs:
                risk_factors.append("Equal Highs resting overhead (potential buy-side liquidity target).")
            if liq.equal_lows:
                risk_factors.append("Equal Lows resting underneath (potential sell-side liquidity target).")

        # Fair value gaps & Order blocks mitigation
        if st.fair_value_gaps:
            recent_fvg = st.fair_value_gaps[-1]
            evidence.append(f"Unmitigated {recent_fvg['type']} provides institutional magnet at {recent_fvg['top']}-{recent_fvg['bottom']}.")
            score += 10.0

        if st.order_blocks:
            recent_ob = st.order_blocks[-1]
            evidence.append(f"High-probability {recent_ob['type']} identified at {recent_ob['mid']}.")
            score += 10.0

        final_score = min(100.0, max(0.0, score))
        confidence = min(0.95, max(0.40, final_score / 100.0))
        elapsed = (time.perf_counter() - t0) * 1000.0

        return AnalystReport(
            role=self.role,
            symbol=context.symbol,
            bias=bias if bias != "NEUTRAL" else st.bias,
            score=round(final_score, 1),
            confidence=round(confidence, 2),
            evidence=evidence,
            risk_factors=risk_factors,
            execution_time_ms=round(elapsed, 2),
            metadata={"sweep": liq.sweep_detected, "sweep_type": liq.sweep_type, "equal_highs": liq.equal_highs, "equal_lows": liq.equal_lows}
        )
