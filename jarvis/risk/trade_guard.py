"""
JARVIS AI 3.0 — Autonomous Trade Quality Guard.
Executes hard independent pre-flight checks before approving any trade for execution.
"""
from typing import Dict, List, Any
from datetime import datetime, timezone
from jarvis.data.schemas import DecisionObject, AccountSnapshot, PositionSnapshot
from jarvis.data.symbol_registry import resolve

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

        symbol_data = resolve(decision.symbol)
        
        # Use symbol-specific max spread if available, otherwise use default
        allowed_max_spread = getattr(symbol_data, 'max_spread', max_spread_pips)
        
        # Asian session check (approx 22:00 to 08:00 UTC)
        # We'll just do a simple check for hours 22, 23, 0-7
        current_hour = datetime.now(timezone.utc).hour
        is_asian_session = current_hour >= 22 or current_hour < 8
        
        is_crypto = getattr(symbol_data, 'type', '').lower() == 'crypto' or 'crypto' in getattr(symbol_data, 'tags', []) or 'BTC' in decision.symbol or 'ETH' in decision.symbol
        
        if is_crypto and is_asian_session:
            allowed_max_spread *= 2.0

        if current_spread_pips > allowed_max_spread:
            reasons.append(f"Spread ({current_spread_pips} pips) exceeds maximum threshold ({allowed_max_spread} pips).")

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
