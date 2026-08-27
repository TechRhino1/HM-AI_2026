"""
JARVIS AI 3.0 — Autonomous Decision Engine & Trade Quality Gate.
Synthesizes multi-agent confluences, applies Devil's Advocate risk penalties, calculates expected value, and gates execution.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging
import numpy as np

logger = logging.getLogger("JARVIS_DecisionEngine")

from jarvis.intelligence.order_flow import InstitutionalVolumeOrderFlowEngine
from jarvis.intelligence.self_learning import SelfLearningEngine
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
from jarvis.market.news import GLOBAL_NEWS_ENGINE
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.risk.account_tier import is_micro_account, get_effective_min_ev

from jarvis.learning.fractional_diff import FractionalDifferentiationTransformer
from jarvis.learning.ensemble_bandit import EnsembleStrategyBandit
from jarvis.intelligence.meta_labeler import MetaLabeler
from jarvis.intelligence.gate_policy import AdaptiveGatePolicy, HARD_GATES


def _is_forex(symbol: str) -> bool:
    try:
        spec = resolve_symbol(symbol)
        return getattr(spec, "asset_class", "").upper() == "FOREX"
    except Exception:
        return False

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
        self.ensemble_bandit = EnsembleStrategyBandit()
        self.frac_diff = FractionalDifferentiationTransformer()
        self.min_ev_hurdle = min_ev_hurdle
        self.max_devil_penalty = max_devil_penalty
        self.order_flow = InstitutionalVolumeOrderFlowEngine()
        self.self_learning = SelfLearningEngine()
        self.meta_labeler = MetaLabeler()
        self.gate_policy = AdaptiveGatePolicy()


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
        elif bear_votes > bull_votes:
            tentative_bias = "SELL"
        elif bull_votes > bear_votes:
            tentative_bias = "BUY"
        elif st.bias == "BEARISH":
            tentative_bias = "SELL"
        elif st.bias == "BULLISH":
            tentative_bias = "BUY"
        elif getattr(context.momentum, "trend_score", 0.0) < 0:
            tentative_bias = "SELL"
        else:
            tentative_bias = "BUY"

        spec = resolve_symbol(context.symbol)
        digits = spec.digits
        atr = vol.atr if vol.atr > 0 else (c_price * 0.005)

        # §P2, §P5 & §B-1: Regime & Conviction Adaptive SL, TP & Partial Profit Scaling
        is_strong_trend = (
            regime.primary_regime in (MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR)
            and getattr(regime, "confidence", 0.0) > 0.75
            and getattr(context.momentum, "adx", 0.0) > 25.0
        )
        is_ranging = regime.primary_regime in (MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY)
        is_breakout = regime.primary_regime in (MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY)

        if is_strong_trend:
            sl_default_mult = 1.2       # Shallow pullbacks in strong trends: tight structure-anchored SL
            sl_min_bound_mult = 0.5     # Tighter lower bound
            sl_max_bound_mult = 2.2     # Tighter upper bound
            sl_buffer_mult = 0.12       # Tighter structural buffer
            tp_multiplier = 3.8         # Strong confirmed trend — let winners run for massive R:R
            first_target_volume_pct = 0.25  # 25% scale-out, 75% rides to target
        elif is_ranging:
            sl_default_mult = 1.4       # Safe structural buffer outside chop
            sl_min_bound_mult = 0.7
            sl_max_bound_mult = 3.0
            sl_buffer_mult = 0.20
            tp_multiplier = 2.2         # Target internal range liquidity
            first_target_volume_pct = 0.50  # 50% locked in quickly inside range
        elif is_breakout:
            sl_default_mult = 1.4
            sl_min_bound_mult = 0.70
            sl_max_bound_mult = 3.0
            sl_buffer_mult = 0.20
            tp_multiplier = 3.2         # Breakout expansion target
            first_target_volume_pct = 0.35
        else:
            sl_default_mult = 1.8
            sl_min_bound_mult = 0.8
            sl_max_bound_mult = 4.0
            sl_buffer_mult = 0.20
            tp_multiplier = 2.5         # Default baseline institutional R:R
            first_target_volume_pct = 0.50

        spread_dist = max(0.0, context.ask - context.bid) if (context.ask > 0 and context.bid > 0) else (context.volatility.current_spread_pips * spec.pip_size)

        if tentative_bias == "BUY":
            entry_price = round(context.ask, digits)
            # Structural SL with regime-adaptive buffer and bounds
            if st.demand_zone[0] > 0 and entry_price > st.demand_zone[0]:
                struct_sl_dist = entry_price - (st.demand_zone[0] - (atr * sl_buffer_mult))
                if (sl_min_bound_mult * atr) <= struct_sl_dist <= (sl_max_bound_mult * atr):
                    sl_dist = struct_sl_dist
                else:
                    sl_dist = atr * sl_default_mult
            else:
                sl_dist = atr * sl_default_mult

            sl_price = round(entry_price - sl_dist, digits)
            risk_dist = abs(entry_price - sl_price)

            flat_tp_dist = risk_dist * tp_multiplier
            struct_target_dist = 0.0
            if st.supply_zone[0] > entry_price:
                struct_target_dist = st.supply_zone[0] - entry_price
            elif hasattr(st, "key_levels") and st.key_levels:
                res_levels = [kl["price"] for kl in st.key_levels if kl.get("price", 0) > entry_price]
                if res_levels:
                    struct_target_dist = min(res_levels) - entry_price

            if is_strong_trend:
                # In strong trends, honor further structural targets up to 5.0R
                if struct_target_dist >= (risk_dist * 1.5):
                    tp_dist = min(struct_target_dist, risk_dist * 5.0)
                else:
                    tp_dist = flat_tp_dist
            else:
                if struct_target_dist >= (risk_dist * 1.5) and struct_target_dist <= flat_tp_dist:
                    tp_dist = struct_target_dist
                else:
                    tp_dist = flat_tp_dist

            tp_price = round(entry_price + tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)

            # §B-2 / §B-3: First target for partial scaling (near structure or 1.0R)
            if 0 < struct_target_dist < tp_dist and struct_target_dist >= (risk_dist * 0.8):
                first_target_price = round(entry_price + struct_target_dist, digits)
            else:
                first_target_price = round(entry_price + (risk_dist * 1.0), digits)

        elif tentative_bias == "SELL":
            entry_price = round(context.bid, digits)
            # Structural SL with regime-adaptive buffer, spread offset and bounds
            if st.supply_zone[1] > 0 and st.supply_zone[1] > entry_price:
                struct_sl_dist = (st.supply_zone[1] + (atr * sl_buffer_mult) + spread_dist) - entry_price
                if (sl_min_bound_mult * atr) <= struct_sl_dist <= (sl_max_bound_mult * atr + spread_dist):
                    sl_dist = struct_sl_dist
                else:
                    sl_dist = atr * sl_default_mult + spread_dist
            else:
                sl_dist = atr * sl_default_mult + spread_dist

            sl_price = round(entry_price + sl_dist, digits)
            risk_dist = abs(sl_price - entry_price)

            flat_tp_dist = risk_dist * tp_multiplier
            struct_target_dist = 0.0
            if st.demand_zone[1] > 0 and st.demand_zone[1] < entry_price:
                struct_target_dist = entry_price - st.demand_zone[1]
            elif hasattr(st, "key_levels") and st.key_levels:
                sup_levels = [kl["price"] for kl in st.key_levels if 0 < kl.get("price", 0) < entry_price]
                if sup_levels:
                    struct_target_dist = entry_price - max(sup_levels)

            if is_strong_trend:
                # In strong trends, honor further structural targets up to 5.0R
                if struct_target_dist >= (risk_dist * 1.5):
                    tp_dist = min(struct_target_dist, risk_dist * 5.0)
                else:
                    tp_dist = flat_tp_dist
            else:
                if struct_target_dist >= (risk_dist * 1.5) and struct_target_dist <= flat_tp_dist:
                    tp_dist = struct_target_dist
                else:
                    tp_dist = flat_tp_dist

            tp_price = round(entry_price - tp_dist, digits)
            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)

            # §B-2 / §B-3: First target for partial scaling (near structure or 1.0R)
            if 0 < struct_target_dist < tp_dist and struct_target_dist >= (risk_dist * 0.8):
                first_target_price = round(entry_price - struct_target_dist, digits)
            else:
                first_target_price = round(entry_price - (risk_dist * 1.0), digits)
        else:
            # When bias is HOLD / MONITOR, compute a valid structural reference bracket
            # based on prevailing structure/momentum rather than setting SL=TP=entry.
            is_bear_tilt = (st.bias == "BEARISH") or (getattr(context.momentum, "trend_score", 0.0) < 0)
            if is_bear_tilt:
                entry_price = round(context.bid, digits)
                sl_dist = atr * sl_default_mult
                if st.supply_zone[1] > entry_price:
                    candidate_dist = (st.supply_zone[1] + (atr * sl_buffer_mult)) - entry_price
                    if (sl_min_bound_mult * atr) <= candidate_dist <= (sl_max_bound_mult * atr):
                        sl_dist = candidate_dist
                sl_price = round(entry_price + sl_dist, digits)
                risk_dist = abs(sl_price - entry_price)
                tp_dist = risk_dist * tp_multiplier
                tp_price = round(entry_price - tp_dist, digits)
            else:
                entry_price = round(context.ask, digits)
                sl_dist = atr * sl_default_mult
                if st.demand_zone[0] > 0 and entry_price > st.demand_zone[0]:
                    candidate_dist = entry_price - (st.demand_zone[0] - (atr * sl_buffer_mult))
                    if (sl_min_bound_mult * atr) <= candidate_dist <= (sl_max_bound_mult * atr):
                        sl_dist = candidate_dist
                sl_price = round(entry_price - sl_dist, digits)
                risk_dist = abs(entry_price - sl_price)
                tp_dist = risk_dist * tp_multiplier
                tp_price = round(entry_price + tp_dist, digits)

            rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)
            first_target_price = None

        return tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio, first_target_price, first_target_volume_pct

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

        # Order flow volume delta continuous calibration (E1)
        of_data = getattr(context, "order_flow", {})
        delta_score = float(of_data.get("delta_score", 0.0)) if isinstance(of_data, dict) else 0.0
        if tentative_bias == "BUY":
            if delta_score > 20.0:
                calibrated_win_p = min(0.95, calibrated_win_p + (delta_score / 100.0) * 0.06)
            elif delta_score < -20.0:
                calibrated_win_p = max(0.05, calibrated_win_p - (abs(delta_score) / 100.0) * 0.08)
        elif tentative_bias == "SELL":
            if delta_score < -20.0:
                calibrated_win_p = min(0.95, calibrated_win_p + (abs(delta_score) / 100.0) * 0.06)
            elif delta_score > 20.0:
                calibrated_win_p = max(0.05, calibrated_win_p - (delta_score / 100.0) * 0.08)

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
        pip_val_per_lot = spec.pip_value_per_lot
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

        from jarvis.data.symbol_registry import resolve as resolve_symbol
        spec = resolve_symbol(context.symbol)
        atr_pips = context.volatility.atr / spec.pip_size if spec.pip_size > 0 else 0

        is_prime_session = bool(getattr(context.session, "is_prime_session", False)) if hasattr(context, "session") else False

        # Dynamic Scalp Confluence & Quality Factor
        is_scalp_favorable = (
            rr_ratio >= 1.8
            and spread <= (spec.max_spread_pips * 0.7)
            and not context.volatility.is_excessive_spread
            and (abs(context.momentum.trend_score) >= 10 or context.structure.bos or context.liquidity.sweep_detected)
        )

        if is_micro_mode:
            if is_scalp_favorable and (is_prime_session or rr_ratio >= 2.0):
                min_score = 72.0
                min_rr = 1.8
                required_win_p = 0.50
            elif account_balance <= 40.0:
                min_score = 78.0
                min_rr = 1.8
                required_win_p = 0.52
            else:
                min_score = 75.0
                min_rr = 1.8
                required_win_p = 0.52
            
            base_spread = 3.0
            dynamic_max_spread = max(base_spread, atr_pips * 0.08)
            dynamic_max_spread = min(dynamic_max_spread, context.volatility.max_allowed_spread_pips * 0.75)
            max_spread = round(dynamic_max_spread, 1)

            if current_drawdown_pct > 5.0:
                min_score = max(min_score, 82.0)
                required_win_p = max(required_win_p, 0.58)
        else:
            min_score = 72.0 if is_scalp_favorable else 75.0
            min_rr = 1.5
            required_win_p = 0.50 if is_scalp_favorable else 0.55
            max_spread = spec.max_spread_pips

        if _is_forex(context.symbol):
            required_win_p = 0.48

        # Check Macro MTF Confluence (H4 and D1 alignment)
        mtf_align = getattr(context, "mtf_alignment", {})
        h4_bias = mtf_align.get("H4", "NEUTRAL") if isinstance(mtf_align, dict) else "NEUTRAL"
        d1_bias = mtf_align.get("D1", "NEUTRAL") if isinstance(mtf_align, dict) else "NEUTRAL"
        mtf_counter_trend = False
        if tentative_bias == "BUY" and h4_bias == "BEARISH" and d1_bias == "BEARISH":
            mtf_counter_trend = True
        elif tentative_bias == "SELL" and h4_bias == "BULLISH" and d1_bias == "BULLISH":
            mtf_counter_trend = True

        if mtf_counter_trend:
            min_score = max(min_score, 82.0)
            required_win_p = max(required_win_p, 0.62)

        from jarvis.market.sessions import SessionEngine
        mkt_status = SessionEngine.get_market_trading_status(context.symbol, dt=getattr(context, "timestamp", None))
        is_mkt_open = mkt_status.get("is_open", True)

        # 16-Point Comprehensive Institutional Quality Gate Matrix
        gate_checks = {
            "Market Session Open": is_mkt_open,
            "Drawdown Safety Guard": current_drawdown_pct <= 10.0,
            "Regime Viability": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Directional Bias": tentative_bias in ["BUY", "SELL"],
            "Risk/Reward >= 1.5": rr_ratio >= min_rr,
            "Positive Expected Value": ev > 0 and ev >= effective_min_ev,
            "Spread Protection": spread <= max_spread and not context.volatility.is_excessive_spread,
            "AI Multi-Score Gate": ai_score >= min_score,
            "Devil Adversarial Guard": devil_report.penalty_score <= self.max_devil_penalty,
            "Calibrated Win Prob >= 50%": calibrated_win_p >= required_win_p,
            "Valid Stop Loss Distance": risk_dist >= (context.volatility.atr * (0.6 if is_micro_mode else 0.5)),
            "Premium/Discount Alignment": premium_discount_valid,
            "No Active Macro Shock": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Order Flow Momentum": abs(context.momentum.trend_score) >= 10 or context.structure.bos or context.liquidity.sweep_detected,
            "Macro MTF Alignment": not mtf_counter_trend or (ai_score >= 82.0 and calibrated_win_p >= 0.62),
            "Margin Capacity Limit": account_balance >= 10.0 and planned_risk_dollars > 0
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
        current_drawdown_pct: float = 0.0,
        mtf_data=None,
        recent_candles: Optional[List[Dict[str, Any]]] = None
    ) -> DecisionObject:
        tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio, first_target_price, first_target_volume_pct = self._compute_bias_and_levels(
            context, regime, analyst_reports
        )

        # §B-5: Devil's Advocate Threat Feedback Adjustment
        threat_lvl = getattr(devil_report, "threat_price_level", None) if devil_report else None
        if threat_lvl is not None and isinstance(threat_lvl, (int, float)) and threat_lvl > 0:
            spec = resolve_symbol(context.symbol)
            atr_val = context.volatility.atr if context.volatility.atr > 0 else (entry_price * 0.005)
            if tentative_bias == "BUY" and entry_price < threat_lvl < tp_price:
                adjusted_tp = round(threat_lvl - (atr_val * 0.1), spec.digits)
                if adjusted_tp >= entry_price + (risk_dist * 1.5):
                    logger.info(f"[{context.symbol}] Devil's Advocate threat level {threat_lvl} detected ahead of TP! Tucking TP: {tp_price} -> {adjusted_tp}")
                    tp_price = adjusted_tp
                    tp_dist = tp_price - entry_price
                    rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)
            elif tentative_bias == "SELL" and tp_price < threat_lvl < entry_price:
                adjusted_tp = round(threat_lvl + (atr_val * 0.1), spec.digits)
                if adjusted_tp <= entry_price - (risk_dist * 1.5):
                    logger.info(f"[{context.symbol}] Devil's Advocate threat level {threat_lvl} detected ahead of TP! Tucking TP: {tp_price} -> {adjusted_tp}")
                    tp_price = adjusted_tp
                    tp_dist = entry_price - tp_price
                    rr_ratio = round(tp_dist / (risk_dist + 1e-9), 2)



        strategy_probs = self.strategy_selector.select_strategy_probabilities(
            regime, context=context, account_equity=account_balance
        )
        best_strategy = max(strategy_probs.items(), key=lambda x: x[1])[0]

        ai_score = sum(r.score for r in analyst_reports.values()) / max(1, len(analyst_reports)) if analyst_reports else 0.0

        of_res = {"signal": "NEUTRAL", "strength": 0.0, "institutional_activity": False}
        if mtf_data and "primary" in mtf_data and not mtf_data["primary"].empty:
            of_res = self.order_flow.analyze_order_flow(mtf_data["primary"])
            
            if of_res["institutional_activity"] and of_res["signal"] == tentative_bias:
                ai_score = min(100.0, ai_score + (of_res["strength"] * 10.0))
                logger.info(f"[{context.symbol}] Institutional Order Flow aligns with {tentative_bias}! Boosting AI score to {ai_score:.1f}")
            elif of_res["institutional_activity"] and of_res["signal"] != "NEUTRAL":
                ai_score = max(0.0, ai_score - (of_res["strength"] * 10.0))
                logger.warning(f"[{context.symbol}] Institutional Order Flow opposes {tentative_bias}! Penalizing AI score to {ai_score:.1f}")

        final_win_p, loss_p, ev, hypotheses, calibrated_win_p = self._compute_blended_probability(
            context, regime, analyst_reports, devil_report, tentative_bias, rr_ratio, risk_dist, account_balance, risk_per_trade_pct
        )
        
        # 1. Apply Empirical Trade Pattern Memory Feedback (B1-WIRING)
        regime_str = regime.primary_regime.value if regime and hasattr(regime, "primary_regime") else "GLOBAL"
        session_str = context.session.current_session if context.session else "UNKNOWN"
        is_prime = context.session.is_prime_session if context.session else True
        pattern_memory = self.self_learning.get_pattern_win_rate_and_ev(
            symbol=context.symbol,
            regime=regime_str,
            session_name=session_str,
            is_prime=is_prime
        )
        if pattern_memory.get("sample_size", 0) >= 3:
            p_mult = pattern_memory.get("conviction_multiplier", 1.0)
            calibrated_win_p = min(0.99, max(0.10, calibrated_win_p * p_mult))
            final_win_p = min(0.99, max(0.10, final_win_p * p_mult))
            if pattern_memory.get("empirical_edge"):
                ai_score = min(100.0, ai_score + 5.0)
                logger.info(f"[{context.symbol}] Empirical pattern edge: WinRate={pattern_memory['win_rate']*100:.0f}%, EV={pattern_memory['avg_ev']:.2f}")

        # 2. Apply Post-News Stop-Hunt Liquidity Sweep Reaction (B5-WIRING)
        news_reaction = GLOBAL_NEWS_ENGINE.evaluate_post_news_sweep_reaction(
            symbol=context.symbol,
            sweep_detected=context.liquidity.sweep_detected,
            sweep_type=context.liquidity.sweep_type,
            sweep_magnitude_pips=context.liquidity.sweep_magnitude
        )
        if news_reaction.get("news_reversal_setup"):
            c_boost = news_reaction.get("conviction_boost", 0.0)
            calibrated_win_p = min(0.99, calibrated_win_p + c_boost)
            final_win_p = min(0.99, final_win_p + c_boost)
            ai_score = min(100.0, ai_score + 8.0)
            logger.info(f"[{context.symbol}] {news_reaction.get('reason')}")

        # 3. Apply Multi-Timeframe Top-Down Confluence Score (B7-WIRING)
        mtf_score = getattr(context, "mtf_confluence_score", 0.0)
        if tentative_bias == "BUY":
            if mtf_score >= 30.0:
                ai_score = min(100.0, ai_score + (mtf_score / 20.0))
            elif mtf_score <= -30.0:
                ai_score = max(0.0, ai_score - (abs(mtf_score) / 10.0))
        elif tentative_bias == "SELL":
            if mtf_score <= -30.0:
                ai_score = min(100.0, ai_score + (abs(mtf_score) / 20.0))
            elif mtf_score >= 30.0:
                ai_score = max(0.0, ai_score - (mtf_score / 10.0))

        # 3.5. Apply Order Flow Volume Delta Score (E1-WIRING)
        of_data = getattr(context, "order_flow", {})
        delta_score = float(of_data.get("delta_score", 0.0)) if isinstance(of_data, dict) else 0.0
        if tentative_bias == "BUY":
            if delta_score >= 35.0:
                ai_score = min(100.0, ai_score + 5.0)
            elif delta_score <= -35.0:
                ai_score = max(0.0, ai_score - 8.0)
        elif tentative_bias == "SELL":
            if delta_score <= -35.0:
                ai_score = min(100.0, ai_score + 5.0)
            elif delta_score >= 35.0:
                ai_score = max(0.0, ai_score - 8.0)

        # 4. Standard Regime Multiplier
        if regime:
            sl_multiplier = self.self_learning.get_regime_multiplier(regime_str)
            if sl_multiplier != 1.0:
                logger.info(f"[{context.symbol}] Self-Learning Engine adjusting {regime_str} Win Prob by {sl_multiplier}x")
                calibrated_win_p = min(0.99, calibrated_win_p * sl_multiplier)
                final_win_p = min(0.99, final_win_p * sl_multiplier)

        # Recompute EV from the (now fully adjusted) blended win probability so the
        # Expected Value shown/used for gating is consistent with the displayed probability.
        if tentative_bias in ["BUY", "SELL"]:
            loss_p = round(1.0 - final_win_p, 2)
            _risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))
            _win_dollars = _risk_dollars * rr_ratio
            _spec = resolve_symbol(context.symbol)
            _est_lots = max(0.01, _risk_dollars / (max(risk_dist, 1e-4) * _spec.contract_size))
            _spread_cost = context.volatility.current_spread_pips * _spec.pip_value_per_lot * _est_lots
            _slippage = (context.volatility.atr * 0.02) * _est_lots
            ev = round(float((final_win_p * _win_dollars) - (loss_p * _risk_dollars) - _spread_cost - _slippage), 2)
        else:
            loss_p = round(1.0 - final_win_p, 2)
            ev = 0.0

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
        
        from jarvis.market.sessions import SessionEngine
        mkt_status = SessionEngine.get_market_trading_status(context.symbol, dt=getattr(context, "timestamp", None))
        is_mkt_open = mkt_status.get("is_open", True)

        gate_passed = quality_gate.passed
        failing_reasons = quality_gate.failing_reasons

        # ---- ML Meta-Label confirmation gate (safe: neutral until a model is trained) ----
        meta_label_prob = None
        gate_policy_decision = "PASS"
        softened_gates: List[str] = []
        if recent_candles and len(recent_candles) >= self.meta_labeler.MIN_WINDOW:
            _bias = 1.0 if tentative_bias == "BUY" else (-1.0 if tentative_bias == "SELL" else 0.0)
            meta_label_prob = self.meta_labeler.predict_proba(recent_candles, bias=_bias)
            if meta_label_prob is not None:
                quality_gate.checks["ML Meta-Label Confirmation"] = meta_label_prob >= self.meta_labeler.MIN_PROB
                quality_gate.failing_reasons = [
                    r for r in quality_gate.failing_reasons if r != "ML Meta-Label Confirmation"
                ]
                if meta_label_prob < self.meta_labeler.MIN_PROB:
                    quality_gate.failing_reasons.append("ML Meta-Label Confirmation")
                quality_gate.passed = len(quality_gate.failing_reasons) == 0
                failing_reasons = quality_gate.failing_reasons
                gate_passed = quality_gate.passed

        # ---- Adaptive gate strictness (AI-decided hard vs soft) ----
        if not gate_passed:
            _rwr = pattern_memory.get("win_rate") if pattern_memory.get("sample_size", 0) >= 5 else None
            if _is_forex(context.symbol):
                # Forex is the LIVE trading domain. When confidence is decent (>=0.50) and
                # only NON-critical gates fail (<=2), allow execution (softened with a small
                # confidence penalty). Hard gates (session/drawdown/margin/regime) always block.
                _soft_only = [g for g in failing_reasons if g not in HARD_GATES]
                if _soft_only and len(_soft_only) <= 2 and calibrated_win_p >= 0.50:
                    _pen = min(
                        self.gate_policy.confidence_penalty(_soft_only),
                        max(0.0, calibrated_win_p - 0.45)
                    )
                    calibrated_win_p = max(0.45, calibrated_win_p - _pen)
                    final_win_p = max(0.45, final_win_p - _pen)
                    loss_p = round(1.0 - final_win_p, 2)
                    gate_passed = True
                    failing_reasons = []
                    quality_gate.passed = True
                    quality_gate.failing_reasons = []
                    gate_policy_decision = "SOFTEN"
                    softened_gates = _soft_only
                else:
                    gate_policy_decision = "BLOCK"
            else:
                _decision, _soft = self.gate_policy.decide(failing_reasons, _rwr)
                if _decision == "SOFTEN":
                    _pen = self.gate_policy.confidence_penalty(_soft)
                    calibrated_win_p = max(0.05, calibrated_win_p - _pen)
                    final_win_p = max(0.05, final_win_p - _pen)
                    loss_p = round(1.0 - final_win_p, 2)
                    softened_gates = _soft
                    gate_passed = True
                    failing_reasons = []
                    quality_gate.passed = True
                    quality_gate.failing_reasons = []
                    gate_policy_decision = "SOFTEN"
                else:
                    gate_policy_decision = "BLOCK"

        if not is_mkt_open:
            decision_action = "NO_TRADE"
        elif gate_passed:
            decision_action = "EXECUTE"
        elif tentative_bias in ["BUY", "SELL"] and len(failing_reasons) <= 2 and quality_gate.checks.get("Regime Viability", False):
            decision_action = "WAIT"
        else:
            decision_action = "NO_TRADE"

        waiting_reasons = []
        rejection_reasons = []

        if gate_policy_decision == "SOFTEN" and softened_gates:
            waiting_reasons.extend([f"Softened gate (AI adaptive, win-rate evidence): {g}" for g in softened_gates])

        if not is_mkt_open:
            rejection_reasons.append(
                f"Market session is closed for the weekend ({mkt_status.get('reason', 'Weekend Close')}). Live order execution halted until session opens on {mkt_status.get('next_open_ist', 'Monday')}."
            )
        elif decision_action == "WAIT":
            for reason in failing_reasons:
                if "Calibrated Win Prob" in reason:
                    waiting_reasons.append(f"Calibrated probability ({calibrated_win_p*100:.0f}%) below institutional threshold (55%).")
                elif "Order Flow" in reason:
                    waiting_reasons.append("Awaiting institutional volume / order flow momentum confirmation.")
                elif "Premium/Discount" in reason:
                    zone = context.structure.discount_premium_zone
                    waiting_reasons.append(f"Price currently in {zone} zone -- awaiting retracement into favorable discount/equilibrium.")
                elif "Risk/Reward" in reason:
                    waiting_reasons.append(f"Current setup R:R (1:{rr_ratio:.2f}) awaiting optimal price fill.")
                elif "Positive Expected Value" in reason:
                    waiting_reasons.append(f"Expected value (${ev:.2f}) awaiting higher statistical edge.")
                elif "AI Multi-Score" in reason:
                    waiting_reasons.append(f"Blended AI score ({ai_score:.1f}) pending multi-agent consensus.")
                elif "Spread Protection" in reason:
                    waiting_reasons.append(f"Spread ({context.volatility.current_spread_pips:.1f} pips) elevated — awaiting spread normalization.")
                else:
                    waiting_reasons.append(f"Awaiting validation check: {reason}.")
            if not waiting_reasons:
                waiting_reasons.append("Awaiting confirmation of institutional entry trigger and candle close.")

        elif decision_action == "NO_TRADE" or not gate_passed:
            for reason in failing_reasons:
                if "Positive Expected Value" in reason:
                    rejection_reasons.append(f"Negative / insufficient mathematical edge (EV: ${ev:.2f}).")
                elif "Devil Adversarial" in reason:
                    rejection_reasons.append(f"Adversarial counter-thesis penalty too high ({devil_report.penalty_score:.1f} / {self.max_devil_penalty:.1f}).")
                elif "Premium/Discount" in reason:
                    zone = context.structure.discount_premium_zone
                    rejection_reasons.append(f"Unfavorable pricing zone ({zone}) for {tentative_bias} execution.")
                elif "Regime Viability" in reason:
                    rejection_reasons.append(f"Regime {regime.primary_regime.value} classified as hazardous / non-tradable.")
                elif "Spread Protection" in reason:
                    rejection_reasons.append(f"Spread {context.volatility.current_spread_pips:.1f} pips exceeds maximum tolerable risk limit.")
                elif "Drawdown Safety" in reason:
                    rejection_reasons.append("Account drawdown exceeds safety threshold (5.0%).")
                elif "Calibrated Win Prob" in reason:
                    rejection_reasons.append(f"Model win probability ({calibrated_win_p*100:.0f}%) fails minimum hurdle.")
                else:
                    rejection_reasons.append(f"Failed quality check: {reason}.")
            for threat in devil_report.threats_detected[:2]:
                if threat not in rejection_reasons:
                    rejection_reasons.append(f"Adversarial risk: {threat}")
            if not rejection_reasons and tentative_bias == "HOLD":
                rejection_reasons.append("No actionable institutional market structure or clear directional bias detected.")

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
            first_target_price=first_target_price,
            first_target_volume_pct=first_target_volume_pct,
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
            waiting_reasons=waiting_reasons,
            rejection_reasons=rejection_reasons,
            decision=decision_action,
            execution_authorized=gate_passed,
            context=context,
            pattern_sample_size=pattern_memory.get("sample_size", 0) if "pattern_memory" in locals() and pattern_memory else 0,
            meta_label_prob=meta_label_prob,
            gate_policy_decision=gate_policy_decision
        )
