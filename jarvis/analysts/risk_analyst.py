"""
JARVIS AI 3.0 — Risk & Reward Feasibility Analyst Agent.
Answers: Is the risk-to-reward ratio viable? What is the expected loss if invalidated? What is the baseline viability?
"""
import time
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class RiskAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__(AnalystRole.RISK)

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        vol = context.volatility
        st = context.structure
        evidence = []
        risk_factors = []

        score = 65.0
        bias = st.bias

        # Determine structural R:R distance
        c_price = context.current_price
        if bias == "BULLISH":
            sl_dist = abs(c_price - st.demand_zone[0]) if st.demand_zone[0] > 0 else (vol.atr * 1.5)
            tp_dist = abs(st.supply_zone[1] - c_price) if st.supply_zone[1] > c_price else (vol.atr * 3.0)
        elif bias == "BEARISH":
            sl_dist = abs(st.supply_zone[1] - c_price) if st.supply_zone[1] > 0 else (vol.atr * 1.5)
            tp_dist = abs(c_price - st.demand_zone[0]) if st.demand_zone[0] < c_price and st.demand_zone[0] > 0 else (vol.atr * 3.0)
        else:
            sl_dist = vol.atr * 1.5
            tp_dist = vol.atr * 2.0

        rr_ratio = round(tp_dist / (sl_dist + 1e-9), 2) if sl_dist > 0 else 1.0

        if rr_ratio >= 2.5:
            score += 25.0
            evidence.append(f"Highly favorable structural Risk-to-Reward ratio (1:{rr_ratio:.2f}).")
        elif rr_ratio >= 1.5:
            score += 15.0
            evidence.append(f"Acceptable Risk-to-Reward ratio (1:{rr_ratio:.2f}).")
        else:
            score -= 20.0
            risk_factors.append(f"Sub-optimal structural R:R ratio (1:{rr_ratio:.2f} < 1:1.50).")

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
            metadata={"rr_ratio": rr_ratio, "sl_dist": round(sl_dist, 4), "tp_dist": round(tp_dist, 4)}
        )
