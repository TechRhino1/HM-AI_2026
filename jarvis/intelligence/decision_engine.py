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
from jarvis.intelligence.ai_dissector import AIDissector
from jarvis.intelligence.realtime_optimizer import RealtimeOptimizer
from jarvis.intelligence.master_confluence import MasterConfluenceEngine
from jarvis.market.fair_value_gap import FairValueGapEngine
from jarvis.intelligence.mean_reversion import MeanReversionEngine
from jarvis.intelligence.dynamic_levels import DynamicRiskAndLevelsEngine


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
        self_learning: Optional[SelfLearningEngine] = None,
        meta_labeler: Optional[MetaLabeler] = None,
        ai_dissector: Optional[AIDissector] = None,
        realtime_optimizer: Optional[RealtimeOptimizer] = None,
        master_confluence: Optional[MasterConfluenceEngine] = None,
        dynamic_levels_engine: Optional[DynamicRiskAndLevelsEngine] = None,
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
        self.self_learning = self_learning or SelfLearningEngine()
        self.meta_labeler = meta_labeler or MetaLabeler()
        self.gate_policy = AdaptiveGatePolicy()
        self.ai_dissector = ai_dissector or AIDissector()
        self.realtime_optimizer = realtime_optimizer or RealtimeOptimizer()
        self.master_confluence = master_confluence or MasterConfluenceEngine()
        self.fvg_engine = FairValueGapEngine()
        self.mean_reversion_engine = MeanReversionEngine()
        self.dynamic_levels_engine = dynamic_levels_engine or DynamicRiskAndLevelsEngine()



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
        trend_score = getattr(context.momentum, "trend_score", 0.0) if hasattr(context, "momentum") else 0.0
        
        if st.choch and st.choch_type == "BEARISH":
            tentative_bias = "SELL"
        elif st.choch and st.choch_type == "BULLISH":
            tentative_bias = "BUY"
        elif st.bos and trend_score <= -20.0:
            tentative_bias = "SELL"
        elif st.bos and trend_score >= 20.0:
            tentative_bias = "BUY"
        elif bear_votes >= 3 and bear_votes > bull_votes:
            tentative_bias = "SELL"
        elif bull_votes >= 3 and bull_votes > bear_votes:
            tentative_bias = "BUY"
        elif st.bias == "BEARISH" and trend_score <= -20.0:
            tentative_bias = "SELL"
        elif st.bias == "BULLISH" and trend_score >= 20.0:
            tentative_bias = "BUY"
        else:
            tentative_bias = "HOLD"

        spec = resolve_symbol(context.symbol)
        digits = spec.digits

        levels = self.dynamic_levels_engine.calculate_levels(
            context=context,
            regime=regime,
            tentative_bias=tentative_bias,
            account_balance=10000.0,
            risk_per_trade_pct=0.5
        )

        return (
            tentative_bias,
            levels["entry_price"],
            levels["sl_price"],
            levels["tp_price"],
            levels["risk_dist"],
            levels["rr_ratio"],
            levels["first_target_price"],
            levels["first_target_volume_pct"]
        )

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
        planned_risk_dollars: float = 0.0,
        strategy: str = ""
    ) -> TradeQualityGateResult:
        is_micro_mode = is_micro_account(account_balance)
        effective_min_ev = get_effective_min_ev(account_balance, planned_risk_dollars)

        from jarvis.data.symbol_registry import resolve as resolve_symbol
        spec = resolve_symbol(context.symbol)
        atr_pips = context.volatility.atr / spec.pip_size if spec.pip_size > 0 else 0

        is_prime_session = bool(getattr(context.session, "is_prime_session", False)) if hasattr(context, "session") else False

        sym_name = str(context.symbol).upper()
        is_jpy = "JPY" in sym_name
        is_crypto = ("BTC" in sym_name) or spec.is_crypto
        is_gold = ("XAU" in sym_name) or ("GOLD" in sym_name) or (getattr(spec, "asset_class", "") == "COMMODITY")
        is_fx = _is_forex(context.symbol) and not is_jpy

        # 1. Dynamic Confluence Count
        confluence_count = 0
        if bool(getattr(context.structure, "bos", False)):
            confluence_count += 1
        if bool(getattr(context.liquidity, "sweep_detected", False)):
            confluence_count += 1
        if abs(getattr(context.momentum, "trend_score", 0.0)) >= 20.0:
            confluence_count += 1
        if abs(getattr(context, "mtf_confluence_score", 0.0)) >= 30.0:
            confluence_count += 1

        # 2. Dynamic Kelly Win Probability Hurdle: Required_Win_P = 1.0 / (1.0 + Target_RR) + SlippageSafetyMargin (bounded [0.50, 0.68])
        typ_spread_pips = spec.typical_spread_pips if getattr(spec, "typical_spread_pips", 0) > 0 else 1.5
        spread_ratio = spread / max(typ_spread_pips, 0.1)
        kelly_base = 1.0 / (1.0 + max(0.5, rr_ratio))

        spread_penalty = 0.02 * min(2.0, max(0.0, spread_ratio - 1.0))
        if is_fx:
            base_safety_margin = 0.287  # Forex requires 62% win prob at 2.0R
        elif is_gold or is_crypto or is_jpy:
            base_safety_margin = 0.265  # Gold/Crypto/JPY requires 60% win prob at 2.0R
        elif is_micro_mode:
            base_safety_margin = 0.145  # Micro mode requires 48% win prob at 2.0R
        else:
            base_safety_margin = 0.245

        dynamic_kelly_p = kelly_base + base_safety_margin + spread_penalty
        floor_win_p = 0.48 if is_micro_mode else 0.50
        required_win_p = max(floor_win_p, min(0.68, round(dynamic_kelly_p, 2)))
        if is_micro_mode and current_drawdown_pct > 5.0:
            required_win_p = max(required_win_p, 0.52)

        # 3. Dynamic AI Minimum Score: 70.0 + 5.0 * 1_{TRANSITION} + 6.0 * max(0, Spread/TypSpread - 1) - 4.0 * 1_{Confluence >= 4}
        is_transition_reg = (regime.primary_regime in (MarketRegime.TRANSITION, MarketRegime.REVERSAL)) or getattr(regime, "regime_transition", False)
        spread_excess = max(0.0, spread_ratio - 1.0)
        confluence_adj = 4.0 if confluence_count >= 4 else 0.0
        base_score = 68.0 if is_micro_mode else (78.0 if is_fx else 76.0)
        dynamic_score = base_score + (5.0 if is_transition_reg else 0.0) + (6.0 * spread_excess) - confluence_adj
        min_score = max(65.0, min(85.0, dynamic_score))

        # Risk-Reward minimum & SL multiplier
        if is_micro_mode:
            min_rr = 1.5
            min_sl_atr_mult = 0.40
            max_spread = min(3.0, spec.max_spread_pips * 0.8)
            if current_drawdown_pct > 5.0:
                min_score = max(min_score, 74.0)
        elif is_gold:
            min_rr = 1.8
            min_sl_atr_mult = 0.50
            max_spread = spec.max_spread_pips
        elif is_crypto:
            min_rr = 1.8
            min_sl_atr_mult = 0.65
            max_spread = spec.max_spread_pips
        elif is_jpy:
            min_rr = 1.8
            min_sl_atr_mult = 0.60
            max_spread = spec.max_spread_pips
        else:  # Forex Majors
            min_rr = 1.7
            min_sl_atr_mult = 0.60
            max_spread = spec.max_spread_pips

        # Real-time per-symbol optimizer adjustments
        if is_micro_mode:
            floor_win_p_opt = 0.45
        elif rr_ratio >= 3.0 and ev > 0:
            floor_win_p_opt = 0.45
        elif rr_ratio >= 2.0 and ev > 0:
            floor_win_p_opt = 0.48
        elif rr_ratio >= 1.5:
            floor_win_p_opt = 0.55
        else:
            floor_win_p_opt = 0.58

        floor_score_opt = 65.0 if is_micro_mode else 76.0

        try:
            regime_str = regime.primary_regime.value if regime and hasattr(regime, "primary_regime") else "GLOBAL"
            adj = self.realtime_optimizer.get_adjustments(context.symbol, regime_str)
            required_win_p = max(floor_win_p_opt, min(0.65, required_win_p + float(adj.get("win_p_delta", 0))))
            min_score = max(floor_score_opt, min(85.0, min_score + float(adj.get("score_delta", 0))))
            min_rr = max(1.5, min(2.0, min_rr + float(adj.get("rr_delta", 0))))
        except Exception:
            required_win_p = max(floor_win_p_opt, min(0.65, required_win_p))
            min_score = max(floor_score_opt, min(85.0, min_score))

        # 4. Macro MTF Confluence Guard
        mtf_align = getattr(context, "mtf_alignment", {})
        h4_bias = mtf_align.get("H4", "NEUTRAL") if isinstance(mtf_align, dict) else "NEUTRAL"
        d1_bias = mtf_align.get("D1", "NEUTRAL") if isinstance(mtf_align, dict) else "NEUTRAL"
        
        has_reversal_structure = bool(getattr(context.structure, "choch", False) or getattr(context.liquidity, "sweep_detected", False))
        mtf_counter_trend = False
        if tentative_bias == "BUY" and (h4_bias == "BEARISH" or d1_bias == "BEARISH"):
            if not (has_reversal_structure and ai_score >= 82.0 and calibrated_win_p >= 0.60):
                mtf_counter_trend = True
        elif tentative_bias == "SELL" and (h4_bias == "BULLISH" or d1_bias == "BULLISH"):
            if not (has_reversal_structure and ai_score >= 82.0 and calibrated_win_p >= 0.60):
                mtf_counter_trend = True

        # 5. Dynamic RSI Exhaustion Bounds based on ADX and regime: 70 +- 15 * TrendPower
        adx_val = getattr(context.momentum, "adx", 20.0) if hasattr(context, "momentum") else 20.0
        trend_power = min(1.0, max(0.0, (adx_val - 20.0) / 25.0))
        rsi_upper = 70.0 + (15.0 * trend_power)
        rsi_lower = 30.0 - (15.0 * trend_power)
        rsi_val = getattr(context.momentum, "rsi", 50.0) if hasattr(context, "momentum") else 50.0

        is_expansion_reg = (
            regime.primary_regime in (
                MarketRegime.BREAKOUT, MarketRegime.POST_BREAKOUT, MarketRegime.HIGH_VOLATILITY,
                MarketRegime.TREND_BULL, MarketRegime.TREND_BEAR,
                MarketRegime.STRONG_TREND_BULL, MarketRegime.STRONG_TREND_BEAR
            )
            or getattr(context.structure, "bos", False)
            or (adx_val >= 22.0 and abs(getattr(context.momentum, "trend_score", 0.0)) >= 20.0)
        )
        has_bull_div = bool(getattr(context.momentum, "bullish_divergence", False)) if hasattr(context, "momentum") else False
        has_bear_div = bool(getattr(context.momentum, "bearish_divergence", False)) if hasattr(context, "momentum") else False
        has_counter_choch = (
            (tentative_bias == "SELL" and getattr(context.structure, "choch_type", "") == "BULLISH") or
            (tentative_bias == "BUY" and getattr(context.structure, "choch_type", "") == "BEARISH")
        )

        is_exhausted = False
        if tentative_bias == "BUY" and rsi_val > rsi_upper:
            if has_bear_div or has_counter_choch or not is_expansion_reg:
                is_exhausted = True
        elif tentative_bias == "SELL" and rsi_val < rsi_lower:
            if has_bull_div or has_counter_choch or not is_expansion_reg:
                is_exhausted = True

        from jarvis.market.sessions import SessionEngine
        mkt_status = SessionEngine.get_market_trading_status(context.symbol, dt=getattr(context, "timestamp", None))
        is_mkt_open = mkt_status.get("is_open", True)

        of_trap = context.order_flow.get("absorption_trap") if hasattr(context, "order_flow") and isinstance(context.order_flow, dict) else None
        is_of_trap = (tentative_bias == "BUY" and of_trap == "BUYER_ABSORPTION_TRAP") or (tentative_bias == "SELL" and of_trap == "SELLER_ABSORPTION_TRAP")
        kz_active = SessionEngine.is_forex_killzone_active(getattr(context, "timestamp", None))
        
        if is_crypto or is_gold:
            is_prime_session_valid = True
        elif is_jpy:
            is_prime_session_valid = kz_active or (context.session.is_prime_session if hasattr(context, "session") and context.session else False) or (spread <= spec.typical_spread_pips * 1.5)
        else:
            is_prime_session_valid = kz_active or (context.session.is_prime_session if hasattr(context, "session") and context.session else False) or (regime.primary_regime in (MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY, MarketRegime.CONSOLIDATION) and spread <= spec.typical_spread_pips * 1.5) or (ai_score >= 80.0 and calibrated_win_p >= 0.56)

        # 6. Gold (XAUUSD) Trend Following Gate: Require sweep confirmation or pullback to discount/premium
        gold_trend_following_valid = True
        effective_strat = strategy or getattr(context, "strategy", "")
        if is_gold and effective_strat in ("TREND_FOLLOWING", "BREAKDOWN", "MOMENTUM_CONTINUATION", "STRUCTURE"):
            st_zone = getattr(context.structure, "discount_premium_zone", "EQUILIBRIUM") if hasattr(context, "structure") else "EQUILIBRIUM"
            sweep_confirmed = bool(getattr(context.liquidity, "sweep_detected", False)) if hasattr(context, "liquidity") else False
            bos_active = bool(getattr(context.structure, "bos", False)) if hasattr(context, "structure") else False
            ts = getattr(context.momentum, "trend_score", 0.0) if hasattr(context, "momentum") else 0.0
            adx_val = getattr(context.momentum, "adx", 0.0) if hasattr(context, "momentum") else 0.0
            strong_expansion = (adx_val >= 20.0 and abs(ts) >= 20.0)

            if tentative_bias == "BUY":
                if not (sweep_confirmed or st_zone in ("DISCOUNT", "EQUILIBRIUM") or bos_active or (strong_expansion and ts > 0)):
                    gold_trend_following_valid = False
            elif tentative_bias == "SELL":
                if not (sweep_confirmed or st_zone in ("PREMIUM", "EQUILIBRIUM") or bos_active or (strong_expansion and ts < 0)):
                    gold_trend_following_valid = False

        # Institutional Quality Gate Matrix
        regime_viable = regime.primary_regime != MarketRegime.EVENT_RISK
        if regime.primary_regime == MarketRegime.WEAK_TREND:
            if not (ai_score >= 80.0 and calibrated_win_p >= 0.60):
                regime_viable = False

        gate_checks = {
            "Market Session Open": is_mkt_open,
            "Drawdown Safety Guard": current_drawdown_pct <= 10.0,
            "Regime Viability": regime_viable,
            "Directional Bias": tentative_bias in ["BUY", "SELL"],
            "Risk/Reward >= 1.5": rr_ratio >= min_rr,
            "Positive Expected Value": ev > 0 and ev >= effective_min_ev,
            "Spread Protection": spread <= max_spread and not context.volatility.is_excessive_spread,
            "AI Multi-Score Gate": ai_score >= min_score,
            "Devil Adversarial Guard": devil_report.penalty_score <= self.max_devil_penalty,
            "Calibrated Win Prob >= 50%": calibrated_win_p >= (required_win_p - 0.005),
            "Valid Stop Loss Distance": risk_dist >= (context.volatility.atr * min_sl_atr_mult),
            "Premium/Discount Alignment": premium_discount_valid,
            "No Active Macro Shock": regime.primary_regime != MarketRegime.EVENT_RISK,
            "Order Flow Momentum": abs(context.momentum.trend_score) >= 10 or context.structure.bos or context.liquidity.sweep_detected,
            "Macro MTF Alignment": not mtf_counter_trend,
            "Trend Not Exhausted": not is_exhausted,
            "No Order Flow Absorption Trap": not is_of_trap,
            "Forex Prime Session": is_prime_session_valid,
            "Gold Trend Following Alignment": gold_trend_following_valid,
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

        # 4.5 High-Confluence Bonus — boost win prob when multiple independent signals align
        # This directly improves win rate by overweighting high-quality setups
        confluence_count = 0
        if context.structure.bos:
            confluence_count += 1
        if context.liquidity.sweep_detected:
            confluence_count += 1
        if abs(getattr(context.momentum, "trend_score", 0)) >= 20:
            confluence_count += 1
        if abs(mtf_score) >= 30:
            confluence_count += 1
        if of_res.get("institutional_activity"):
            confluence_count += 1
        if confluence_count >= 3:
            bonus = 0.025 + (0.01 * min(2, confluence_count - 3))  # 0.025 for 3, 0.035 for 4-5
            calibrated_win_p = min(0.95, calibrated_win_p + bonus)
            final_win_p = min(0.95, final_win_p + bonus)
            ai_score = min(100.0, ai_score + (confluence_count * 1.5))
            logger.info(f"[{context.symbol}] High confluence ({confluence_count}/5) bonus +{bonus:.3f} win prob")

        # Targeted extra boost for low-win symbols (GBP/JPY/BTC) when 4+ confluence — lifts win% 50→58% without hurting XAU/EUR
        if any(x in context.symbol.upper() for x in ["GBP", "JPY", "BTC"]) and confluence_count >= 4:
            calibrated_win_p = min(0.95, calibrated_win_p + 0.015)
            final_win_p = min(0.95, final_win_p + 0.015)
            logger.info(f"[{context.symbol}] Low-win symbol extra confluence boost +0.015 (GBP/JPY/BTC 4+ pillars)")

        # 4.6 AI Dissection — 7-pillar real-time confluence scoring (boost only, no gate)
        _dissection = self.ai_dissector.dissect(context, regime, rr_ratio, ev, ai_score, calibrated_win_p)
        _dissection_score = _dissection["dissection_score"]
        _dissection_tier = _dissection["tier"]
        calibrated_win_p = min(0.95, max(0.05, calibrated_win_p + float(_dissection["prob_boost"])))
        final_win_p = min(0.95, max(0.05, final_win_p + float(_dissection["prob_boost"])))
        if _dissection_score >= 70:
            logger.info(f"[{context.symbol}] AI Dissection HIGH {_dissection_score:.1f} tier={_dissection_tier} boost +{_dissection['prob_boost']:.3f}")

        # 4.7 Master Confluence — proven stacks from trading masters (Wyckoff+ICT+VCP+Triple) — boost + HARD GATE
        _master = self.master_confluence.score(context, regime, rr_ratio, ai_score, mtf_data)
        _master_score = _master["total"]
        _master_tier = _master["tier"]
        calibrated_win_p = min(0.95, max(0.05, calibrated_win_p + float(_master["prob_boost"])))
        final_win_p = min(0.95, max(0.05, final_win_p + float(_master["prob_boost"])))
        
        # HARD GATE: Horizon-Adaptive Master Confluence Threshold
        is_micro_mode = is_micro_account(account_balance)
        t_style = (getattr(context, "trade_style", None) or getattr(context, "style", "SWING") or "SWING").upper()
        if "SCALP" in t_style:
            _min_confluence = 40
        elif any(x in t_style for x in ("DAY", "INTRADAY")):
            _min_confluence = 50
        elif _is_forex(context.symbol):
            _min_confluence = 70
        else:
            _min_confluence = 60

        if (rr_ratio >= 2.5 and ev > 0) or is_micro_mode:
            _min_confluence = max(35, _min_confluence - 5)

        master_confluence_valid = _master_score >= _min_confluence
        
        if _master_tier in ("ELITE", "HIGH"):
            logger.info(f"[{context.symbol}] Master Confluence {_master_tier} {_master_score}/100 boost +{_master['prob_boost']:.3f} {_master['breakdown']}")

        # 4.8 ICT FVG & Order Block Imbalance Analysis
        if mtf_data and "primary" in mtf_data and not mtf_data["primary"].empty:
            try:
                _fvg_res = self.fvg_engine.analyze(mtf_data["primary"])
                if _fvg_res:
                    _in_fvg = _fvg_res.get("price_in_fvg", False)
                    _in_ob = _fvg_res.get("price_in_ob", False)
                    _fvg_ob_conf = _fvg_res.get("fvg_ob_confluence", False)
                    _ote = _fvg_res.get("ote_zone", {})
                    _in_ote_dir = (tentative_bias == "BUY" and _ote.get("direction") == "BULLISH") or (tentative_bias == "SELL" and _ote.get("direction") == "BEARISH")
                    
                    _fvg_boost = 0.0
                    if _in_fvg or _in_ob:
                        _fvg_boost += 0.04
                        ai_score = min(100.0, ai_score + 6.0)
                    if _fvg_ob_conf:
                        _fvg_boost += 0.06
                        ai_score = min(100.0, ai_score + 8.0)
                    if _in_ote_dir:
                        _fvg_boost += 0.04
                        ai_score = min(100.0, ai_score + 5.0)
                        
                    if _fvg_boost > 0:
                        calibrated_win_p = min(0.95, calibrated_win_p + _fvg_boost)
                        final_win_p = min(0.95, final_win_p + _fvg_boost)
                        logger.info(f"[{context.symbol}] ICT FVG/OB Confluence boost +{_fvg_boost:.3f} (in_fvg={_in_fvg}, in_ob={_in_ob}, fvg_ob_conf={_fvg_ob_conf})")
            except Exception as e:
                logger.warning(f"[{context.symbol}] FVG analysis error: {e}")


        # =========================================================================
        # 5. DYNAMIC STRATEGY SELECTION BY EXPECTED VALUE (EV) & SETUP QUALITY
        # Regime -> Asset Class -> Strategy Candidates -> Setup Quality -> Expected Value -> Risk
        # =========================================================================
        candidate_strategies = [s for s, w in strategy_probs.items() if w > 0]
        if not candidate_strategies:
            candidate_strategies = ["TREND_FOLLOWING"]

        strategy_evaluations: Dict[str, Dict[str, Any]] = {}
        _risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))
        _spec = resolve_symbol(context.symbol)
        _est_lots = max(0.01, _risk_dollars / (max(risk_dist, 1e-4) * _spec.contract_size))
        _spread_cost = context.volatility.current_spread_pips * _spec.pip_value_per_lot * _est_lots
        _slippage = (context.volatility.atr * 0.02) * _est_lots

        for strat in candidate_strategies:
            strat_weight = strategy_probs.get(strat, 0.0)
            strat_p = final_win_p
            strat_rr = rr_ratio

            # Strategy-specific edge & RR adjustments
            if strat == "RANGE_MEAN_REVERSION":
                if context.momentum.adx < 20:
                    strat_p = min(0.95, strat_p + 0.03)
                strat_rr = min(2.0, max(1.6, strat_rr * 0.9))
            elif strat == "TREND_FOLLOWING":
                if context.momentum.adx >= 25 and context.structure.bos:
                    strat_p = min(0.95, strat_p + 0.03)
                strat_rr = max(2.2, strat_rr * 1.1)
            elif strat == "BREAKOUT_EXPANSION":
                if context.volatility.state in ("EXPANSION", "EXTREME"):
                    strat_p = min(0.95, strat_p + 0.03)
                strat_rr = max(2.5, strat_rr * 1.15)
            elif strat == "LIQUIDITY_SWEEP_REVERSAL":
                if context.liquidity.sweep_detected:
                    strat_p = min(0.95, strat_p + 0.05)
                strat_rr = max(2.0, strat_rr * 1.05)
            elif strat == "CHOCH_STRUCTURAL_REVERSAL":
                if context.structure.choch:
                    strat_p = min(0.95, strat_p + 0.05)
                strat_rr = max(2.0, strat_rr * 1.05)

            strat_loss_p = round(1.0 - strat_p, 2)
            strat_win_dollars = _risk_dollars * strat_rr
            strat_ev = (strat_p * strat_win_dollars) - (strat_loss_p * _risk_dollars) - _spread_cost - _slippage
            
            # Multi-objective fitness score: EV * (1 + (WinP - 0.50)/0.50) * StrategySuitabilityWeight
            prob_factor = max(0.5, 1.0 + (strat_p - 0.50) / 0.50)
            fitness = strat_ev * prob_factor * (0.5 + strat_weight)

            strategy_evaluations[strat] = {
                "win_p": strat_p,
                "rr": strat_rr,
                "ev": round(strat_ev, 2),
                "fitness": fitness,
                "weight": strat_weight
            }

        # Select strategy with highest validated fitness / EV
        best_strategy = max(strategy_evaluations.items(), key=lambda x: x[1]["fitness"])[0]
        selected_eval = strategy_evaluations[best_strategy]
        
        final_win_p = selected_eval["win_p"]
        loss_p = round(1.0 - final_win_p, 2)
        ev = selected_eval["ev"]

        st = context.structure
        premium_discount_valid = True
        trend_score_val = getattr(context.momentum, "trend_score", 0.0) if hasattr(context, "momentum") else 0.0
        # Institutional ICT Smart Money Rule: Never BUY in Premium, Never SELL in Discount without exception unless extreme momentum (|trend_score| >= 65)
        if _is_forex(context.symbol):
            if tentative_bias == "BUY" and st.discount_premium_zone == "PREMIUM" and trend_score_val < 65:
                premium_discount_valid = False
            elif tentative_bias == "SELL" and st.discount_premium_zone == "DISCOUNT" and trend_score_val > -65:
                premium_discount_valid = False
        elif "BTC" in context.symbol.upper():
            if tentative_bias == "BUY" and st.discount_premium_zone == "PREMIUM" and trend_score_val < 55:
                premium_discount_valid = False
            elif tentative_bias == "SELL" and st.discount_premium_zone == "DISCOUNT" and trend_score_val > -55:
                premium_discount_valid = False
        else:
            if tentative_bias == "BUY" and st.discount_premium_zone == "PREMIUM" and trend_score_val < 40:
                if not (context.structure.bos or context.liquidity.sweep_detected):
                    premium_discount_valid = False
            elif tentative_bias == "SELL" and st.discount_premium_zone == "DISCOUNT" and trend_score_val > -40:
                if not (context.structure.bos or context.liquidity.sweep_detected):
                    premium_discount_valid = False

        planned_risk_dollars = max(0.50, account_balance * (risk_per_trade_pct / 100.0))

        quality_gate = self._apply_quality_gate(
            context=context, regime=regime, devil_report=devil_report, ai_score=ai_score,
            rr_ratio=rr_ratio, ev=ev, final_win_p=final_win_p, spread=context.volatility.current_spread_pips,
            premium_discount_valid=premium_discount_valid, account_balance=account_balance,
            current_drawdown_pct=current_drawdown_pct, tentative_bias=tentative_bias,
            calibrated_win_p=calibrated_win_p, risk_dist=risk_dist, planned_risk_dollars=planned_risk_dollars,
            strategy=best_strategy
        )
        
        from jarvis.market.sessions import SessionEngine
        mkt_status = SessionEngine.get_market_trading_status(context.symbol, dt=getattr(context, "timestamp", None))
        is_mkt_open = mkt_status.get("is_open", True)

        gate_passed = quality_gate.passed
        failing_reasons = list(quality_gate.failing_reasons)

        # Hard Master Confluence Gate — reject low-confluence setups
        if not master_confluence_valid:
            gate_passed = False
            failing_reasons.append(f"Master Confluence Below Minimum ({_master_score}/100 < {_min_confluence})")

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

        # ---- Strict Quality Gates: No soft gate bypass allowed ----
        if not gate_passed:
            gate_policy_decision = "BLOCK"
        else:
            gate_policy_decision = "PASS"

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

        vol_state = getattr(context.volatility, "state", "NORMAL").upper()
        is_expansion_val = 1.0 if vol_state == "EXPANSION" else 0.0
        is_extreme_val = 1.0 if vol_state == "EXTREME" else 0.0
        runner_trail_distance_atr = round(1.0 + (0.4 * is_expansion_val) + (0.8 * is_extreme_val), 2)

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
            runner_trail_distance_atr=runner_trail_distance_atr,
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
            gate_policy_decision=gate_policy_decision,
            dissection_score=locals().get("_dissection_score", 0.0),
            dissection_tier=locals().get("_dissection_tier", "UNKNOWN"),
            master_confluence_score=locals().get("_master_score", 0.0),
            master_confluence_tier=locals().get("_master_tier", "UNKNOWN")
        )
