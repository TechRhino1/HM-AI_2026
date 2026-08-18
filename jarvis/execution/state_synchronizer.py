"""
JARVIS AI 3.0 — Strict MT5 State Synchronization & Reconciliation Engine.
Guarantees real-time consistency between broker terminal state and internal application memory.
"""
import time
import logging
import threading
from typing import Dict, List, Set, Any

from jarvis.data.schemas import AccountSnapshot, PositionSnapshot
from jarvis.execution.mt5_client import MT5Client
from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.application.event_bus import EventBus, GLOBAL_EVENT_BUS

logger = logging.getLogger("JARVIS_StateSynchronizer")

class MT5StateSynchronizer:
    """Active background synchronizer and reconciler for MT5 broker states."""
    
    def __init__(
        self,
        mt5_client: MT5Client,
        state_manager: StateManager = GLOBAL_STATE,
        event_bus: EventBus = GLOBAL_EVENT_BUS,
        sync_interval_sec: float = 1.0
    ):
        self.mt5_client = mt5_client
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.sync_interval_sec = sync_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_position_tickets: Set[int] = set()

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._sync_loop, daemon=True, name="mt5_state_sync")
            self._thread.start()
            logger.info("MT5 State Synchronizer background worker started.")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            logger.info("MT5 State Synchronizer background worker stopped.")

    def sync_once(self) -> Dict[str, Any]:
        """Performs a single atomic synchronization pass and returns reconciliation report."""
        try:
            account = self.mt5_client.get_account_snapshot()
            positions = self.mt5_client.get_open_positions()

            self.state_manager.update_account(account)
            self.state_manager.update_positions(positions)

            # Reconcile closed/opened positions
            current_tickets = set(p.ticket for p in positions)
            
            # Detect newly closed positions
            closed_tickets = self._last_position_tickets - current_tickets
            for t in closed_tickets:
                logger.info(f"State Reconciliation: Position #{t} closed on broker terminal.")
                self.event_bus.publish_sync("POSITION_CLOSED", {"ticket": t})

            # Detect newly opened positions
            opened_tickets = current_tickets - self._last_position_tickets
            for t in opened_tickets:
                logger.info(f"State Reconciliation: Position #{t} discovered on broker terminal.")
                self.event_bus.publish_sync("POSITION_OPENED", {"ticket": t})

            self._last_position_tickets = current_tickets

            status = "CONNECTED" if (self.mt5_client.is_connected and account.login > 0) else "DISCONNECTED"
            self.state_manager.update_service_health("MT5", status)
            self.state_manager.update_service_health("STATE_SYNC", "ONLINE")

            return {
                "success": True,
                "login": account.login,
                "equity": account.equity,
                "open_positions": len(positions),
                "closed_detected": len(closed_tickets),
                "opened_detected": len(opened_tickets)
            }
        except Exception as e:
            logger.error(f"State Synchronization error: {e}", exc_info=True)
            self.state_manager.update_service_health("STATE_SYNC", "DEGRADED")
            return {"success": False, "error": str(e)}

    def _sync_loop(self):
        while self._running:
            self.sync_once()
            time.sleep(self.sync_interval_sec)
