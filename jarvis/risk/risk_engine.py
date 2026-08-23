"""
JARVIS AI 3.0 — Master Risk Management Engine.
Maintains complete independence from the AI. The AI recommends — the Risk Engine authorizes.
"""
import threading
from typing import Dict, List, Any, Optional
from jarvis.data.schemas import DecisionObject, AccountSnapshot, PositionSnapshot
from jarvis.risk.position_sizing import PositionSizer
from jarvis.risk.drawdown import DrawdownGuard
from jarvis.risk.exposure import ExposureManager
from jarvis.risk.circuit_breaker import CircuitBreaker
from jarvis.risk.trade_guard import TradeGuard
from jarvis.market.correlations import DynamicCorrelationEngine

class RiskEngine:
    def __init__(
        self,
        max_daily_loss_pct: float = 4.0,
        max_drawdown_pct: float = 10.0,
        max_open_positions: int = 3,
        max_symbol_positions: int = 1,
        max_risk_per_trade_pct: float = 0.5,
        is_backtest: bool = False
    ):
        self._lock = threading.RLock()
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.drawdown_guard = DrawdownGuard(
            max_daily_loss_pct, max_drawdown_pct,
            db_path="" if is_backtest else "jarvis_drawdown_state.db"
        )
        self.exposure_manager = ExposureManager(max_open_positions, max_symbol_positions)
        self.circuit_breaker = CircuitBreaker(
            db_path="" if is_backtest else "jarvis_circuit_state.db"
        )
        self.position_sizer = PositionSizer()
        self.trade_guard = TradeGuard()
        self.correlation_engine = DynamicCorrelationEngine()

    def authorize_execution(
        self,
        decision: DecisionObject,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        symbol_info: Dict[str, Any],
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes full authorization pipeline. Returns whether execution is approved and calculated lot size.
        """
        if "spread_pips" in kwargs:
            current_spread_pips = float(kwargs["spread_pips"])
        with self._lock:
            rejection_reasons = []

            # 1. Circuit Breaker status (Global + Per-Symbol / Per-Regime)
            cb = self.circuit_breaker.check_status()
            if cb.get("active"):
                rejection_reasons.append(f"Circuit Breaker active: {cb.get('reason')} (Cooldown: {cb.get('remaining_cooldown_sec', 0)}s)")
            if self.circuit_breaker.is_symbol_paused(decision.symbol):
                rejection_reasons.append(f"Symbol {decision.symbol} is temporarily paused due to recent consecutive losses.")
            if decision.regime and hasattr(decision.regime, "primary_regime") and self.circuit_breaker.is_regime_paused(decision.regime.primary_regime.value):
                rejection_reasons.append(f"Regime {decision.regime.primary_regime.value} is temporarily paused due to consecutive losses.")

            # 2. Drawdown & Daily Loss limits
            dd = self.drawdown_guard.check_limits(account.equity, account.balance)
            if not dd.get("passed"):
                rejection_reasons.extend(dd.get("breaches", []))

            # 3. Portfolio Exposure & Margin limits
            exp = self.exposure_manager.check_exposure(decision.symbol, positions, account)
            if not exp.get("passed"):
                rejection_reasons.extend(exp.get("breaches", []))

            # 4. Pre-Execution Geometry & Gate validation
            guard = self.trade_guard.validate_pre_execution(
                decision, account, positions, max_allowed_spread_pips, current_spread_pips
            )
            if not guard.get("passed"):
                rejection_reasons.extend(guard.get("reasons", []))

            # 5. Correlation check
            for pos in positions:
                corr = self.correlation_engine.get_correlation(decision.symbol, pos.symbol)
                if corr > 0.70:
                    rejection_reasons.append(f"Correlation too high ({corr:.2f}) with existing position {pos.symbol}.")

            if rejection_reasons:
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": rejection_reasons
                }

            # 6. Position Sizing with Conviction & Evidence Scaling (B4 / P3 WIRING)
            sample_size = getattr(decision, "pattern_sample_size", 0)
            lots = self.position_sizer.calculate_lot_size(
                account_balance=account.equity,
                entry_price=decision.entry_price,
                sl_price=decision.stop_loss,
                risk_pct=self.max_risk_per_trade_pct,
                symbol_info=symbol_info,
                invalidation_risk_coefficient=1.0 - (decision.adversarial_penalty / 60.0),
                model_confidence=decision.model_confidence,
                pattern_sample_size=sample_size
            )

            # Before returning authorized=True, double check circuit breaker and drawdown
            cb_final = self.circuit_breaker.check_status()
            if cb_final.get("active"):
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": [f"Circuit Breaker tripped during authorization: {cb_final.get('reason')}"]
                }
                
            dd_final = self.drawdown_guard.check_limits(account.equity, account.balance)
            if not dd_final.get("passed"):
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": dd_final.get("breaches", [])
                }

            return {
                "authorized": True,
                "lots": lots,
                "reasons": []
            }
