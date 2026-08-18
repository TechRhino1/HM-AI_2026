"""
JARVIS AI 3.0 — Macroeconomic Event & Calendar Analyst Agent.
Answers: Are high-impact economic news releases approaching? Should execution be blocked or thresholds elevated?
"""
import time
from typing import Dict, Any, List
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class MacroAnalyst(BaseAnalyst):
    def __init__(self, news_calendar: Optional[List[Dict[str, Any]]] = None):
        super().__init__(AnalystRole.MACRO)
        self.news_calendar = news_calendar or []

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        evidence = []
        risk_factors = []

        score = 80.0
        bias = "NEUTRAL"

        # Check session
        session = context.session
        if session.is_prime_session:
            score += 15.0
            evidence.append(f"Institutional Prime Session Active ({session.current_session}).")
        else:
            evidence.append(f"Off-hours / Asian liquidity session ({session.current_session}).")

        # Check regime event risk
        if regime.primary_regime.value == "EVENT_RISK":
            score = 20.0
            risk_factors.append("High-impact economic event risk active — capital preservation prioritized.")
        else:
            evidence.append("No active macro blackout window detected.")

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
            metadata={"session": session.current_session, "is_prime": session.is_prime_session}
        )
