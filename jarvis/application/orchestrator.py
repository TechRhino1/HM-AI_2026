"""
JARVIS AI 3.0 — Master System Orchestrator.
Coordinates data feeds, multi-symbol radar scans, parallel analyst clusters, risk authorization, MT5 state synchronization, and execution.
"""
import time
import logging
import threading
from datetime import datetime, timezone
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
from jarvis.execution.position_monitor import PositionMonitorEngine
from jarvis.learning.trade_memory import TradeMemory
from jarvis.learning.online_ml_predictor import OnlineMLPredictor
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.data.schemas import ExecutionMode
from jarvis.data.symbol_registry import is_crypto
from jarvis.risk.circuit_breaker import CircuitBreaker
from jarvis.risk.drawdown import DrawdownGuard
from jarvis.market.sessions import SessionEngine

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

        self.ml_predictor = OnlineMLPredictor()
        self.strategy_bandit = StrategyBandit()
        self.circuit_breaker = CircuitBreaker()
        self.drawdown_guard = DrawdownGuard()
        self._pending_features = {}

        # ── In-process execution guard ─────────────────────────────────────
        # Tracks symbols currently being executed to prevent race-condition
        # multi-fires before MT5StateSynchronizer (1 s lag) can catch up.
        self._execution_in_progress: set = set()
        self._execution_lock = threading.Lock()
        # Per-symbol last-execution timestamp for 10-min same-symbol cooldown
        self._last_execution_time: Dict[str, float] = {}
        self._SAME_SYMBOL_COOLDOWN_SEC = 600  # 10 minutes

        self.event_bus.subscribe('trade_closed', self._on_trade_closed)

        self.mt5_client = MT5Client(magic_number=magic_number, mode=self.mode)
        self.data_feed = DataFeedEngine(self.mt5_client)
        self.context_engine = MarketContextEngine()
        self.regime_classifier = MarketRegimeClassifier()
        self.analyst_cluster = ParallelAnalystCluster()
        self.decision_engine = DecisionEngine(ml_predictor=self.ml_predictor)
        self.risk_engine = RiskEngine()
        self.order_manager = OrderManager(self.mt5_client)
        self.execution_engine = ExecutionEngine(self.mt5_client, self.state_manager)
        self.trade_memory = TradeMemory()

        self.state_synchronizer = MT5StateSynchronizer(self.mt5_client, self.state_manager, self.event_bus)
        self.position_monitor = PositionMonitorEngine(
            self.mt5_client, self.data_feed, self.context_engine, self.state_manager, self.event_bus
        )
        self._running = False
        self._main_thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the full JARVIS 3.0 engine and background workers."""
        if not self._running:
            self._running = True
            self.state_synchronizer.start()
            self.position_monitor.start()
            self._main_thread = threading.Thread(target=self._orchestration_loop, daemon=True, name="jarvis_orchestrator")
            self._main_thread.start()
            logger.info("JARVIS 3.0 Orchestrator started.")

    def stop(self):
        """Clean shutdown of all engine workers."""
        self._running = False
        self.position_monitor.stop()
        self.state_synchronizer.stop()
        self.mt5_client.shutdown()
        logger.info("JARVIS 3.0 Orchestrator stopped.")

    def _on_trade_closed(self, data):
        ticket = data.get("ticket")
        is_win = data.get("profit", 0) > 0
        r_multiple = data.get("r_multiple", 0.0)
        strategy = data.get("strategy", "UNKNOWN")
        new_equity = data.get("equity", 0.0)
        
        features = self._pending_features.pop(ticket, None)
        if features:
            self.ml_predictor.update_online(features, is_win)
            
        self.strategy_bandit.record_outcome(strategy, is_win, r_multiple)
        self.circuit_breaker.record_trade_result(is_win)
        self.drawdown_guard.update_equity_benchmarks(new_equity)
        logger.info(f"Trade {ticket} closed. Win: {is_win}, R: {r_multiple}. ML/Risk updated.")

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
        from jarvis.data.symbol_registry import resolve as _resolve_sym
        _spec = _resolve_sym(symbol)
        sym_info = {
            "trade_contract_size": _spec.contract_size,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01
        }

        # ── Hard Quality Gate: min model_confidence ────────────────────────
        # Root-cause of triple-Gold loss: entries with confidence only 0.40.
        # Raised minimum to 0.55. Also require devil penalty > 0 (entries with
        # zero devil penalty and high EV are suspiciously overconfident).
        MIN_CONFIDENCE = 0.55
        if decision.decision == "EXECUTE" and decision.model_confidence < MIN_CONFIDENCE:
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": f"CONFIDENCE_GATE: {decision.model_confidence:.2f} < {MIN_CONFIDENCE} minimum"}
        elif decision.decision == "EXECUTE" and decision.adversarial_penalty == 0.0 and decision.expected_value > 1.0:
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "OVERCONFIDENCE_GUARD: Zero devil penalty with high EV is suspicious."}
        else:
            auth_res = {"authorized": decision.decision == "EXECUTE"}

        # ── In-process execution lock + 10-min cooldown ────────────────────
        # Fixes race condition where ThreadPoolExecutor fires multiple trades
        # on same symbol before MT5StateSynchronizer 1-second sync catches up.
        canonical_sym = _spec.canonical
        with self._execution_lock:
            already_executing = canonical_sym in self._execution_in_progress
            last_exec_time = self._last_execution_time.get(canonical_sym, 0.0)
            cooldown_active = (time.time() - last_exec_time) < self._SAME_SYMBOL_COOLDOWN_SEC

        # Anti-Clustering Rule: Prevent stacking multiple simultaneous orders on same asset
        active_sym_positions = [
            p for p in positions if (p.symbol == symbol or (symbol == "XAUUSD" and "GOLD" in p.symbol)
                                      or canonical_sym in p.symbol.upper())
        ]

        # Asian Pre-Market Blackout Rule (01:00 to 05:00 UTC)
        now_utc_hour = datetime.now(timezone.utc).hour
        is_asian_blackout = (1 <= now_utc_hour < 5) and not is_crypto(symbol)

        # Active Open Position Trailing & Profit Lock Management
        for pos in active_sym_positions:
            try:
                manage_res = self.order_manager.manage_position(pos, context)
                if manage_res.get("modified"):
                    self.mt5_client.modify_position(
                        ticket=pos.ticket,
                        sl=manage_res["new_sl"],
                        tp=manage_res["new_tp"]
                    )
            except Exception as e:
                logger.error(f"Error trailing position #{pos.ticket}: {e}", exc_info=True)

        if already_executing and decision.decision == "EXECUTE":
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "IN_PROCESS_LOCK: Execution already in progress for this symbol."}
        elif cooldown_active and decision.decision == "EXECUTE":
            remaining = int(self._SAME_SYMBOL_COOLDOWN_SEC - (time.time() - last_exec_time))
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": f"COOLDOWN_GUARD: {remaining}s remaining before next {canonical_sym} trade."}
        elif active_sym_positions and decision.decision == "EXECUTE":
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "ANTI_CLUSTERING_GUARD: Active trade already open on this asset."}
        elif is_asian_blackout and decision.decision == "EXECUTE":
            decision.decision = "WAIT"
            decision.execution_authorized = False
            auth_res = {"authorized": False, "reason": "ASIAN_SESSION_BLACKOUT: Low liquidity chop protection active."}
        elif auth_res.get("authorized"):
            auth_res = self.risk_engine.authorize_execution(
                decision, account, positions, sym_info, current_spread_pips=context.volatility.current_spread_pips
            )



        # Circuit Breaker check
        cb_status = self.circuit_breaker.check_status()
        if cb_status.get('tripped') and decision.decision == 'EXECUTE':
            decision.decision = 'WAIT'
            decision.execution_authorized = False
            auth_res = {'authorized': False, 'reason': f'CIRCUIT_BREAKER: {cb_status.get("reason", "Cooling down")}'}

        # Drawdown Guard check
        dd_status = self.drawdown_guard.check_limits(account.equity, account.balance)
        if not dd_status.get('passed') and decision.decision == 'EXECUTE':
            decision.decision = 'WAIT'
            decision.execution_authorized = False
            reason = dd_status.get("breaches", ["Max drawdown reached"])[0] if dd_status.get("breaches") else "Max drawdown reached"
            auth_res = {'authorized': False, 'reason': f'DRAWDOWN_GUARD: {reason}'}

        # 7. Execute if authorized
        exec_res = None
        if auth_res.get("authorized") and decision.decision == "EXECUTE":
            decision.execution_authorized = True
            lots = auth_res.get("lots", 0.01)
            # Micro-lot cap on small accounts (< $250)
            if account.equity < 250.0:
                lots = 0.01

            # Claim in-process lock BEFORE sending to MT5
            with self._execution_lock:
                self._execution_in_progress.add(canonical_sym)

            try:
                exec_res = self.execution_engine.execute_decision(decision, lots)
            finally:
                # Always release lock; update cooldown only on successful fill
                with self._execution_lock:
                    self._execution_in_progress.discard(canonical_sym)
                    if exec_res and exec_res.get("status") == "FILLED":
                        self._last_execution_time[canonical_sym] = time.time()
                        logger.info(f"Execution lock released for {canonical_sym}. Cooldown {self._SAME_SYMBOL_COOLDOWN_SEC}s started.")

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
        """Ultra-fast parallel radar scan loop across configured symbols (<50ms latency)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max(4, len(self.symbols)), thread_name_prefix="radar_worker") as executor:
            while self._running:
                try:
                    future_to_sym = {executor.submit(self.run_cycle_for_symbol, sym): sym for sym in self.symbols}
                    radar_results = []
                    for fut in as_completed(future_to_sym):
                        sym = future_to_sym[fut]
                        try:
                            res = fut.result()
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
                            logger.error(f"Parallel scan error for {sym}: {e}", exc_info=True)

                    if radar_results:
                        self.state_manager.update_radar(radar_results)
                except Exception as e:
                    logger.error(f"Orchestration loop error: {e}", exc_info=True)

                try:
                    session = SessionEngine.get_current_session()
                    sleep_interval = 15.0 if session.is_prime_session else 60.0
                except Exception:
                    sleep_interval = 60.0
                time.sleep(sleep_interval)
