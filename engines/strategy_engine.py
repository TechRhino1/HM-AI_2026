from typing import Dict, Any, List

class AdaptiveStrategyEngine:
    def select_strategy(
        self,
        regime_info: Dict[str, Any],
        structure_info: Dict[str, Any],
        volatility_info: Dict[str, Any],
        liquidity_info: Dict[str, Any],
        scalp_info: Dict[str, Any] = None,
        amd_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        regime = regime_info.get("regime", "UNCLEAR_INDETERMINATE")
        vol_state = volatility_info.get("state", "NORMAL")
        sweep = liquidity_info.get("sweep_detected", False)

        strategy_name = "DEFENSIVE_NO_TRADE"
        recommended_action = "HOLD"
        rationale = []

        if vol_state == "EXTREME" or regime == "HIGH_VOLATILITY_SHOCK":
            strategy_name = "DEFENSIVE_NO_TRADE"
            recommended_action = "HOLD"
            rationale.append("Market is experiencing extreme volatility shock. Capital defense active.")
            return {
                "strategy": strategy_name,
                "recommended_action": recommended_action,
                "rationale": rationale
            }

        # 1. Wyckoff / ICT AMD Institutional Phase Priority
        if amd_info and amd_info.get("phase") in ["MANIPULATION", "DISTRIBUTION", "RE_ACCUMULATION", "RE_DISTRIBUTION"]:
            phase = amd_info.get("phase")
            amd_action = amd_info.get("recommended_action")
            amd_strategy = amd_info.get("strategy")

            if phase == "MANIPULATION" and amd_action in ["BUY", "SELL"]:
                strategy_name = amd_strategy
                recommended_action = amd_action
                rationale.extend(amd_info.get("rationale", []))
                return {
                    "strategy": strategy_name,
                    "recommended_action": recommended_action,
                    "rationale": rationale,
                    "amd_phase": phase,
                    "target_pool": amd_info.get("target_pool")
                }

            elif phase == "DISTRIBUTION" and amd_action in ["BUY", "SELL"]:
                strategy_name = amd_strategy
                recommended_action = amd_action
                rationale.extend(amd_info.get("rationale", []))
                return {
                    "strategy": strategy_name,
                    "recommended_action": recommended_action,
                    "rationale": rationale,
                    "amd_phase": phase,
                    "target_pool": amd_info.get("target_pool")
                }

        # 2. High-Frequency Micro-Scalp Strategy Check (M5 EMA Pullback)
        if scalp_info and scalp_info.get("scalp_signal") and vol_state in ["NORMAL", "LOW"]:
            recommended_action = scalp_info.get("action", "HOLD")
            strategy_name = f"SCALPING_MICRO_MOMENTUM_{recommended_action}"
            rationale.append(f"M5 micro-EMA pullback scalping trigger detected aligned with H1 structural trend.")

        # 3. Macro Trend Pullback Strategies
        elif regime in ["STRONG_TREND_BULLISH", "MODERATE_TREND_BULLISH"]:
            strategy_name = "TREND_PULLBACK_BULLISH"
            recommended_action = "BUY"
            rationale.append("Confirmed bullish trend regime. Entering on EMA pullback / demand mitigation.")

        elif regime in ["STRONG_TREND_BEARISH", "MODERATE_TREND_BEARISH"]:
            strategy_name = "TREND_PULLBACK_BEARISH"
            recommended_action = "SELL"
            rationale.append("Confirmed bearish trend regime. Entering on EMA pullback / supply mitigation.")

        # 4. Liquidity Sweep Reversal Strategy
        elif sweep or regime == "ACCUMULATION_DISTRIBUTION":
            strategy_name = "LIQUIDITY_SWEEP_REVERSAL"
            recommended_action = "BUY" if liquidity_info.get("sweep_type") == "BULLISH_SWEEP" else "SELL"
            rationale.append("Liquidity sweep of key swing point detected with rapid institutional rejection.")

        # 5. Breakout Expansion Strategy
        elif "BREAKOUT_EXPANSION" in regime:
            recommended_action = "SELL" if ("BEARISH" in regime or structure_info.get("bos_type") == "BEARISH") else "BUY"
            strategy_name = f"BREAKOUT_EXPANSION_{recommended_action}"
            rationale.append(f"Structural Breakout Expansion ({recommended_action}) confirmed. Strategy targeting break-and-retest impulse.")

        # 6. Accumulation Range Mean Reversion Strategy
        elif regime in ["RANGE_BOUND", "CONSOLIDATION_COMPRESSION"]:
            if amd_info and amd_info.get("strategy") in ["ACCUMULATION_DEMAND_BOUNCE", "ACCUMULATION_SUPPLY_FADE"]:
                strategy_name = amd_info.get("strategy")
                recommended_action = amd_info.get("recommended_action")
                rationale.extend(amd_info.get("rationale", []))
            elif structure_info.get("demand_zone") and structure_info.get("recent_swing_low"):
                strategy_name = "RANGE_MEAN_REVERSION"
                recommended_action = "BUY" if structure_info.get("bias") == "BULLISH" else "SELL"
                rationale.append("Range-bound market. Strategy targeting mean reversion between boundaries.")
            else:
                strategy_name = "ACCUMULATION_WAIT_FOR_MANIPULATION"
                recommended_action = "HOLD"
                rationale.append("Range compression active. Holding for Judas Swing / Manipulation trigger.")

        else:
            strategy_name = "DEFENSIVE_NO_TRADE"
            recommended_action = "HOLD"
            rationale.append("Market regime is consolidating without clean statistical edge.")

        return {
            "strategy": strategy_name,
            "recommended_action": recommended_action,
            "rationale": rationale,
            "amd_phase": amd_info.get("phase", "ACCUMULATION") if isinstance(amd_info, dict) else "ACCUMULATION",
            "target_pool": amd_info.get("target_pool", 0.0) if isinstance(amd_info, dict) else 0.0
        }
