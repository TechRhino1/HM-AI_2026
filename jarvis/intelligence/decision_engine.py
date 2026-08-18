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
        min_ev_hurdle: float = 0.50,
        max_devil_penalty: float = 38.0
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

        # 1. Determine Directional Bias from Analysts Confluence + Macro Shock
        bull_votes = sum(1 for r in analyst_reports.values() if r.bias == "BULLISH")
        bear_votes = sum(1 for r in analyst_reports.values() if r.bias == "BEARISH")
        
        # Immediate structure breakdown override (CHoCH / BOS)
        if st.choch and st.choch_type == "BEARISH":
            tentative_bias = "SELL"
        elif st.choch and st.choch_type == "BULLISH":
            tentative_bias = "BUY"
        elif bear_votes > bull_votes and bear_votes >= 2:
            tentative_bias = "SELL"
        elif bull_votes > bear_votes and bull_votes >= 2:
            tentative_bias = "BUY"
        else:
            tentative_bias = "HOLD"

        # 2. Strategy Selection
        strategy_probs = self.strategy_selector.select_strategy_probabilities(regime)
        best_strategy = max(strategy_probs.items(), key=lambda x: x[1])[0]

        # 3. Calculate SL, TP, Risk-Reward
        digits = 2 if any(k in context.symbol.upper() for k in ["XAU", "GOLD", "BTC"]) else 5
        atr = vol.atr if vol.atr > 0 else (c_price * 0.005)

        if tentative_bias == "BUY":
            entry_price = round(context.ask, digits)
            # SL placed at 1.8 ATR or local demand (capped at 2.5 ATR max)
            sl_dist = min(atr * 2.5, max(atr * 1.5, entry_price - st.demand_zone[0])) if (st.demand_zone[0] > 0 and entry_price > st.demand_zone[0]) else (atr * 1.8)
            sl_price = round(entry_price - sl_dist, digits)
            risk_dist = abs(entry_price - sl_price)
            tp_price = round(entry_price + (risk_dist * 2.5), digits)
            rr_ratio = round(abs(tp_price - entry_price) / (risk_dist + 1e-9), 2)
        elif tentative_bias == "SELL":
            entry_price = round(context.bid, digits)
            # SL placed at 1.8 ATR or local supply (capped at 2.5 ATR max)
            sl_dist = min(atr * 2.5, max(atr * 1.5, st.supply_zone[1] - entry_price)) if (st.supply_zone[1] > 0 and st.supply_zone[1] > entry_price) else (atr * 1.8)
            sl_price = round(entry_price + sl_dist, digits)
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

        # Micro-lot safety: on accounts < $250, calibrate risk to base 0.01 lot
        planned_risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))
        planned_win_dollars = planned_risk_dollars * rr_ratio
        
        contract_size = 100.0 if any(k in context.symbol.upper() for k in ["XAU", "GOLD"]) else 100000.0
        pip_size = 0.1 if any(k in context.symbol.upper() for k in ["XAU", "GOLD"]) else (0.01 if "JPY" in context.symbol.upper() else 0.0001)
        est_lots = max(0.01, planned_risk_dollars / (max(risk_dist, 1e-4) * contract_size))
        pip_val_per_lot = contract_size * pip_size
        spread_cost = vol.current_spread_pips * pip_val_per_lot * est_lots
        expected_slippage = (vol.atr * 0.02) * est_lots

        ev = (calibrated_win_p * planned_win_dollars) - (loss_p * planned_risk_dollars) - spread_cost - expected_slippage
        ev = round(float(ev), 2)

        # 6. Trade Quality Gate Validation (Momentum Breakout & Dynamic EV Hurdle)
        # In strong momentum breakouts (Trend Score >= 60 or <= -60), allow directional continuation
        premium_discount_valid = True
        if tentative_bias == "BUY" and st.discount_premium_zone == "PREMIUM" and mom.trend_score < 60:
            premium_discount_valid = False
        elif tentative_bias == "SELL" and st.discount_premium_zone == "DISCOUNT" and mom.trend_score > -60:
            premium_discount_valid = False

        # Scale minimum EV hurdle dynamically to account balance size
        effective_min_ev = max(0.10, min(self.min_ev_hurdle, planned_risk_dollars * 0.5))

        gate_checks = {
            "Regime Viability": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Directional Bias": tentative_bias in ["BUY", "SELL"],
            "Risk/Reward >= 1.5": rr_ratio >= 1.5,
            "Positive Expected Value": ev > 0 and ev >= effective_min_ev,
            "Spread Protection": not vol.is_excessive_spread,
            "Devil Penalty Guard": devil_report.penalty_score <= self.max_devil_penalty,
            "Calibrated Probability >= 55%": calibrated_win_p >= 0.55,
            "No Active Macro Shock": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Valid Stop Loss Distance": risk_dist > 0,
            "Premium/Discount Zone Valid": premium_discount_valid
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
