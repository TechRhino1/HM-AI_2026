"""
JARVIS AI 3.0 — Momentum & Trend Dynamics Analyst Agent.
Answers: Is momentum increasing or exhausting? Is price accelerating? Is there momentum divergence?
"""
import time
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class MomentumAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__(AnalystRole.MOMENTUM)

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        mom = context.momentum
        evidence = []
        risk_factors = []

        score = 50.0
        bias = "NEUTRAL"
        if mom.trend_score >= 30:
            bias = "BULLISH"
            score += 20.0
            evidence.append(f"Strong positive trend momentum (Score: {mom.trend_score}).")
        elif mom.trend_score <= -30:
            bias = "BEARISH"
            score += 20.0
            evidence.append(f"Strong negative trend momentum (Score: {mom.trend_score}).")

        # ADX trend strength
        if mom.adx >= 25.0:
            score += 15.0
            evidence.append(f"High trend strength (ADX: {mom.adx}).")
        elif mom.adx < 18.0:
            risk_factors.append(f"Low trend velocity (ADX: {mom.adx}) indicates choppy momentum.")

        # Acceleration vs Exhaustion
        if mom.acceleration == "ACCELERATING":
            score += 10.0
            evidence.append("Price impulse is accelerating.")
        elif mom.acceleration == "EXHAUSTION":
            score -= 15.0
            risk_factors.append(f"Extreme RSI momentum exhaustion ({mom.rsi}) — pullback likely imminent.")

        # Divergence
        if mom.divergence == "BULLISH_DIVERGENCE":
            if bias == "BULLISH":
                score += 15.0
                evidence.append("Bullish RSI divergence confirms bottoming accumulation.")
            else:
                risk_factors.append("Bullish divergence detected against bearish trend.")
        elif mom.divergence == "BEARISH_DIVERGENCE":
            if bias == "BEARISH":
                score += 15.0
                evidence.append("Bearish RSI divergence confirms topping distribution.")
            else:
                risk_factors.append("Bearish divergence detected against bullish trend.")

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
            metadata={"rsi": mom.rsi, "adx": mom.adx, "acceleration": mom.acceleration, "divergence": mom.divergence}
        )
