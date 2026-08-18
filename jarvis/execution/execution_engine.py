"""
JARVIS AI 3.0 — Master Execution Engine.
Orchestrates order dispatch, mode verification (LIVE/PAPER/DEMO), and execution logging.
"""
import logging
from typing import Dict, Any
from jarvis.data.schemas import DecisionObject, ExecutionMode
from jarvis.execution.mt5_client import MT5Client
from jarvis.application.state_manager import StateManager, GLOBAL_STATE

logger = logging.getLogger("JARVIS_ExecutionEngine")

class ExecutionEngine:
    def __init__(self, mt5_client: MT5Client, state_manager: StateManager = GLOBAL_STATE):
        self.mt5_client = mt5_client
        self.state_manager = state_manager

    def execute_decision(self, decision: DecisionObject, lots: float) -> Dict[str, Any]:
        """Dispatches authorized decision to MT5 or Paper Simulator."""
        if not decision.execution_authorized or lots <= 0:
            logger.warning(f"Execution rejected for {decision.symbol}: Not authorized or invalid lot size ({lots}).")
            return {"status": "BLOCKED", "reason": "Execution unauthorized"}

        if self.state_manager.is_safe_mode:
            logger.warning(f"Execution blocked for {decision.symbol}: SAFE MODE is ACTIVE.")
            return {"status": "BLOCKED", "reason": "Safe mode active"}

        mode = self.state_manager.execution_mode
        comment = f"J3_{decision.strategy[:6]}_{mode.value}"

        logger.info(f"DISPATCHING ORDER [{mode.value}]: {decision.bias} {lots} {decision.symbol} @ Entry={decision.entry_price} SL={decision.stop_loss} TP={decision.take_profit}")

        res = self.mt5_client.send_market_order(
            symbol=decision.symbol,
            order_type=decision.bias,
            volume=lots,
            sl_price=decision.stop_loss,
            tp_price=decision.take_profit,
            comment=comment
        )

        return res
