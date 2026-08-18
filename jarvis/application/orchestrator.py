"""
JARVIS AI 3.0 — Master System Orchestrator.
Coordinates data feeds, multi-symbol radar scans, parallel analyst clusters, risk authorization, MT5 state synchronization, and execution.
"""
import time
import logging
import threading
from typing import Dict, List, Any, Optional

from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.application.event_bus import EventBus, GLOBAL_EVENT_BUS
from jarvis.market.data_feed import DataFeedEngine
from jarvis.market.market_context import MarketContextEngine
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.analysts.parallel_runner import ParallelAnalystCluster
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.risk.risk_engine import RiskEngine
from jarvis.execution.mt5_client import MT5Client
from jarvis.execution.state_synchronizer import MT5StateSynchronizer
from jarvis.execution.execution_engine import ExecutionEngine
from jarvis.execution.order_manager import OrderManager
from jarvis.learning.trade_memory import TradeMemory
from jarvis.data.schemas import ExecutionMode

logger = logging.getLogger("JARVIS_Orchestrator")

class JarvisOrchestrator:
    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        mode: str = "paper",
        magic_number: int = 888999
    ):
        self.symbols = symbols or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
        self.mode = mode.lower()

        self.state_manager = GLOBAL_STATE
        self.state_manager.set_execution_mode(ExecutionMode(self.mode.upper()))
        self.event_bus = GLOBAL_EVENT_BUS

        self.mt5_client = MT5Client(magic_number=magic_number, mode=self.mode)
        self.data_feed = DataFeedEngine(self.mt5_client)
        self.context_engine = MarketContextEngine()
        self.regime_classifier = MarketRegimeClassifier()
        self.analyst_cluster = ParallelAnalystCluster()
        self.decision_engine = DecisionEngine()
        self.risk_engine = RiskEngine()
        self.order_manager = OrderManager(self.mt5_client)
        self.execution_engine = ExecutionEngine(self.mt5_client, self.state_manager)
        self.trade_memory = TradeMemory()

        self.state_synchronizer = MT5StateSynchronizer(self.mt5_client, self.state_manager, self.event_bus)
        self._running = False
        self._main_thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the full JARVIS 3.0 engine and background workers."""
        if not self._running:
            self._running = True
            self.state_synchronizer.start()
            self._main_thread = threading.Thread(target=self._orchestration_loop, daemon=True, name="jarvis_orchestrator")
            self._main_thread.start()
            logger.info("JARVIS 3.0 Orchestrator started.")

    def stop(self):
        """Clean shutdown of all engine workers."""
        self._running = False
        self.state_synchronizer.stop()
        self.mt5_client.shutdown()
        logger.info("JARVIS 3.0 Orchestrator stopped.")

    def run_cycle_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """Executes a single end-to-end analytical and decision cycle for a target symbol."""
        # 1. Fetch Multi-Timeframe Data
        mtf_data = self.data_feed.fetch_multi_timeframe(symbol)
        
        # 2. Synthesize Multi-Timeframe Market Context
        context = self.context_engine.build_context(symbol, mtf_data)
        self.state_manager.update_market_context(symbol, context)

        # 3. Classify Market Regime
        regime = self.regime_classifier.classify_regime(context)

        # 4. Dispatch Parallel Analysts + Devil's Advocate
        tentative_bias = "BUY" if context.structure.bias == "BULLISH" else ("SELL" if context.structure.bias == "BEARISH" else "HOLD")
        analyst_reports, devil_report = self.analyst_cluster.run_all_parallel(context, regime, tentative_bias)

        # 5. Evaluate Decision with Expected Value & Quality Gate
        account = self.state_manager.account or self.mt5_client.get_account_snapshot()
        decision = self.decision_engine.evaluate(
            context, regime, analyst_reports, devil_report, account_balance=account.equity
        )
        self.state_manager.record_decision(symbol, decision)

        # 6. Risk Engine Independent Authorization & Sizing
        positions = self.state_manager.positions
        sym_info = {
            "trade_contract_size": 100 if "XAU" in symbol else 100000,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01
        }

        # Anti-Clustering Rule: Prevent stacking multiple simultaneous orders on same asset
        active_sym_positions = [
            p for p in positions if (p.symbol == symbol or (symbol == "XAUUSD" and "GOLD" in p.symbol))
        ]
        
        # Asian Pre-Market Blackout Rule (01:00 to 05:00 UTC)
        now_utc_hour = datetime.now(timezone.utc).hour
        is_asian_blackout = (1 <= now_utc_hour < 5)

        if active_sym_positions and decision.decision == "EXECUTE":
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "ANTI_CLUSTERING_GUARD: Active trade already open on this asset."}
        elif is_asian_blackout and decision.decision == "EXECUTE":
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "ASIAN_SESSION_BLACKOUT: Low liquidity chop protection active."}
        else:
            auth_res = self.risk_engine.authorize_execution(
                decision, account, positions, sym_info, current_spread_pips=context.volatility.current_spread_pips
            )

        # 7. Execute if authorized
        exec_res = None
        if auth_res.get("authorized") and decision.decision == "EXECUTE":
            decision.execution_authorized = True
            lots = auth_res.get("lots", 0.01)
            # Micro-lot cap on small accounts (< $250)
            if account.equity < 250.0:
                lots = 0.01
            exec_res = self.execution_engine.execute_decision(decision, lots)
            if exec_res and exec_res.get("status") == "FILLED":
                self.trade_memory.record_trade({
                    "ticket": exec_res.get("ticket"),
                    "symbol": symbol,
                    "type": decision.bias,
                    "entry": decision.entry_price,
                    "sl": decision.stop_loss,
                    "tp": decision.take_profit,
                    "lots": lots,
                    "regime": regime.primary_regime.value,
                    "strategy": decision.strategy,
                    "model_confidence": decision.model_confidence,
                    "adversarial_penalty": decision.adversarial_penalty,
                    "expected_value": decision.expected_value
                })

        return {
            "symbol": symbol,
            "decision": decision,
            "authorized": auth_res["authorized"],
            "execution": exec_res
        }

    def _orchestration_loop(self):
        """Continuous radar scan loop across configured symbols."""
        while self._running:
            radar_results = []
            for sym in self.symbols:
                try:
                    res = self.run_cycle_for_symbol(sym)
                    d = res["decision"]
                    radar_results.append({
                        "symbol": sym,
                        "action": d.bias if d.decision == "EXECUTE" else "WAIT",
                        "decision": d.decision,
                        "score": round(d.model_confidence * 100.0, 0),
                        "ev": d.expected_value,
                        "regime": d.regime.primary_regime.value,
                        "strategy": d.strategy
                    })
                except Exception as e:
                    logger.error(f"Orchestration error for {sym}: {e}", exc_info=True)

            self.state_manager.update_radar(radar_results)
            time.sleep(3.0)
