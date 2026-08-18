"""
JARVIS AI 3.0 — Explainable Reasoning Engine.
Generates structured natural-language rationales and decision explainability audit records.
"""
from typing import Dict, List, Any
from jarvis.data.schemas import DecisionObject

class ReasoningEngine:
    """Produces institutional-grade structured explanations for every trade decision."""
    
    @staticmethod
    def generate_explanation(decision: DecisionObject) -> str:
        d = decision
        lines = [
            f"=== JARVIS 3.0 DECISION EXPLANATION [{d.symbol}] ===",
            f"ACTION: {d.decision} ({d.bias}) | STRATEGY: {d.strategy}",
            f"CALIBRATED WIN PROBABILITY: {d.probabilities.get(d.bias.lower(), 0.5)*100:.1f}% | EXPECTED VALUE: ${d.expected_value:.2f}",
            f"REGIME: {d.regime.primary_regime.value} (Confidence: {d.regime.confidence*100:.0f}%)",
            "",
            "1. CONFLUENCE FACTORS (BULL/BEAR CASE):"
        ]
        case_items = d.bull_case if d.bias == "BUY" else (d.bear_case if d.bias == "SELL" else ["Neutral equilibrium"])
        for item in case_items:
            lines.append(f"  ✓ {item}")

        lines.append("")
        lines.append(f"2. ADVERSARIAL ANALYSIS & DEVIL'S ADVOCATE (Penalty: -{d.adversarial_penalty:.1f} pts):")
        for risk in d.risk_factors:
            lines.append(f"  ⚠ {risk}")

        lines.append("")
        lines.append("3. INVALIDATION CRITERIA ('What Would Change My Mind'):")
        for inv in d.invalidation_levels:
            lines.append(f"  ✗ {inv}")

        lines.append("")
        lines.append(f"4. TRADE QUALITY GATE STATUS: {'PASSED' if d.quality_gate.passed else 'FAILED'}")
        if not d.quality_gate.passed:
            lines.append(f"  Blocked Reasons: {', '.join(d.quality_gate.failing_reasons)}")

        lines.append("=====================================================")
        return "\n".join(lines)
