"""
JARVIS AI 3.0 — Autonomous Trade Quality Guard.
Executes hard independent pre-flight checks before approving any trade for execution.
"""
from typing import Dict, List, Any
from jarvis.data.schemas import DecisionObject, AccountSnapshot, PositionSnapshot

class TradeGuard:
    @staticmethod
    def validate_pre_execution(
        decision: DecisionObject,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        max_spread_pips: float = 35.0,
        current_spread_pips: float = 2.0
    ) -> Dict[str, Any]:
        reasons = []

        if decision.decision != "EXECUTE":
            reasons.append(f"AI Decision status is '{decision.decision}' (Requires 'EXECUTE').")

        if not account.trade_allowed:
            reasons.append("Account trade permissions disabled by broker.")

        if current_spread_pips > max_spread_pips:
            reasons.append(f"Spread ({current_spread_pips} pips) exceeds maximum threshold ({max_spread_pips} pips).")

        if decision.expected_value <= 0:
            reasons.append(f"Expected value (${decision.expected_value:.2f}) is non-positive after trading costs.")

        if decision.risk_reward_ratio < 1.5:
            reasons.append(f"Risk-to-Reward ratio (1:{decision.risk_reward_ratio:.2f}) below minimum 1:1.50.")

        # Inverted or invalid stop loss check
        if decision.bias == "BUY" and decision.stop_loss >= decision.entry_price:
            reasons.append("Invalid BUY order geometry: Stop loss is above entry price.")
        elif decision.bias == "SELL" and decision.stop_loss <= decision.entry_price:
            reasons.append("Invalid SELL order geometry: Stop loss is below entry price.")

        is_passed = len(reasons) == 0
        return {
            "passed": is_passed,
            "reasons": reasons
        }
