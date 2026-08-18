"""
JARVIS AI 3.0 — Devil's Advocate Adversarial Intelligence Agent.
Implements the Adversarial Risk Penalty Scoring System (replacing binary veto).
Actively searches for invalidation, liquidity traps, exhaustion, conflicting timeframes, and counter-trend threats.
"""
import time
from typing import Dict, List, Any
from jarvis.data.schemas import MarketContext, RegimeOutput, DevilAdvocateReport

class DevilAdvocateAnalyst:
    """
    Mandatory Adversarial Counter-Analyst.
    Calculates adversarial penalty scores and invalidation risk coefficients to stress-test trade hypotheses.
    """
    def __init__(self):
        pass

    def critique_opportunity(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        proposed_bias: str  # "BUY" or "SELL"
    ) -> DevilAdvocateReport:
        t0 = time.perf_counter()
        threats = []
        invalidation_triggers = []
        traps = []

        penalty_score = 0.0
        st = context.structure
        mom = context.momentum
        vol = context.volatility
        liq = context.liquidity
        mtf = context.mtf_alignment

        counter_bias = "BEARISH" if proposed_bias == "BUY" else "BULLISH"

        if proposed_bias == "BUY":
            # 1. Counter-trend momentum check
            if mom.trend_score < -20:
                penalty_score += 15.0
                threats.append(f"Counter-trend buying against negative momentum score ({mom.trend_score}).")
            if mom.rsi > 70.0:
                penalty_score += 12.0
                threats.append(f"Overextended buy entry with RSI in overbought territory ({mom.rsi:.1f}).")
            if mom.divergence == "BEARISH_DIVERGENCE":
                penalty_score += 14.0
                threats.append("Bearish RSI divergence warning against buying impulse.")

            # 2. Structural resistance & Premium zone
            if st.discount_premium_zone == "PREMIUM":
                penalty_score += 10.0
                threats.append("Buying in PREMIUM zone above equilibrium (unfavorable entry price).")
            if st.lower_highs and st.lower_lows:
                penalty_score += 18.0
                threats.append("Primary structure exhibits Lower Highs and Lower Lows (downtrend).")

            # 3. Timeframe conflict
            if mtf.get("H4") == "BEARISH" or mtf.get("D1") == "BEARISH":
                penalty_score += 12.0
                threats.append(f"Higher timeframe structural conflict: Macro timeframe is {mtf.get('H4') or mtf.get('D1')}.")

            # 4. Liquidity traps
            if liq.equal_lows:
                traps.append(f"Unswept Equal Lows at {st.demand_zone[0]} — smart money may hunt sell-side stops first.")
                penalty_score += 8.0

            # 5. Invalidation triggers
            invalidation_triggers.append(f"H1 candle close below demand zone {st.demand_zone[0]}.")
            invalidation_triggers.append("Bearish displacement breaking recent swing low.")

        elif proposed_bias == "SELL":
            # 1. Counter-trend momentum check
            if mom.trend_score > 20:
                penalty_score += 15.0
                threats.append(f"Counter-trend selling against positive momentum score ({mom.trend_score}).")
            if mom.rsi < 30.0:
                penalty_score += 12.0
                threats.append(f"Overextended sell entry with RSI in oversold territory ({mom.rsi:.1f}).")
            if mom.divergence == "BULLISH_DIVERGENCE":
                penalty_score += 14.0
                threats.append("Bullish RSI divergence warning against selling impulse.")

            # 2. Structural support & Discount zone
            if st.discount_premium_zone == "DISCOUNT":
                penalty_score += 10.0
                threats.append("Selling in DISCOUNT zone below equilibrium (unfavorable entry price).")
            if st.higher_highs and st.higher_lows:
                penalty_score += 18.0
                threats.append("Primary structure exhibits Higher Highs and Higher Lows (uptrend).")

            # 3. Timeframe conflict
            if mtf.get("H4") == "BULLISH" or mtf.get("D1") == "BULLISH":
                penalty_score += 12.0
                threats.append(f"Higher timeframe structural conflict: Macro timeframe is {mtf.get('H4') or mtf.get('D1')}.")

            # 4. Liquidity traps
            if liq.equal_highs:
                traps.append(f"Unswept Equal Highs at {st.supply_zone[1]} — smart money may hunt buy-side stops first.")
                penalty_score += 8.0

            # 5. Invalidation triggers
            invalidation_triggers.append(f"H1 candle close above supply zone {st.supply_zone[1]}.")
            invalidation_triggers.append("Bullish displacement breaking recent swing high.")

        # Volatility shock penalty
        if vol.state == "EXTREME":
            penalty_score += 20.0
            threats.append("Extreme volatility shock in progress — stop loss vulnerability elevated.")

        # Cap penalty score between 0.0 and 50.0
        final_penalty = round(min(50.0, max(0.0, penalty_score)), 1)
        
        # Invalidation risk coefficient: 1.0 (no penalty) down to 0.2 (severe penalty)
        invalidation_coeff = round(max(0.20, 1.0 - (final_penalty / 60.0)), 2)

        elapsed = (time.perf_counter() - t0) * 1000.0

        return DevilAdvocateReport(
            symbol=context.symbol,
            counter_bias=counter_bias,
            penalty_score=final_penalty,
            invalidation_risk_coefficient=invalidation_coeff,
            threats_detected=threats,
            invalidation_triggers=invalidation_triggers,
            liquidity_traps=traps,
            execution_time_ms=round(elapsed, 2)
        )
