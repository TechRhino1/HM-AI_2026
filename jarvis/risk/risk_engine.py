"""
JARVIS AI 3.0 — Master Risk Management Engine.
Maintains complete independence from the AI. The AI recommends — the Risk Engine authorizes.
"""
from typing import Dict, List, Any, Optional
from jarvis.data.schemas import DecisionObject, AccountSnapshot, PositionSnapshot
from jarvis.risk.position_sizing import PositionSizer
from jarvis.risk.drawdown import DrawdownGuard
from jarvis.risk.exposure import ExposureManager
from jarvis.risk.circuit_breaker import CircuitBreaker
from jarvis.risk.trade_guard import TradeGuard

class RiskEngine:
    def __init__(
        self,
        max_daily_loss_pct: float = 4.0,
        max_drawdown_pct: float = 10.0,
        max_open_positions: int = 3,
        max_symbol_positions: int = 1,
        max_risk_per_trade_pct: float = 0.5
    ):
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.drawdown_guard = DrawdownGuard(max_daily_loss_pct, max_drawdown_pct)
        self.exposure_manager = ExposureManager(max_open_positions, max_symbol_positions)
        self.circuit_breaker = CircuitBreaker()
        self.position_sizer = PositionSizer()
        self.trade_guard = TradeGuard()

    def authorize_execution(
        self,
        decision: DecisionObject,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        symbol_info: Dict[str, Any],
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0
    ) -> Dict[str, Any]:
        """
        Executes full authorization pipeline. Returns whether execution is approved and calculated lot size.
        """
        rejection_reasons = []

        # 1. Circuit Breaker status
        cb = self.circuit_breaker.check_status()
        if cb["active"]:
            rejection_reasons.append(f"Circuit Breaker active: {cb['reason']} (Cooldown: {cb['remaining_cooldown_sec']}s)")

        # 2. Drawdown & Daily Loss limits
        dd = self.drawdown_guard.check_limits(account.equity, account.balance)
        if not dd["passed"]:
            rejection_reasons.extend(dd["breaches"])

        # 3. Portfolio Exposure & Margin limits
        exp = self.exposure_manager.check_exposure(decision.symbol, positions, account)
        if not exp["passed"]:
            rejection_reasons.extend(exp["breaches"])

        # 4. Pre-Execution Geometry & Gate validation
        guard = self.trade_guard.validate_pre_execution(
            decision, account, positions, max_allowed_spread_pips, current_spread_pips
        )
        if not guard["passed"]:
            rejection_reasons.extend(guard["reasons"])

        if rejection_reasons:
            return {
                "authorized": False,
                "lots": 0.0,
                "reasons": rejection_reasons
            }

        # 5. Position Sizing
        lots = self.position_sizer.calculate_lot_size(
            account_balance=account.equity,
            entry_price=decision.entry_price,
            sl_price=decision.stop_loss,
            risk_pct=self.max_risk_per_trade_pct,
            symbol_info=symbol_info,
            invalidation_risk_coefficient=1.0 - (decision.adversarial_penalty / 60.0)
        )

        return {
            "authorized": True,
            "lots": lots,
            "reasons": []
        }
