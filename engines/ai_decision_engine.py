from typing import Dict, Any, List, Optional
from engines.self_learning_engine import SelfLearningEngine
from engines.ml_optimizer_engine import MachineLearningOptimizerEngine

class AIDecisionEngine:
    def __init__(self, min_trade_score: float = 75.0, high_risk_trade_score: float = 85.0, learning_engine: SelfLearningEngine = None, logger: Any = None):
        self.min_trade_score = min_trade_score
        self.high_risk_trade_score = high_risk_trade_score
        self.learning_engine = learning_engine or SelfLearningEngine()
        self.ml_optimizer = MachineLearningOptimizerEngine(logger=logger)
        self.logger = logger

    def evaluate_trade_opportunity(
        self,
        symbol: str,
        structure: Dict[str, Any],
        trend: Dict[str, Any],
        volatility: Dict[str, Any],
        liquidity: Dict[str, Any],
        news: Dict[str, Any],
        strategy: Dict[str, Any],
        sl_tp: Dict[str, Any],
        regime: Dict[str, Any] = None,
        orderflow: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        reasons = []
        reasons_not_to_trade = []

        score_structure = 0.0
        score_trend = 0.0
        score_mtf = 0.0
        score_volatility = 0.0
        score_liquidity = 0.0
        score_news = 0.0
        score_rr = 0.0

        # 1. Market Structure & Order Block Confluence (25 pts)
        bias = structure.get("bias", "NEUTRAL")
        regime_str = regime.get("regime", "NEUTRAL") if isinstance(regime, dict) else str(regime or "")

        if bias == "NEUTRAL":
            if "BULLISH" in regime_str:
                bias = "BULLISH"
            elif "BEARISH" in regime_str:
                bias = "BEARISH"

        if bias != "NEUTRAL":
            score_structure += 15.0
            reasons.append(f"Confirmed structural trend bias: {bias}.")
        if structure.get("bos"):
            score_structure += 10.0
            reasons.append("Break of Structure (BOS) confirms institutional order flow.")
        elif structure.get("choch"):
            score_structure += 8.0
            reasons.append("Change of Character (CHoCH) signals early trend reversal.")

        # 2. Trend Momentum & RSI Filter (15 pts)
        trend_score = trend.get("trend_score", 0)
        rsi = trend.get("rsi", 50.0)
        if abs(trend_score) >= 55:
            score_trend += 15.0
            reasons.append(f"Strong trend momentum (Score: {trend_score}, RSI: {rsi:.1f}).")
        elif abs(trend_score) >= 25:
            score_trend += 10.0

        # 3. Multi-Timeframe & Regime Confluence (20 pts)
        recommended = strategy.get("recommended_action", "HOLD")
        regime_val = regime.get("regime", "NEUTRAL") if isinstance(regime, dict) else str(regime or "")
        regime_is_bullish = "BULLISH" in regime_val or bias == "BULLISH"
        regime_is_bearish = "BEARISH" in regime_val or bias == "BEARISH"

        is_aligned = (recommended == "BUY" and regime_is_bullish) or (recommended == "SELL" and regime_is_bearish)
        if is_aligned:
            score_mtf += 20.0
            reasons.append(f"Regime and trend alignment confirmed ({regime_val}).")
        else:
            reasons_not_to_trade.append("Lower timeframe setup conflicts with macro structural context.")

        # 5. Anti-Countertrend Directional Lock Guard (CRITICAL SAFETY FILTER)
        trend_score = trend.get("trend_score", 0)
        close_price = trend.get("close", 0.0)
        ema_fast = trend.get("ema_fast", 0.0)

        if recommended == "SELL":
            if trend_score > 0 or (close_price > 0 and close_price > ema_fast):
                reasons_not_to_trade.append("FORBIDDEN: Cannot execute SELL order while price is in an UPWARD trend above EMA fast.")
            elif close_price > 0 and ema_fast > 0 and (close_price < ema_fast * 0.992):
                reasons_not_to_trade.append("FORBIDDEN: Overextended SELL entry (>0.8% below EMA fast). Waiting for pullback to EMA resistance.")
        elif recommended == "BUY":
            if trend_score < 0 or (close_price > 0 and close_price < ema_fast):
                reasons_not_to_trade.append("FORBIDDEN: Cannot execute BUY order while price is in a DOWNWARD trend below EMA fast.")
            elif close_price > 0 and ema_fast > 0 and (close_price > ema_fast * 1.008):
                reasons_not_to_trade.append("FORBIDDEN: Overextended BUY entry (>0.8% above EMA fast). Waiting for pullback to EMA support.")

        # 6. Volatility & Spread Guard (10 pts)
        vol_state = volatility.get("state", "NORMAL")
        if vol_state in ["NORMAL", "HIGH"]:
            score_volatility += 10.0
            reasons.append(f"Optimal market volatility ({vol_state}).")
        elif vol_state == "EXTREME":
            score_volatility = 0.0
            reasons_not_to_trade.append("Extreme volatility shock in progress.")
        elif volatility.get("is_excessive_spread"):
            score_volatility = 0.0
            reasons_not_to_trade.append(f"Live spread ({volatility.get('current_spread_pips')} pips) exceeds maximum allowed.")

        # 5. Liquidity & Volume Order Flow Imbalance Mitigation (10 pts)
        if orderflow and orderflow.get("delta_imbalance") != "NEUTRAL":
            imbalance = orderflow.get("delta_imbalance", "")
            if (recommended == "BUY" and "BULLISH" in imbalance) or (recommended == "SELL" and "BEARISH" in imbalance):
                score_liquidity += 10.0
                reasons.append(f"Institutional Order Flow Imbalance ({imbalance}) confirms entry direction.")
            else:
                score_liquidity += 3.0
                reasons_not_to_trade.append(f"Order Flow Imbalance ({imbalance}) conflicts with trade direction.")
        elif liquidity.get("sweep_detected"):
            score_liquidity += 10.0
            reasons.append(f"Liquidity sweep ({liquidity.get('sweep_type')}) provides high-probability entry.")
        elif liquidity.get("fvg_detected") and liquidity.get("price_in_fvg_zone"):
            score_liquidity += 8.0
            reasons.append(f"Fair Value Gap ({liquidity.get('fvg_type')}) imbalance mitigation confirmed.")
        else:
            score_liquidity += 5.0

        # 6. Macro News Intelligence (10 pts)
        news_status = news.get("news_status", "NEWS_RISK_LOW")
        if news_status == "NEWS_RISK_LOW":
            score_news += 10.0
            reasons.append("No high-impact economic news within buffer window.")
        elif news_status == "NEWS_DATA_UNAVAILABLE":
            score_news += 5.0
            reasons_not_to_trade.append("News feed offline (NEWS_DATA_UNAVAILABLE); requiring elevated score threshold.")
        else:
            score_news = 0.0
            reasons_not_to_trade.extend(news.get("reasons_not_to_trade", []))

        # 7. Risk-to-Reward Ratio (10 pts)
        rr = sl_tp.get("rr_ratio", 1.0)
        if rr >= 2.0:
            score_rr += 10.0
            reasons.append(f"High Risk-to-Reward Ratio (1:{rr:.2f}).")
        elif rr >= 1.5:
            score_rr += 7.0
        else:
            score_rr = 2.0
            reasons_not_to_trade.append(f"Inadequate Risk-to-Reward ratio (1:{rr:.2f} < 1:1.5).")

        # 8. Professional Timing & Session Filter
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        current_hour = now_utc.hour

        is_prime_session = (7 <= current_hour <= 21)
        if is_prime_session:
            score_mtf += 5.0
            reasons.append(f"Institutional Prime Volume Session ({current_hour:02d}:00 UTC).")

        # 9. Self-Learning Reinforcement Score Adjustment
        strategy_name = strategy.get("strategy", "NEUTRAL")
        learned_adj = self.learning_engine.get_strategy_score_adjustment(regime_val, strategy_name)
        if learned_adj != 0.0:
            reasons.append(f"Self-Learning Reinforcement adjustment applied ({learned_adj:+.1f} pts for {strategy_name}).")

        # 10. Wyckoff / ICT AMD Institutional Confluence Bonus
        score_amd = 0.0
        if "WYCKOFF" in strategy_name or "MANIPULATION" in strategy_name:
            score_amd = 8.0
            reasons.append("Institutional Wyckoff Manipulation / Spring-Upthrust setup confirmed.")
        elif "AMD_DISTRIBUTION" in strategy_name:
            score_amd = 8.0
            reasons.append("Institutional AMD Distribution / True Expansion displacement confirmed.")

        total_trade_score = score_structure + score_trend + score_mtf + score_volatility + score_liquidity + score_news + score_rr + learned_adj + score_amd
        total_trade_score = round(min(max(total_trade_score, 0.0), 100.0), 1)

        # 10. Machine Learning Probability Classifier & Score Optimizer
        of_imb = orderflow.get("delta_imbalance", "NEUTRAL") if isinstance(orderflow, dict) else "NEUTRAL"
        ml_pred = self.ml_optimizer.predict_trade_probability(symbol, regime_val, strategy_name, total_trade_score, orderflow_imbalance=of_imb)
        ml_prob = ml_pred.get("ml_win_probability", 0.65)
        ml_opt_score = ml_pred.get("optimized_trade_score", total_trade_score)

        if ml_pred.get("ml_score_adjustment", 0) != 0:
            reasons.append(f"ML Classifier prediction ({ml_prob*100:.0f}% win prob) adjusted AI score ({ml_pred.get('ml_score_adjustment'):+.1f} pts).")

        base_thresh = self.min_trade_score  # Restored 75.0 / 100
        adaptive_threshold = self.learning_engine.get_adaptive_score_threshold(base_thresh)

        required_score = self.high_risk_trade_score if (news_status != "NEWS_RISK_LOW" or vol_state == "HIGH") else adaptive_threshold

        if ml_opt_score >= required_score and recommended in ["BUY", "SELL"] and not reasons_not_to_trade:
            decision = "APPROVED"
            if self.logger:
                self.logger.info(f"AI DECISION APPROVED [{symbol} {recommended}]: Score={ml_opt_score:.1f}/100 (Req={required_score:.1f} | ML Prob={ml_prob*100:.0f}%). Confluence: {', '.join(reasons[:3])}")
        else:
            decision = "REJECTED"
            if ml_opt_score < required_score:
                reasons_not_to_trade.append(f"ML Optimized trade score ({ml_opt_score}/100) below required threshold ({required_score}/100).")
            if self.logger:
                self.logger.info(f"AI DECISION REJECTED [{symbol} {recommended}]: Score={ml_opt_score:.1f}/100 (Req={required_score:.1f}). Reasons: {', '.join(reasons_not_to_trade[:2])}")

        return {
            "symbol": symbol,
            "decision": decision,
            "action": recommended if decision == "APPROVED" else "HOLD",
            "trade_score": ml_opt_score,
            "ml_win_probability": ml_prob,
            "ml_recommendation": ml_pred.get("ml_recommendation", "STANDARD"),
            "strategy": strategy_name,
            "reasons": reasons,
            "reasons_not_to_trade": reasons_not_to_trade,
            "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S")
        }
