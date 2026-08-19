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
        c_price = context.current_price

        primary_evidence = []
        for role, rep in analyst_reports.items():
            if rep.evidence:
                primary_evidence.extend(rep.evidence[:2])

        alternative_evidence = list(devil_report.threats_detected)
        if devil_report.liquidity_traps:
            alternative_evidence.extend(devil_report.liquidity_traps)

        invalidation_criteria = list(devil_report.invalidation_triggers)
        confirmation_conditions = []
        
        structural_invalidation_distance = 0.0

        # §18: Calculate dynamic confluence base from analyst votes, momentum, and MTF alignment
        bull_score = sum(r.score for r in analyst_reports.values() if r.bias == "BULLISH")
        bear_score = sum(r.score for r in analyst_reports.values() if r.bias == "BEARISH")
        total_score = max(1.0, sum(r.score for r in analyst_reports.values()))

        # MTF alignment bonus
        mtf_align = getattr(context, "mtf_alignment", {})
        mtf_bonus = 0.0
        if proposed_action == "BUY" and mtf_align.get("macro") == "BULLISH":
            mtf_bonus += 0.04
        elif proposed_action == "SELL" and mtf_align.get("macro") == "BEARISH":
            mtf_bonus += 0.04

        # Trend persistence factor
        trend_persist = getattr(mom, "trend_persistence", 0)
        persist_factor = min(0.06, max(-0.06, trend_persist * 0.003))

        adv_penalty = devil_report.penalty_score

        if proposed_action == "BUY":
            primary_thesis = f"Bullish continuation / demand bounce in {regime.primary_regime.value} regime."
            alternative_thesis = "Bearish rejection / liquidity sweep failure breakdown."
            
            confluence_ratio = bull_score / total_score
            dynamic_base = 0.50 + (confluence_ratio * 0.25) + persist_factor + mtf_bonus
            primary_p = round(max(0.20, min(0.88, dynamic_base - (adv_penalty * 0.008))), 2)
            alt_p = round(max(0.10, min(0.65, (1.0 - primary_p) * 0.70 + (adv_penalty * 0.004))), 2)
            no_trade_p = round(max(0.05, 1.0 - primary_p - alt_p), 2)

            invalidation_criteria.append(f"M15 close below recent swing low ({st.demand_zone[0]}).")
            invalidation_criteria.append("Bearish displacement candle breaking demand equilibrium.")
            
            confirmation_conditions.append("M5 bullish displacement with volume absorption.")
            confirmation_conditions.append(f"Hold above demand level {st.demand_zone[0]}.")
            expected_outcome = f"Targeting supply liquidity pool at {st.supply_zone[1]} with minimum 1:2.0 R:R."
            
            structural_invalidation_distance = abs(c_price - st.demand_zone[0]) if st.demand_zone[0] > 0 else 0.0

        elif proposed_action == "SELL":
            primary_thesis = f"Bearish continuation / supply mitigation in {regime.primary_regime.value} regime."
            alternative_thesis = "Bullish short squeeze / demand support breakout."

            confluence_ratio = bear_score / total_score
            dynamic_base = 0.50 + (confluence_ratio * 0.25) + persist_factor + mtf_bonus
            primary_p = round(max(0.20, min(0.88, dynamic_base - (adv_penalty * 0.008))), 2)
            alt_p = round(max(0.10, min(0.65, (1.0 - primary_p) * 0.70 + (adv_penalty * 0.004))), 2)
            no_trade_p = round(max(0.05, 1.0 - primary_p - alt_p), 2)

            invalidation_criteria.append(f"M15 close above recent swing high ({st.supply_zone[1]}).")
            invalidation_criteria.append("Bullish displacement candle breaking supply equilibrium.")

            confirmation_conditions.append("M5 bearish displacement with volume rejection.")
            confirmation_conditions.append(f"Hold below supply level {st.supply_zone[1]}.")
            expected_outcome = f"Targeting demand liquidity pool at {st.demand_zone[0]} with minimum 1:2.0 R:R."
            
            structural_invalidation_distance = abs(st.supply_zone[1] - c_price) if st.supply_zone[1] > 0 else 0.0

        else:
            primary_thesis = "Indeterminate market equilibrium. Capital preservation active."
            alternative_thesis = "Breakout emergence from range compression."
            
            factor = min(1.0, adv_penalty / 50.0)
            primary_p = round(0.5 * (1.0 - factor) + 0.33 * factor, 2)
            alt_p = round(0.5 * (1.0 - factor) + 0.33 * factor, 2)
            no_trade_p = round(max(0.05, 1.0 - primary_p - alt_p), 2)
            
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
            expected_outcome=expected_outcome,
            structural_invalidation_distance=structural_invalidation_distance
        )
