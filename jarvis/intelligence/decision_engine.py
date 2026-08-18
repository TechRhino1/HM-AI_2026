"""
JARVIS AI 3.0 — Autonomous Decision Engine & Trade Quality Gate.
Synthesizes multi-agent confluences, applies Devil's Advocate risk penalties, calculates expected value, and gates execution.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import numpy as np

from jarvis.data.schemas import (
    MarketContext,
    RegimeOutput,
    AnalystReport,
    DevilAdvocateReport,
    DecisionObject,
    TradeQualityGateResult,
    MarketRegime
)
from jarvis.intelligence.strategy_selector import StrategySelector
from jarvis.intelligence.hypothesis_engine import HypothesisEngine
from jarvis.intelligence.confidence import ConfidenceCalibrationEngine

class DecisionEngine:
    def __init__(
        self,
        strategy_selector: Optional[StrategySelector] = None,
        hypothesis_engine: Optional[HypothesisEngine] = None,
        calibrator: Optional[ConfidenceCalibrationEngine] = None,
        min_ev_hurdle: float = 1.20,
        max_devil_penalty: float = 35.0
    ):
        self.strategy_selector = strategy_selector or StrategySelector()
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.calibrator = calibrator or ConfidenceCalibrationEngine()
        self.min_ev_hurdle = min_ev_hurdle
        self.max_devil_penalty = max_devil_penalty

    def evaluate(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        analyst_reports: Dict[str, AnalystReport],
        devil_report: DevilAdvocateReport,
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5
    ) -> DecisionObject:
        st = context.structure
        vol = context.volatility
        mom = context.momentum
        c_price = context.current_price

        # 1. Determine Directional Bias from Analysts Confluence
        bull_votes = sum(1 for r in analyst_reports.values() if r.bias == "BULLISH")
        bear_votes = sum(1 for r in analyst_reports.values() if r.bias == "BEARISH")
        
        tentative_bias = "BUY" if bull_votes > bear_votes and bull_votes >= 2 else (
            "SELL" if bear_votes > bull_votes and bear_votes >= 2 else "HOLD"
        )

        # 2. Strategy Selection
        strategy_probs = self.strategy_selector.select_strategy_probabilities(regime)
        best_strategy = max(strategy_probs.items(), key=lambda x: x[1])[0]

        # 3. Calculate SL, TP, Risk-Reward
        digits = 2 if any(k in context.symbol.upper() for k in ["XAU", "GOLD", "BTC"]) else 5
        atr = vol.atr if vol.atr > 0 else (c_price * 0.005)

        if tentative_bias == "BUY":
            entry_price = round(context.ask, digits)
            # SL placed below demand zone or 1.5 ATR
            sl_price = round(min(entry_price - (atr * 1.5), st.demand_zone[0]) if st.demand_zone[0] > 0 else entry_price - (atr * 1.5), digits)
            risk_dist = abs(entry_price - sl_price)
            tp_price = round(entry_price + (risk_dist * 2.5), digits)
            rr_ratio = round(abs(tp_price - entry_price) / (risk_dist + 1e-9), 2)
        elif tentative_bias == "SELL":
            entry_price = round(context.bid, digits)
            # SL placed above supply zone or 1.5 ATR
            sl_price = round(max(entry_price + (atr * 1.5), st.supply_zone[1]) if st.supply_zone[1] > 0 else entry_price + (atr * 1.5), digits)
            risk_dist = abs(sl_price - entry_price)
            tp_price = round(entry_price - (risk_dist * 2.5), digits)
            rr_ratio = round(abs(entry_price - tp_price) / (risk_dist + 1e-9), 2)
        else:
            entry_price = c_price
            sl_price = c_price
            tp_price = c_price
            risk_dist = 0.0
            rr_ratio = 1.0

        # 4. Generate dialectical hypotheses and adversarial adjustment
        hypotheses = self.hypothesis_engine.construct_hypotheses(
            context, regime, analyst_reports, devil_report, tentative_bias
        )

        # 5. Calibrated Win Probability & Expected Value Calculation
        raw_prob = hypotheses.primary_probability if tentative_bias in ["BUY", "SELL"] else 0.33
        calibrated_win_p = self.calibrator.calibrate_probability(raw_prob)
        loss_p = 1.0 - calibrated_win_p

        # Expected Value = (P_win * Avg_Win) - (P_loss * Avg_Loss) - Spread_Cost - Slippage
        planned_risk_dollars = account_balance * (risk_per_trade_pct / 100.0)
        planned_win_dollars = planned_risk_dollars * rr_ratio
        spread_cost = vol.current_spread_pips * (1.0 if "XAU" in context.symbol else 10.0)
        expected_slippage = vol.atr * 0.05

        ev = (calibrated_win_p * planned_win_dollars) - (loss_p * planned_risk_dollars) - spread_cost - expected_slippage
        ev = round(float(ev), 2)

        # 6. Trade Quality Gate Validation (14-Point Checklist)
        gate_checks = {
            "Regime Viability": regime.primary_regime != MarketRegime.EVENT_RISK and regime.primary_regime != MarketRegime.HIGH_VOLATILITY,
            "Directional Bias": tentative_bias in ["BUY", "SELL"],
            "Risk/Reward >= 1.5": rr_ratio >= 1.5,
            "Positive Expected Value": ev > 0 and ev >= self.min_ev_hurdle,
            "Spread Protection": not vol.is_excessive_spread,
            "Devil Penalty Guard": devil_report.penalty_score <= self.max_devil_penalty,
            "Calibrated Probability >= 55%": calibrated_win_p >= 0.55,
            "No Active Macro Shock": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Valid Stop Loss Distance": risk_dist > 0
        }

        failing_reasons = [name for name, passed in gate_checks.items() if not passed]
        gate_passed = len(failing_reasons) == 0

        # Final decision action
        if gate_passed:
            decision_action = "EXECUTE"
        elif tentative_bias in ["BUY", "SELL"] and len(failing_reasons) <= 2 and "Regime Viability" in gate_checks:
            decision_action = "WAIT"
        else:
            decision_action = "NO_TRADE"

        # Evidence and Risk factors compilation
        bull_case = []
        bear_case = []
        for rep in analyst_reports.values():
            if rep.bias == "BULLISH":
                bull_case.extend(rep.evidence)
            elif rep.bias == "BEARISH":
                bear_case.extend(rep.evidence)

        probabilities = {
            "buy": round(calibrated_win_p if tentative_bias == "BUY" else loss_p * 0.4, 2),
            "sell": round(calibrated_win_p if tentative_bias == "SELL" else loss_p * 0.4, 2),
            "no_trade": round(hypotheses.no_trade_probability, 2)
        }

        return DecisionObject(
            symbol=context.symbol,
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            bias=tentative_bias,
            probabilities=probabilities,
            strategy=best_strategy,
            entry_price=entry_price,
            stop_loss=sl_price,
            take_profit=tp_price,
            risk_reward_ratio=rr_ratio,
            calculated_risk_percent=round(risk_per_trade_pct * devil_report.invalidation_risk_coefficient, 2),
            expected_value=ev,
            model_confidence=regime.confidence,
            adversarial_penalty=devil_report.penalty_score,
            invalidation_levels=hypotheses.invalidation_criteria,
            bull_case=bull_case[:4],
            bear_case=bear_case[:4],
            risk_factors=devil_report.threats_detected[:4],
            quality_gate=TradeQualityGateResult(passed=gate_passed, checks=gate_checks, failing_reasons=failing_reasons),
            decision=decision_action,
            execution_authorized=gate_passed
        )
