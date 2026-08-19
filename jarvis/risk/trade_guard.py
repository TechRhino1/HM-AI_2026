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
        
        # Fix #5: Use correct attribute name 'max_spread_pips' (not 'max_spread')
        allowed_max_spread = getattr(symbol_data, 'max_spread_pips', max_spread_pips)
        
        # Fix #10: Unified Asian session definition — 01:00 to 04:59 UTC
        # (Consistent with orchestrator.py)
        current_hour = datetime.now(timezone.utc).hour
        is_asian_session = 1 <= current_hour < 5
        
        # Fix #5b: Use correct attribute for crypto detection
        is_crypto = getattr(symbol_data, 'is_crypto', False) or getattr(symbol_data, 'asset_class', '').upper() == 'CRYPTO' or 'BTC' in decision.symbol or 'ETH' in decision.symbol
        
        if is_crypto and is_asian_session:
            allowed_max_spread *= 2.0

        if current_spread_pips > allowed_max_spread:
            reasons.append(f"Spread ({current_spread_pips} pips) exceeds maximum threshold ({allowed_max_spread} pips).")

        # Inverted or invalid stop loss check
        if decision.bias == "BUY" and decision.stop_loss >= decision.entry_price:
            reasons.append("Invalid BUY order geometry: Stop loss is above entry price.")
        elif decision.bias == "SELL" and decision.stop_loss <= decision.entry_price:
            reasons.append("Invalid SELL order geometry: Stop loss is below entry price.")

        # Fix #11: TP geometry validation
        if decision.bias == "BUY" and decision.take_profit <= decision.entry_price:
            reasons.append("Invalid BUY order geometry: Take profit is below entry price.")
        elif decision.bias == "SELL" and decision.take_profit >= decision.entry_price:
            reasons.append("Invalid SELL order geometry: Take profit is above entry price.")

        is_passed = len(reasons) == 0
        return {
            "passed": is_passed,
            "reasons": reasons
        }
