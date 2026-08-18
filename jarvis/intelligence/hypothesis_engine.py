"""
JARVIS AI 3.0 — Competing Hypothesis & Invalidation Engine.
Constructs competing theses (Primary vs Alternative) and explicit invalidation criteria ("What would change my mind?").
"""
from typing import Dict, List, Any
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, DevilAdvocateReport, CompetingHypotheses

class HypothesisEngine:
    """Generates rigorous dialectical market hypotheses and invalidation levels."""
    
    def construct_hypotheses(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        analyst_reports: Dict[str, AnalystReport],
        devil_report: DevilAdvocateReport,
        proposed_action: str
    ) -> CompetingHypotheses:
        st = context.structure
        mom = context.momentum
        vol = context.volatility
        liq = context.liquidity

        primary_evidence = []
        for role, rep in analyst_reports.items():
            if rep.evidence:
                primary_evidence.extend(rep.evidence[:2])

        alternative_evidence = list(devil_report.threats_detected)
        if devil_report.liquidity_traps:
            alternative_evidence.extend(devil_report.liquidity_traps)

        invalidation_criteria = list(devil_report.invalidation_triggers)
        confirmation_conditions = []

        if proposed_action == "BUY":
            primary_thesis = f"Bullish continuation / demand bounce in {regime.primary_regime.value} regime."
            alternative_thesis = "Bearish rejection / liquidity sweep failure breakdown."
            
            # Confidence & Probabilities
            adv_penalty = devil_report.penalty_score
            primary_p = round(max(0.20, min(0.85, 0.72 - (adv_penalty * 0.008))), 2)
            alt_p = round(max(0.10, min(0.60, 0.20 + (adv_penalty * 0.008))), 2)
            no_trade_p = round(max(0.05, 1.0 - primary_p - alt_p), 2)

            invalidation_criteria.append(f"M15 close below recent swing low ({st.demand_zone[0]}).")
            invalidation_criteria.append("Bearish displacement candle breaking demand equilibrium.")
            
            confirmation_conditions.append("M5 bullish displacement with volume absorption.")
            confirmation_conditions.append(f"Hold above demand level {st.demand_zone[0]}.")
            expected_outcome = f"Targeting supply liquidity pool at {st.supply_zone[1]} with minimum 1:2.0 R:R."

        elif proposed_action == "SELL":
            primary_thesis = f"Bearish continuation / supply mitigation in {regime.primary_regime.value} regime."
            alternative_thesis = "Bullish short squeeze / demand support breakout."

            adv_penalty = devil_report.penalty_score
            primary_p = round(max(0.20, min(0.85, 0.72 - (adv_penalty * 0.008))), 2)
            alt_p = round(max(0.10, min(0.60, 0.20 + (adv_penalty * 0.008))), 2)
            no_trade_p = round(max(0.05, 1.0 - primary_p - alt_p), 2)

            invalidation_criteria.append(f"M15 close above recent swing high ({st.supply_zone[1]}).")
            invalidation_criteria.append("Bullish displacement candle breaking supply equilibrium.")

            confirmation_conditions.append("M5 bearish displacement with volume rejection.")
            confirmation_conditions.append(f"Hold below supply level {st.supply_zone[1]}.")
            expected_outcome = f"Targeting demand liquidity pool at {st.demand_zone[0]} with minimum 1:2.0 R:R."

        else:
            primary_thesis = "Indeterminate market equilibrium. Capital preservation active."
            alternative_thesis = "Breakout emergence from range compression."
            primary_p = 0.33
            alt_p = 0.33
            no_trade_p = 0.34
            invalidation_criteria.append("Break of structural range boundaries.")
            confirmation_conditions.append("Wait for confirmed directional displacement.")
            expected_outcome = "No trade execution authorized; observing price action."

        return CompetingHypotheses(
            primary_thesis=primary_thesis,
            primary_probability=primary_p,
            primary_evidence=primary_evidence,
            alternative_thesis=alternative_thesis,
            alternative_probability=alt_p,
            alternative_evidence=alternative_evidence,
            no_trade_probability=no_trade_p,
            invalidation_criteria=invalidation_criteria,
            confirmation_conditions=confirmation_conditions,
            expected_outcome=expected_outcome
        )
