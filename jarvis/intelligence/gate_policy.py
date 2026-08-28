"""
JARVIS AI 4.0 — Adaptive Quality-Gate Policy.

Per the user's directive, gate strictness is decided automatically by the AI:
- CRITICAL gates (market session, drawdown, margin, event-regime) are ALWAYS hard
  (they protect capital and are never softened).
- NON-critical gates (order-flow, AI score, premium/discount, spread, win-prob, EV)
  can be *softened* — converted into a confidence penalty instead of a hard block —
  but ONLY when we have evidence the strategy is currently profitable in this regime
  (recent win-rate above threshold) and only a small number are failing.

If there is no performance evidence yet, the policy defaults to BLOCK (identical to
today's behaviour), so it can never increase risk on an untuned system.
"""
from typing import List, Dict, Any, Tuple, Optional


# Gates that must always block when they fail (capital-protection / validity).
HARD_GATES = {
    "Market Session Open",
    "Drawdown Safety Guard",
    "Margin Capacity Limit",
    "Regime Viability",
}


class AdaptiveGatePolicy:
    def __init__(self, max_soft_fail: int = 3, min_recent_win_rate: float = 0.45):
        self.max_soft_fail = max_soft_fail
        self.min_recent_win_rate = min_recent_win_rate

    def decide(self, failing_reasons: List[str], recent_win_rate: Optional[float]) -> Tuple[str, List[str]]:
        """Return (decision, gates_to_soften).

        decision is one of: PASS, SOFTEN, BLOCK.
        """
        hard = [g for g in failing_reasons if g in HARD_GATES]
        soft = [g for g in failing_reasons if g not in HARD_GATES]

        if hard:
            return ("BLOCK", hard)
        if not soft:
            return ("PASS", [])
        # No performance evidence -> keep current (strict) behaviour.
        if recent_win_rate is None or recent_win_rate < self.min_recent_win_rate:
            return ("BLOCK", soft)
        if len(soft) <= self.max_soft_fail:
            return ("SOFTEN", soft)
        return ("BLOCK", soft)

    @staticmethod
    def confidence_penalty(softened_gates: List[str]) -> float:
        """Reduce model_confidence by 0.03 per softened gate (capped) — was 0.04, now gentler."""
        return min(0.12, 0.03 * len(softened_gates))
