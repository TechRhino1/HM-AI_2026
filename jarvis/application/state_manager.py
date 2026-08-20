"""
JARVIS AI 3.0 — Central State Manager.
Thread-safe, atomic centralized state repository for live telemetry, account records, decisions, and system health.
"""
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from jarvis.data.schemas import (
    AccountSnapshot,
    PositionSnapshot,
    MarketContext,
    DecisionObject,
    ExecutionMode
)

class StateManager:
    """Central synchronized in-memory state repository."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self._rw_lock = threading.RLock()
        self.execution_mode: ExecutionMode = ExecutionMode.PAPER
        self.is_safe_mode: bool = False
        self.is_running: bool = True
        
        self.account: Optional[AccountSnapshot] = None
        self.positions: List[PositionSnapshot] = []
        self.market_contexts: Dict[str, MarketContext] = {}
        self.latest_decisions: Dict[str, DecisionObject] = {}
        self.radar_opportunities: List[Dict[str, Any]] = []
        self.services_health: Dict[str, str] = {
            "MT5": "DISCONNECTED",
            "DATA_FEED": "OFFLINE",
            "REGIME_ENGINE": "READY",
            "ANALYST_CLUSTER": "READY",
            "DEVIL_ADVOCATE": "READY",
            "RISK_ENGINE": "ACTIVE",
            "STATE_SYNC": "ONLINE",
            "TELEMETRY_API": "ONLINE"
        }
        self.logs: List[Dict[str, Any]] = []
        self.last_update = datetime.now(timezone.utc)

    def set_execution_mode(self, mode: ExecutionMode):
        with self._rw_lock:
            self.execution_mode = mode

    def toggle_safe_mode(self) -> bool:
        with self._rw_lock:
            self.is_safe_mode = not self.is_safe_mode
            return self.is_safe_mode

    def update_account(self, account: AccountSnapshot):
        with self._rw_lock:
            self.account = account
            self.last_update = datetime.now(timezone.utc)

    def update_positions(self, positions: List[PositionSnapshot]):
        with self._rw_lock:
            self.positions = positions
            self.last_update = datetime.now(timezone.utc)

    def sync_broker_state(self, account: Optional[AccountSnapshot], positions: List[PositionSnapshot]):
        with self._rw_lock:
            if account:
                self.account = account
            self.positions = positions
            self.last_update = datetime.now(timezone.utc)

    def update_market_context(self, symbol: str, context: MarketContext):
        with self._rw_lock:
            self.market_contexts[symbol] = context
            self.last_update = datetime.now(timezone.utc)

    def record_decision(self, symbol: str, decision: DecisionObject):
        with self._rw_lock:
            self.latest_decisions[symbol] = decision
            self.last_update = datetime.now(timezone.utc)

    def update_radar(self, opportunities: List[Dict[str, Any]]):
        with self._rw_lock:
            self.radar_opportunities = opportunities
            self.last_update = datetime.now(timezone.utc)

    def update_service_health(self, service: str, status: str):
        with self._rw_lock:
            self.services_health[service] = status

    def append_log(self, level: str, message: str, source: str = "SYSTEM"):
        with self._rw_lock:
            entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "source": source,
                "message": message
            }
            self.logs.append(entry)
            if len(self.logs) > 500:
                self.logs.pop(0)

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Returns an atomic serialization of current system state for API/UI dashboards."""
        with self._rw_lock:
            acc_dict = self.account.to_dict() if (self.account and hasattr(self.account, "to_dict")) else (self.account.__dict__ if self.account else None)
            pos_list = [p.to_dict() if hasattr(p, "to_dict") else p.__dict__ for p in self.positions]
            dec_dict = {}
            for k, v in self.latest_decisions.items():
                dec_dict[k] = v.to_dict() if hasattr(v, "to_dict") else v.__dict__

            return {
                "execution_mode": self.execution_mode.value,
                "safe_mode": self.is_safe_mode,
                "is_running": self.is_running,
                "account": acc_dict,
                "positions_count": len(self.positions),
                "positions": pos_list,
                "services": self.services_health,
                "radar_opportunities": self.radar_opportunities,
                "latest_decisions": dec_dict,
                "recent_logs": self.logs[-50:],
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }

GLOBAL_STATE = StateManager()
