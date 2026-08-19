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
from jarvis.learning.online_ml_predictor import OnlineMLPredictor
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.risk.account_tier import is_micro_account, get_effective_min_ev

class DecisionEngine:
    def __init__(
        self,
        strategy_selector: Optional[StrategySelector] = None,
        hypothesis_engine: Optional[HypothesisEngine] = None,
        calibrator: Optional[ConfidenceCalibrationEngine] = None,
        ml_predictor: Optional[OnlineMLPredictor] = None,
        min_ev_hurdle: float = 0.50,
        max_devil_penalty: float = 38.0
    ):
        self.strategy_selector = strategy_selector or StrategySelector()
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.calibrator = calibrator or ConfidenceCalibrationEngine()
        self.ml_predictor = ml_predictor or OnlineMLPredictor()
        self.min_ev_hurdle = min_ev_hurdle
        self.max_devil_penalty = max_devil_penalty

    def _compute_bias_and_levels(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        analyst_reports: Dict[str, AnalystReport]
    ):
        st = context.structure
        vol = context.volatility
        c_price = context.current_price
        
        bull_votes = sum(1 for r in analyst_reports.values() if r.bias == "BULLISH")
        bear_votes = sum(1 for r in analyst_reports.values() if r.bias == "BEARISH")
        
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

        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        atr = vol.atr if vol.atr > 0 else (c_price * 0.005)

        if tentative_bias == "BUY":
            entry_price = round(context.ask, digits)
            # §5 & §6: Structural SL with ±0.2 ATR buffer and [0.8*ATR, 4.0*ATR] sanity bounds
            if st.demand_zone[0] > 0 and entry_price > st.demand_zone[0]:
                struct_sl_dist = entry_price - (st.demand_zone[0] - (atr * 0.2))
                if (0.8 * atr) <= struct_sl_dist <= (4.0 * atr):
                    sl_dist = struct_sl_dist
                else:
                    sl_dist = atr * 1.8
            else:
                sl_dist = atr * 1.8

            sl_price = round(entry_price - sl_dist, digits)
            risk_dist = abs(entry_price - sl_price)

            # §7: Dynamic TP targeting nearest opposing structural supply zone or key resistance
            flat_tp_dist = risk_dist * 2.5
            struct_target_dist = 0.0
            if st.supply_zone[0] > entry_price:
                struct_target_dist = st.supply_zone[0] - entry_price
            elif hasattr(st, "key_levels") and st.key_levels:
                res_levels = [kl["price"] for kl in st.key_levels if kl.get("price", 0) > entry_price]
                if res_levels:
                    struct_target_dist = min(res_levels) - entry_price

            if struct_target_dist >= (risk_dist * 1.5) and struct_target_dist < flat_tp_dist:
                tp_dist = struct_target_dist
            else:
                tp_dist = flat_tp_dist

            tp_price = round(entry_price + tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)

        elif tentative_bias == "SELL":
            entry_price = round(context.bid, digits)
            # §5 & §6: Structural SL with ±0.2 ATR buffer and [0.8*ATR, 4.0*ATR] sanity bounds
            if st.supply_zone[1] > 0 and st.supply_zone[1] > entry_price:
                struct_sl_dist = (st.supply_zone[1] + (atr * 0.2)) - entry_price
                if (0.8 * atr) <= struct_sl_dist <= (4.0 * atr):
                    sl_dist = struct_sl_dist
                else:
                    sl_dist = atr * 1.8
            else:
                sl_dist = atr * 1.8

            sl_price = round(entry_price + sl_dist, digits)
            risk_dist = abs(sl_price - entry_price)

            # §7: Dynamic TP targeting nearest opposing structural demand zone or key support
            flat_tp_dist = risk_dist * 2.5
            struct_target_dist = 0.0
            if st.demand_zone[1] > 0 and st.demand_zone[1] < entry_price:
                struct_target_dist = entry_price - st.demand_zone[1]
            elif hasattr(st, "key_levels") and st.key_levels:
                sup_levels = [kl["price"] for kl in st.key_levels if 0 < kl.get("price", 0) < entry_price]
                if sup_levels:
                    struct_target_dist = entry_price - max(sup_levels)

            if struct_target_dist >= (risk_dist * 1.5) and struct_target_dist < flat_tp_dist:
                tp_dist = struct_target_dist
            else:
                tp_dist = flat_tp_dist

            tp_price = round(entry_price - tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)
        else:
            entry_price = c_price
            sl_price = c_price
            tp_price = c_price
            risk_dist = 0.0
            rr_ratio = 1.0

        return tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio

    def _compute_blended_probability(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        analyst_reports: Dict[str, AnalystReport],
        devil_report: DevilAdvocateReport,
        tentative_bias: str,
        rr_ratio: float,
        risk_dist: float = 0.0,
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5
    ):
        hypotheses = self.hypothesis_engine.construct_hypotheses(
            context, regime, analyst_reports, devil_report, tentative_bias
        )
        raw_prob = hypotheses.primary_probability if tentative_bias in ["BUY", "SELL"] else 0.33
        calibrated_win_p = self.calibrator.calibrate_probability(raw_prob)

        ml_features = self.ml_predictor.extract_feature_vector(
            context=context,
            regime=regime,
            tentative_bias=tentative_bias,
            devil_penalty=devil_report.penalty_score,
            target_rr=rr_ratio
        )
        ml_win_p = self.ml_predictor.predict_win_probability(ml_features)

        final_win_p = round((0.45 * calibrated_win_p) + (0.55 * ml_win_p), 2)
        loss_p = round(1.0 - final_win_p, 2)

        planned_risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))
        planned_win_dollars = planned_risk_dollars * rr_ratio
        
        spec = resolve_symbol(context.symbol)
        contract_size = spec.contract_size
        pip_size = spec.pip_size
        
        if tentative_bias not in ["BUY", "SELL"]:
            return final_win_p, loss_p, 0.0, hypotheses, calibrated_win_p

        est_lots = max(0.01, planned_risk_dollars / (max(risk_dist, 1e-4) * contract_size))
        pip_val_per_lot = contract_size * pip_size
        spread_cost = context.volatility.current_spread_pips * pip_val_per_lot * est_lots
        expected_slippage = (context.volatility.atr * 0.02) * est_lots

        ev = (final_win_p * planned_win_dollars) - (loss_p * planned_risk_dollars) - spread_cost - expected_slippage
        ev = round(float(ev), 2)
        return final_win_p, loss_p, ev, hypotheses, calibrated_win_p

    def _apply_quality_gate(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        devil_report: DevilAdvocateReport,
        ai_score: float,
        rr_ratio: float,
        ev: float,
        final_win_p: float,
        spread: float,
        premium_discount_valid: bool,
        account_balance: float,
        current_drawdown_pct: float = 0.0,
        tentative_bias: str = "HOLD",
        calibrated_win_p: float = 0.0,
        risk_dist: float = 0.0,
        planned_risk_dollars: float = 0.0
    ) -> TradeQualityGateResult:
        is_micro_mode = is_micro_account(account_balance)
        effective_min_ev = get_effective_min_ev(account_balance, planned_risk_dollars)

        if is_micro_mode:
            if account_balance <= 40.0:
                min_score = 80.0
                min_rr = 2.0
                max_spread = 2.5
            elif account_balance <= 70.0:
                min_score = 80.0
                min_rr = 2.0
                max_spread = 3.0
            else:
                min_score = 78.0
                min_rr = 1.8
                max_spread = 3.5

            if current_drawdown_pct > 5.0:
                min_score = max(min_score, 85.0)

            if regime.primary_regime in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR] and regime.confidence > 0.7:
                effective_min_ev *= 0.7

            gate_checks = {
                "Regime Viability": regime.primary_regime != MarketRegime.EVENT_RISK,
                "Directional Bias": tentative_bias in ["BUY", "SELL"],
                "Risk/Reward >= 2.0": rr_ratio >= min_rr,
                "Positive Expected Value": ev > 0 and ev >= effective_min_ev,
                "Spread Protection": spread <= max_spread,
                "AI Score Gate >= 80": ai_score >= min_score,
                "Devil Penalty Guard": devil_report.penalty_score <= self.max_devil_penalty,
                "Calibrated Probability >= 55%": calibrated_win_p >= 0.55,
                "Valid Stop Loss Distance": risk_dist >= (context.volatility.atr * 0.75),
                "Premium/Discount Zone Valid": premium_discount_valid
            }
        else:
            if regime.primary_regime in [MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR] and regime.confidence > 0.7:
                effective_min_ev *= 0.7

            gate_checks = {
                "Regime Viability": regime.primary_regime != MarketRegime.EVENT_RISK,
                "Directional Bias": tentative_bias in ["BUY", "SELL"],
                "Risk/Reward >= 1.5": rr_ratio >= 1.5,
                "Positive Expected Value": ev > 0 and ev >= effective_min_ev,
                "Spread Protection": not context.volatility.is_excessive_spread,
                "Devil Penalty Guard": devil_report.penalty_score <= self.max_devil_penalty,
                "Calibrated Probability >= 55%": calibrated_win_p >= 0.55,
                "No Active Macro Shock": regime.primary_regime != MarketRegime.EVENT_RISK,
                "Valid Stop Loss Distance": risk_dist > 0,
                "Premium/Discount Zone Valid": premium_discount_valid
            }

        failing_reasons = [name for name, passed in gate_checks.items() if not passed]
        gate_passed = len(failing_reasons) == 0

        return TradeQualityGateResult(passed=gate_passed, checks=gate_checks, failing_reasons=failing_reasons)

    def evaluate(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        analyst_reports: Dict[str, AnalystReport],
        devil_report: DevilAdvocateReport,
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5,
        current_drawdown_pct: float = 0.0
    ) -> DecisionObject:
        tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio = self._compute_bias_and_levels(
            context, regime, analyst_reports
        )

        strategy_probs = self.strategy_selector.select_strategy_probabilities(
            regime, context=context, account_equity=account_balance
        )
        best_strategy = max(strategy_probs.items(), key=lambda x: x[1])[0]

        final_win_p, loss_p, ev, hypotheses, calibrated_win_p = self._compute_blended_probability(
            context, regime, analyst_reports, devil_report, tentative_bias, rr_ratio, risk_dist, account_balance, risk_per_trade_pct
        )

        ai_score = sum(r.score for r in analyst_reports.values()) / max(1, len(analyst_reports)) if analyst_reports else 0.0
        
        st = context.structure
        premium_discount_valid = True
        if tentative_bias == "BUY" and st.discount_premium_zone == "PREMIUM" and context.momentum.trend_score < 60:
            premium_discount_valid = False
        elif tentative_bias == "SELL" and st.discount_premium_zone == "DISCOUNT" and context.momentum.trend_score > -60:
            premium_discount_valid = False

        planned_risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))

        quality_gate = self._apply_quality_gate(
            context=context, regime=regime, devil_report=devil_report, ai_score=ai_score,
            rr_ratio=rr_ratio, ev=ev, final_win_p=final_win_p, spread=context.volatility.current_spread_pips,
            premium_discount_valid=premium_discount_valid, account_balance=account_balance,
            current_drawdown_pct=current_drawdown_pct, tentative_bias=tentative_bias,
            calibrated_win_p=calibrated_win_p, risk_dist=risk_dist, planned_risk_dollars=planned_risk_dollars
        )
        
        gate_passed = quality_gate.passed
        failing_reasons = quality_gate.failing_reasons

        if gate_passed:
            decision_action = "EXECUTE"
        elif tentative_bias in ["BUY", "SELL"] and len(failing_reasons) <= 2 and quality_gate.checks.get("Regime Viability", False):
            decision_action = "WAIT"
        else:
            decision_action = "NO_TRADE"

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

        tp_dist = abs(tp_price - entry_price)

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
            sl_distance=risk_dist,
            tp_distance=tp_dist,
            risk_reward_ratio=rr_ratio,
            calculated_risk_percent=round(risk_per_trade_pct * devil_report.invalidation_risk_coefficient, 2),
            expected_value=ev,
            model_confidence=calibrated_win_p,
            adversarial_penalty=devil_report.penalty_score,
            invalidation_levels=hypotheses.invalidation_criteria,
            bull_case=bull_case[:4],
            bear_case=bear_case[:4],
            risk_factors=devil_report.threats_detected[:4],
            quality_gate=quality_gate,
            decision=decision_action,
            execution_authorized=gate_passed
        )
