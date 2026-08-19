"""
JARVIS AI 3.0 — Volatility & Spread Feasibility Analyst Agent.
Answers: Is volatility expanding or compressing? Is the stop loss distance realistic? Is the spread within acceptable limits?
"""
import time
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class VolatilityAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__(AnalystRole.VOLATILITY)

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        vol = context.volatility
        st = context.structure
        mom = context.momentum
        evidence = []
        risk_factors = []

        score = 70.0
        bias = "NEUTRAL"

        if vol.is_excessive_spread:
            score = 10.0
            risk_factors.append(f"Excessive spread ({vol.current_spread_pips} pips > {vol.max_allowed_spread_pips} max allowed).")
        elif vol.current_spread_pips <= 2.5:
            score += 15.0
            evidence.append(f"Tight institutional spread ({vol.current_spread_pips} pips).")

        if vol.state == "NORMAL":
            score += 15.0
            evidence.append("Optimal volatility conditions for systematic execution.")
            # Normal volatility: align with structure bias
            bias = st.bias if st.bias in ("BULLISH", "BEARISH") else "NEUTRAL"
        elif vol.state == "EXPANSION":
            score += 10.0
            evidence.append("Volatility expanding — favorable for breakout/trend setups.")
            # Expansion: align with momentum direction for trend-following
            if mom.trend_score >= 40:
                bias = "BULLISH"
                evidence.append("Expansion with strong bullish momentum — volatility supports BUY.")
            elif mom.trend_score <= -40:
                bias = "BEARISH"
                evidence.append("Expansion with strong bearish momentum — volatility supports SELL.")
        elif vol.state == "COMPRESSION":
            evidence.append("Volatility compression — breakout or liquidity sweep imminent.")
            # Compression = no directional edge, stay neutral
        elif vol.state == "EXTREME":
            score -= 35.0
            risk_factors.append("Extreme volatility shock active — stop-outs likely due to erratic wicks.")
            # Extreme = dangerous, stay neutral

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
            metadata={"state": vol.state, "atr": vol.atr, "spread": vol.current_spread_pips}
        )
