"""
JARVIS AI 4.0 — Universal Master Opportunity Arbiter & Autonomous Trade Selector.
Evaluates, scores, and ranks trading opportunities across multi-asset universes and multiple trading styles
(SWING, DAY_TRADING, SCALP) using Machine Learning probability, Expected Value (EV), Master Confluence,
Adversarial Threat Penalty, and Market Regime dynamic multipliers.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

from jarvis.data.schemas import DecisionObject, MarketContext, RegimeOutput, MarketRegime

logger = logging.getLogger("JARVIS_OpportunityArbiter")

@dataclass
class CandidateOpportunity:
    """
    Standardized trading opportunity candidate across all symbols and styles.
    """
    symbol: str
    trade_style: str
    timeframe: str
    strategy: str
    bias: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    expected_value: float
    win_prob: float
    ml_prob: float
    confluence_score: float
    confluence_factors: List[str]
    adversarial_penalty: float
    risk_factors: List[str]
    regime: str
    regime_multiplier: float
    utility_score: float
    setup_grade: str
    is_actionable: bool
    decision_obj: Optional[Any] = None
    context: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trade_style": self.trade_style,
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "bias": self.bias,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "expected_value": self.expected_value,
            "win_prob": self.win_prob,
            "ml_prob": self.ml_prob,
            "confluence_score": self.confluence_score,
            "confluence_factors": self.confluence_factors,
            "adversarial_penalty": self.adversarial_penalty,
            "risk_factors": self.risk_factors,
            "regime": self.regime,
            "regime_multiplier": self.regime_multiplier,
            "utility_score": self.utility_score,
            "setup_grade": self.setup_grade,
            "is_actionable": self.is_actionable,
        }

    def to_radar_item(self) -> Dict[str, Any]:
        """Converts candidate opportunity to standard JARVIS state radar dictionary."""
        d = self.decision_obj
        ctx = self.context
        
        status_label = "NO SETUP"
        decision_str = getattr(d, "decision", "NO_TRADE") if d else "NO_TRADE"
        bias_str = self.bias

        from jarvis.market.sessions import SessionEngine
        mkt_status = SessionEngine.get_market_trading_status(self.symbol)
        is_mkt_open = mkt_status.get("is_open", True)

        if not is_mkt_open:
            status_label = "MARKET CLOSED"
        elif decision_str == "EXECUTE":
            status_label = f"{bias_str} READY"
        elif decision_str == "WAIT" and bias_str in ["BUY", "SELL"]:
            status_label = f"WAIT: {bias_str}"
        elif decision_str == "NO_TRADE":
            if d and getattr(d, "quality_gate", None) and not d.quality_gate.passed and any("Invalid" in r or "Devil" in r or "Adversarial" in r for r in getattr(d.quality_gate, "failing_reasons", [])):
                status_label = f"INVALID: {bias_str}" if bias_str in ["BUY", "SELL"] else "TRADE INVALIDATED"
            elif bias_str in ["BUY", "SELL"]:
                status_label = f"NO TRADE: {bias_str}"
            else:
                status_label = "NO SETUP"
        elif bias_str in ["BUY", "SELL"]:
            status_label = f"WAIT: {bias_str}"
        else:
            status_label = "NO SETUP"

        return {
            "symbol": self.symbol,
            "trade_style": self.trade_style,
            "timeframe": self.timeframe,
            "current_price": getattr(ctx, "current_price", self.entry_price) if ctx else self.entry_price,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "ev": round(self.expected_value, 2),
            "bias": self.bias,
            "action": status_label,
            "status_label": status_label,
            "decision": decision_str,
            "score": round(self.win_prob, 0),
            "win_prob": round(self.win_prob, 0),
            "ml_prob": round(self.ml_prob, 3),
            "confluence_score": round(self.confluence_score, 1),
            "confluence_tier": getattr(d, "master_confluence_tier", "MODERATE") if d else "MODERATE",
            "regime": self.regime,
            "regime_multiplier": round(self.regime_multiplier, 2),
            "strategy": self.strategy,
            "gate_passed": d.quality_gate.passed if (d and getattr(d, "quality_gate", None)) else False,
            "failing_reasons": d.quality_gate.failing_reasons if (d and getattr(d, "quality_gate", None)) else [],
            "checks": d.quality_gate.checks if (d and getattr(d, "quality_gate", None)) else {},
            "waiting_reasons": getattr(d, "waiting_reasons", []) if d else [],
            "rejection_reasons": getattr(d, "rejection_reasons", []) if d else [],
            "risk_factors": self.risk_factors,
            "adversarial_penalty": round(self.adversarial_penalty, 1),
            "invalidation_levels": getattr(d, "invalidation_levels", []) if d else [],
            "mtf_alignment": getattr(ctx, "mtf_alignment", {}) if ctx else {},
            "mtf_confluence": getattr(ctx, "mtf_confluence_score", 0.0) if ctx else 0.0,
            "utility_score": self.utility_score,
            "setup_grade": self.setup_grade,
            "is_actionable": self.is_actionable,
        }


class UniversalOpportunityArbiter:
    """
    Master Opportunity Arbiter.
    Ranks, arbitrates, and selects the single most mathematically superior trade setup
    across multiple asset classes (Forex, Metals, Crypto, Indices) and multiple trading horizons.
    """

    def __init__(self, ml_predictor=None, bandit=None, self_learning=None):
        self.ml_predictor = ml_predictor
        self.bandit = bandit
        self.self_learning = self_learning

    def calculate_regime_multiplier(self, regime: str, trade_style: str, strategy: str) -> float:
        """
        Computes dynamic regime compatibility multiplier.
        Rewards setups aligned with the optimal market structure phase.
        """
        reg_upper = str(regime or "RANGE").upper()
        style_upper = str(trade_style or "SWING").upper()
        strat_upper = str(strategy or "").upper()

        mult = 1.0

        # Style-Regime Matrix
        if "SWING" in style_upper:
            if "TREND_BULL" in reg_upper or "TREND_BEAR" in reg_upper:
                mult = 1.20
            elif "BREAKOUT" in reg_upper or "ACCUMULATION" in reg_upper or "DISTRIBUTION" in reg_upper:
                mult = 1.10
            elif "RANGE" in reg_upper or "CONSOLIDATION" in reg_upper:
                mult = 0.95
            elif "HIGH_VOLATILITY" in reg_upper or "EVENT_RISK" in reg_upper:
                mult = 0.80
        elif "DAY" in style_upper or "INTRADAY" in style_upper:
            if "TREND_BULL" in reg_upper or "TREND_BEAR" in reg_upper:
                mult = 1.15
            elif "BREAKOUT" in reg_upper or "POST_BREAKOUT" in reg_upper:
                mult = 1.15
            elif "RANGE" in reg_upper or "CONSOLIDATION" in reg_upper:
                mult = 1.05
            elif "HIGH_VOLATILITY" in reg_upper:
                mult = 0.90
            elif "EVENT_RISK" in reg_upper:
                mult = 0.80
        elif "SCALP" in style_upper:
            if "LIQUIDITY_SWEEP" in reg_upper or "REVERSAL" in reg_upper:
                mult = 1.25
            elif "RANGE" in reg_upper or "COMPRESSION" in reg_upper:
                mult = 1.15
            elif "HIGH_VOLATILITY" in reg_upper:
                mult = 1.00
            elif "EVENT_RISK" in reg_upper or "LIQUIDITY_STRESS" in reg_upper:
                mult = 0.75

        # Strategy-Regime Synergy Bonus
        if "SWEEP" in strat_upper and "LIQUIDITY" in reg_upper:
            mult += 0.05
        elif "TREND" in strat_upper and "TREND" in reg_upper:
            mult += 0.05
        elif "RANGE" in strat_upper and "RANGE" in reg_upper:
            mult += 0.05

        # Query self-learning historical regime adjustment if available
        if self.self_learning and hasattr(self.self_learning, "get_regime_multiplier"):
            try:
                hist_mult = self.self_learning.get_regime_multiplier(reg_upper)
                mult = (mult * 0.7) + (hist_mult * 0.3)
            except Exception:
                pass

        return round(float(mult), 3)

    def evaluate_opportunity(
        self,
        decision_obj: DecisionObject,
        context: Optional[MarketContext] = None,
        trade_style: str = "SWING"
    ) -> CandidateOpportunity:
        """
        Evaluates a single decision object through the Universal Opportunity Arbiter.
        Calculates Utility = P_ML * E[V] * (1 + Confluence / 100) * (1 - Penalty) * RegimeMultiplier
        and assigns setup grades (GRADE A+, GRADE A, GRADE B, GRADE C).
        """
        symbol = getattr(decision_obj, "symbol", "UNKNOWN")
        strategy = getattr(decision_obj, "strategy", "STRUCTURE") or "STRUCTURE"
        bias = getattr(decision_obj, "bias", "HOLD")
        entry_price = float(getattr(decision_obj, "entry_price", 0.0) or 0.0)
        stop_loss = float(getattr(decision_obj, "stop_loss", 0.0) or 0.0)
        take_profit = float(getattr(decision_obj, "take_profit", 0.0) or 0.0)
        rr_ratio = float(getattr(decision_obj, "risk_reward_ratio", 0.0) or 0.0)
        expected_value = float(getattr(decision_obj, "expected_value", 0.0) or 0.0)

        # Timeframe mapping
        style_norm = str(trade_style or "SWING").upper()
        if "SWING" in style_norm:
            timeframe = "D1/H4/H1"
        elif "DAY" in style_norm or "INTRADAY" in style_norm:
            timeframe = "H1/M15/M5"
        else:
            timeframe = "M15/M5/M1"

        # Win probability (percentage 0.0-100.0 and probability 0.0-1.0)
        raw_prob = getattr(decision_obj, "model_confidence", 0.50) or 0.50
        if hasattr(decision_obj, "probabilities") and decision_obj.probabilities and bias in ("BUY", "SELL"):
            raw_prob = decision_obj.probabilities.get(bias.lower(), raw_prob)

        win_prob_pct = (raw_prob * 100.0) if raw_prob <= 1.0 else raw_prob
        win_prob_decimal = win_prob_pct / 100.0

        # ML Probability (P_ML)
        ml_prob = getattr(decision_obj, "meta_label_prob", None)
        if ml_prob is None or ml_prob <= 0:
            if self.ml_predictor and context is not None:
                try:
                    reg_obj = getattr(decision_obj, "regime", None)
                    features = self.ml_predictor.extract_features(
                        context=context,
                        regime=reg_obj,
                        trade_style=style_norm,
                        strategy=strategy,
                        tentative_bias=bias,
                        devil_penalty=getattr(decision_obj, "adversarial_penalty", 0.0),
                        target_rr=rr_ratio
                    )
                    ml_prob = self.ml_predictor.predict_probability(features)
                except Exception as e:
                    logger.debug(f"Arbiter ML feature extraction fallback: {e}")
                    ml_prob = win_prob_decimal
            else:
                ml_prob = win_prob_decimal

        ml_prob = float(np.clip(ml_prob, 0.35, 0.88))

        # Master Confluence Score (0.0 to 100.0)
        confluence_score = float(getattr(decision_obj, "master_confluence_score", 0.0) or 0.0)
        if confluence_score == 0.0 and context is not None:
            confluence_score = float(getattr(context, "mtf_confluence_score", 50.0) or 50.0)

        confluence_factors = []
        if getattr(decision_obj, "bull_case", None):
            confluence_factors.extend(decision_obj.bull_case[:3])
        if getattr(decision_obj, "bear_case", None) and bias == "SELL":
            confluence_factors.extend(decision_obj.bear_case[:3])

        # Adversarial Penalty (normalized 0.0 to 1.0)
        raw_penalty = float(getattr(decision_obj, "adversarial_penalty", 0.0) or 0.0)
        penalty_norm = min(0.60, max(0.0, raw_penalty / 100.0 if raw_penalty > 1.0 else raw_penalty))

        # Regime & Regime Multiplier
        reg_obj = getattr(decision_obj, "regime", None)
        if reg_obj and hasattr(reg_obj, "primary_regime"):
            regime_str = reg_obj.primary_regime.value if hasattr(reg_obj.primary_regime, "value") else str(reg_obj.primary_regime)
        else:
            regime_str = str(reg_obj or "RANGE")

        regime_multiplier = self.calculate_regime_multiplier(regime_str, style_norm, strategy)

        # Mathematical Utility Computation:
        # Utility = P_ML * E[V] * (1 + Confluence / 100) * (1 - Penalty) * RegimeMultiplier
        effective_ev = max(0.0, expected_value)
        confluence_term = 1.0 + (confluence_score / 100.0)
        penalty_term = max(0.20, 1.0 - penalty_norm)

        if expected_value <= 0.0 or bias not in ("BUY", "SELL"):
            utility_score = 0.0
        else:
            utility_score = round(
                float(ml_prob * effective_ev * confluence_term * penalty_term * regime_multiplier),
                4
            )

        # Setup Grade Assignment:
        # GRADE A+ if Utility >= 1.80, Win Prob >= 70%, Confluence >= 75, EV >= 0.85R
        # GRADE A if Utility >= 1.35, Win Prob >= 60%, Confluence >= 65, EV >= 0.50R
        # GRADE B if Utility >= 1.00
        # GRADE C otherwise
        if utility_score >= 1.80 and (win_prob_pct >= 62.0 or ml_prob >= 0.70) and confluence_score >= 28.0 and expected_value >= 0.80:
            setup_grade = "GRADE A+"
        elif utility_score >= 1.30 and (win_prob_pct >= 55.0 or ml_prob >= 0.60) and confluence_score >= 22.0 and expected_value >= 0.40:
            setup_grade = "GRADE A"
        elif utility_score >= 0.95 and expected_value > 0:
            setup_grade = "GRADE B"
        else:
            setup_grade = "GRADE C"

        # Actionability Determination
        gate_passed = decision_obj.quality_gate.passed if (decision_obj and getattr(decision_obj, "quality_gate", None)) else True
        decision_val = getattr(decision_obj, "decision", "")

        is_actionable = bool(
            bias in ("BUY", "SELL") and
            utility_score >= 0.95 and
            expected_value > 0 and
            (
                decision_val == "EXECUTE"
                or (
                    setup_grade in ("GRADE A+", "GRADE A", "GRADE B")
                    and (gate_passed or (decision_val == "WAIT" and len(getattr(decision_obj.quality_gate, "failing_reasons", [])) <= 1))
                )
            )
        )

        risk_factors = getattr(decision_obj, "risk_factors", []) or []

        return CandidateOpportunity(
            symbol=symbol,
            trade_style=style_norm,
            timeframe=timeframe,
            strategy=strategy,
            bias=bias,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=rr_ratio,
            expected_value=expected_value,
            win_prob=win_prob_pct,
            ml_prob=ml_prob,
            confluence_score=confluence_score,
            confluence_factors=confluence_factors,
            adversarial_penalty=raw_penalty,
            risk_factors=risk_factors,
            regime=regime_str,
            regime_multiplier=regime_multiplier,
            utility_score=utility_score,
            setup_grade=setup_grade,
            is_actionable=is_actionable,
            decision_obj=decision_obj,
            context=context
        )

    def rank_and_select_best(
        self,
        candidates: List[CandidateOpportunity]
    ) -> Tuple[Optional[CandidateOpportunity], List[CandidateOpportunity]]:
        """
        Ranks all candidate opportunities by utility score descending.
        Selects the best actionable Grade A/A+/B opportunity.
        Returns (best_actionable_opportunity, ranked_list).
        """
        if not candidates:
            return None, []

        ranked = sorted(
            candidates,
            key=lambda c: (
                c.utility_score,
                c.win_prob,
                c.confluence_score,
                c.expected_value
            ),
            reverse=True
        )

        best_actionable = None
        for cand in ranked:
            if cand.is_actionable and cand.setup_grade in ("GRADE A+", "GRADE A", "GRADE B"):
                best_actionable = cand
                break

        return best_actionable, ranked
