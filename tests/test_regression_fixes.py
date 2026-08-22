import unittest
import os
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from jarvis.data.database import SQLiteTradeDB
from jarvis.execution.mt5_client import MT5Client
from jarvis.data.schemas import (
    PositionSnapshot,
    MarketContext,
    StructureContext,
    LiquidityContext,
    VolatilityContext,
    MomentumContext,
    SessionContext,
    RegimeOutput,
    MarketRegime,
    DecisionObject,
    TradeQualityGateResult,
    AccountSnapshot
)
from jarvis.execution.position_monitor import PositionMonitorEngine, JARVIS_MAGIC_NUMBER
from engines.dynamic_sl_tp import DynamicSLTPEngine
from jarvis.risk.position_sizing import PositionSizer
from jarvis.risk.circuit_breaker import CircuitBreaker
from jarvis.analysts.devil_advocate import DevilAdvocateAnalyst
from jarvis.intelligence.self_learning import SelfLearningEngine
from jarvis.execution.execution_engine import ExecutionEngine
from jarvis.application.state_manager import StateManager
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.risk.risk_engine import RiskEngine
from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.intelligence.regime_engine import MarketRegimeClassifier

class TestRegressionFixes(unittest.TestCase):
    def test_a1_log_trade_timezone_iso(self):
        """A1: Verify log_trade writes row with valid ISO timestamp and no NameError."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name
        
        try:
            db = SQLiteTradeDB(db_path=db_path)
            db.log_trade(
                ticket=777888,
                symbol='XAUUSD',
                action='BUY',
                entry=2450.50,
                sl=2440.00,
                tp=2470.00,
                volume=0.05,
                score=92.5,
                regime='TRENDING_BULL',
                ev=1.85,
                executor='BOT (AI)',
                session_name='LONDON',
                is_prime_session=True,
                adx=32.5,
                plus_di=28.0,
                minus_di=14.0,
                spread_pips=1.5,
                mtf_alignment='{"D1": "BULLISH", "H4": "BULLISH"}',
                threats_json='[]',
                features_json='{"strategy": "BREAKOUT"}'
            )
            
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute('''
                SELECT ticket, symbol, action, entry_price, sl, tp, volume, timestamp, 
                       ai_score, regime, expected_value, executor, session_name, adx, spread_pips
                FROM executed_trades WHERE ticket=777888
            ''')
            row = cur.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row[0], 777888)
            self.assertEqual(row[1], 'XAUUSD')
            self.assertEqual(row[2], 'BUY')
            self.assertEqual(row[3], 2450.50)
            self.assertEqual(row[11], 'BOT (AI)')
            self.assertEqual(row[12], 'LONDON')
            self.assertEqual(row[13], 32.5)
            self.assertEqual(row[14], 1.5)
            
            # Assert timestamp parses as valid ISO format
            ts_str = row[7]
            parsed_dt = datetime.fromisoformat(ts_str)
            self.assertIsNotNone(parsed_dt)
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_a2_paper_modify_and_close_status(self):
        """A2: Verify paper mode returns MODIFIED and CLOSED matching callers."""
        client = MT5Client(mode='paper')
        
        # Place paper trade
        exec_res = client.send_market_order('EURUSD', 'BUY', 0.01, 1.0850, 1.0800, 1.0950)
        ticket = exec_res.get('ticket')
        self.assertIsNotNone(ticket)
        
        # Modify SL/TP
        mod_res = client.modify_position(ticket, 1.0820, 1.0980)
        self.assertEqual(mod_res.get('status'), 'MODIFIED')
        self.assertEqual(mod_res.get('sl'), 1.0820)
        self.assertEqual(mod_res.get('tp'), 1.0980)
        
        # Close position
        close_res = client.close_position(ticket)
        self.assertEqual(close_res.get('status'), 'CLOSED')
        self.assertEqual(close_res.get('ticket'), ticket)

    def test_a3_position_monitor_manual_tag_classification(self):
        """A3: Verify _is_manual_trade properly detects manual trades vs AI trades."""
        monitor = PositionMonitorEngine(
            mt5_client=MagicMock(),
            data_feed=MagicMock(),
            context_engine=MagicMock(),
            state_manager=MagicMock(),
            event_bus=MagicMock()
        )
        
        # AI trade
        ai_pos = PositionSnapshot(
            ticket=1, symbol='BTCUSD', type='BUY', volume=0.01,
            open_price=60000, current_price=60100, sl=59000, tp=62000,
            profit=10.0, swap=0.0, commission=0.0, open_time=datetime.now(),
            magic=JARVIS_MAGIC_NUMBER, comment='JARVIS_EXECUTION'
        )
        self.assertFalse(monitor._is_manual_trade(ai_pos))
        
        # Manual trade with tag
        desk_pos = PositionSnapshot(
            ticket=2, symbol='BTCUSD', type='BUY', volume=0.01,
            open_price=60000, current_price=60100, sl=59000, tp=62000,
            profit=10.0, swap=0.0, commission=0.0, open_time=datetime.now(),
            magic=JARVIS_MAGIC_NUMBER, comment='DESK_MANUAL_ORDER'
        )
        self.assertTrue(monitor._is_manual_trade(desk_pos))

    def test_a4_dynamic_sl_tp_profile_multiplier(self):
        """A4: Verify dynamic SL calculation uses sl_atr_multiplier from profile."""
        engine = DynamicSLTPEngine()
        profile = {'digits': 2, 'sl_atr_multiplier': 2.0}
        struct_data = {'demand_zone': (0, 0), 'supply_zone': (0, 0)}
        vol_data = {'atr': 5.0}
        
        res = engine.calculate_sl_tp('XAUUSD', 'BUY', 2400.0, struct_data, vol_data, profile)
        sl_dist = 2400.0 - res['sl_price']
        self.assertLessEqual(sl_dist, 10.0 + 1e-4)

    def test_a5_is_high_vol_sizing_strengthened(self):
        """A5: Verify is_high_vol strictly reduces lot sizing by 0.85x multiplier."""
        sym_gold = {"name": "XAUUSD", "trade_contract_size": 100.0, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        sym_base = {"name": "CUSTOM_ASSET", "trade_contract_size": 100.0, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        
        # Account balance = $5,000, distance = $10, risk = 1.0% ($50)
        gold_size = PositionSizer.calculate_lot_size(
            account_balance=5000.0, entry_price=2400.0, sl_price=2390.0, risk_pct=1.0, symbol_info=sym_gold
        )
        base_size = PositionSizer.calculate_lot_size(
            account_balance=5000.0, entry_price=2400.0, sl_price=2390.0, risk_pct=1.0, symbol_info=sym_base
        )
        # Gold should receive 0.85x reduction: 0.04 lots vs 0.05 lots
        self.assertLess(gold_size, base_size)
        self.assertEqual(gold_size, 0.04)
        self.assertEqual(base_size, 0.05)

    def test_b1_devil_advocate_spread_typical_spec(self):
        """B1-BUG: Verify devil_advocate handles is_excessive_spread without AttributeError."""
        analyst = DevilAdvocateAnalyst()
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(is_excessive_spread=True, current_spread_pips=12.0),
            momentum=MomentumContext(),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.8)
        report = analyst.critique_opportunity(ctx, regime, "BUY")
        self.assertIsNotNone(report)
        self.assertTrue(any("Excessive spread" in t for t in report.threats_detected))

    def test_b2_circuit_breaker_isolation_and_persistence(self):
        """B2-BUG: Verify circuit breaker attributes initialize properly and isolate per symbol."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name
        
        try:
            cb = CircuitBreaker(db_path=db_path)
            self.assertFalse(cb.is_symbol_paused("XAUUSD"))
            self.assertFalse(cb.is_symbol_paused("EURUSD"))
            
            # Record 2 consecutive losses on XAUUSD
            cb.record_trade_result(is_win=False, symbol="XAUUSD", regime="TREND_BULL")
            self.assertFalse(cb.is_symbol_paused("XAUUSD"))
            cb.record_trade_result(is_win=False, symbol="XAUUSD", regime="TREND_BULL")
            
            # XAUUSD must be paused, but EURUSD must NOT be paused
            self.assertTrue(cb.is_symbol_paused("XAUUSD"))
            self.assertFalse(cb.is_symbol_paused("EURUSD"))
            
            # Win on EURUSD should not clear XAUUSD pause
            cb.record_trade_result(is_win=True, symbol="EURUSD", regime="TREND_BULL")
            self.assertTrue(cb.is_symbol_paused("XAUUSD"))
            self.assertFalse(cb.is_symbol_paused("EURUSD"))
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_b1_empirical_pattern_memory_lookup(self):
        """B1-WIRING: Verify get_pattern_win_rate_and_ev executes without error."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name
        
        try:
            db = SQLiteTradeDB(db_path=db_path)
            for i in range(5):
                db.log_trade(
                    ticket=1000 + i, symbol="XAUUSD", action="BUY", entry=2400.0,
                    sl=2390.0, tp=2420.0, volume=0.01, score=80.0,
                    regime="TREND_BULL", ev=1.5 if i % 2 == 0 else -0.5,
                    session_name="LONDON", is_prime_session=True
                )
            sle = SelfLearningEngine(db_path=db_path)
            res = sle.get_pattern_win_rate_and_ev("XAUUSD", "TREND_BULL", "LONDON", True)
            self.assertEqual(res["sample_size"], 5)
            self.assertIn("win_rate", res)
            self.assertIn("conviction_multiplier", res)
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_a9_hm_start_smoke_error_handling(self):
        """A9/A12: Verify HM_start orchestrator error is safely logged without crash."""
        import HM_start
        with patch('HM_start.JarvisOrchestrator') as mock_orch, \
             patch('HM_start.threading.Thread') as mock_thread, \
             patch('HM_start.start_cloudflare_tunnel', return_value=(None, None)):
            
            mock_inst = MagicMock()
            mock_inst.start.side_effect = RuntimeError('Simulated startup failure')
            mock_orch.return_value = mock_inst
            
            with patch('sys.argv', ['HM_start.py', 'view']), \
                 patch('time.sleep', side_effect=KeyboardInterrupt):
                try:
                    HM_start.main()
                except KeyboardInterrupt:
                    pass
            
            self.assertTrue(mock_inst.start.called)
            self.assertTrue(mock_thread.called)

    def test_c1_execution_engine_rich_market_context_logging(self):
        """C1-WIRING: Verify execution_engine resolves real MarketContext and writes non-default metrics to DB."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name

        try:
            custom_db = SQLiteTradeDB(db_path=db_path)
            
            # Setup StateManager with rich MarketContext
            state_mgr = StateManager()
            ctx = MarketContext(
                symbol="XAUUSD",
                timestamp=datetime.now(timezone.utc),
                current_price=2400.0,
                bid=2399.8,
                ask=2400.2,
                structure=StructureContext(bias="BULLISH"),
                liquidity=LiquidityContext(),
                volatility=VolatilityContext(current_spread_pips=1.8),
                momentum=MomentumContext(adx=38.5, plus_di=30.0, minus_di=12.0),
                session=SessionContext(current_session="LONDON", is_prime_session=True),
                mtf_alignment={"H1": "BULLISH", "H4": "BULLISH"}
            )
            state_mgr.update_market_context("XAUUSD", ctx)
            
            # Verify StateManager get_market_context returns ctx
            self.assertEqual(state_mgr.get_market_context("XAUUSD"), ctx)

            mock_mt5 = MagicMock()
            mock_mt5.send_market_order.return_value = {
                "status": "FILLED",
                "ticket": 888999,
                "price": 2400.0,
                "sl": 2390.0,
                "tp": 2425.0
            }
            mock_bus = MagicMock()

            regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)
            decision = DecisionObject(
                symbol="XAUUSD",
                timestamp=datetime.now(timezone.utc),
                regime=regime,
                bias="BUY",
                probabilities={"buy": 0.85},
                strategy="MOMENTUM_BREAKOUT",
                entry_price=2400.0,
                stop_loss=2390.0,
                take_profit=2425.0,
                risk_reward_ratio=2.5,
                calculated_risk_percent=0.5,
                expected_value=25.0,
                model_confidence=0.85,
                adversarial_penalty=5.0,
                invalidation_levels=[],
                bull_case=[],
                bear_case=[],
                risk_factors=[],
                quality_gate=TradeQualityGateResult(passed=True, checks={}),
                decision="EXECUTE",
                execution_authorized=True,
                context=ctx
            )

            with patch('jarvis.data.database.TRADE_DB', custom_db):
                exec_engine = ExecutionEngine(mt5_client=mock_mt5, state_manager=state_mgr)
                res = exec_engine.execute_decision(decision, lots=0.01)

            self.assertEqual(res.get("status"), "FILLED")
            self.assertEqual(res.get("ticket"), 888999)

            # Query the database row written by execution_engine
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute('''
                SELECT ticket, symbol, session_name, is_prime_session, adx, plus_di, minus_di, spread_pips, mtf_alignment
                FROM executed_trades WHERE ticket=888999
            ''')
            row = cur.fetchone()
            conn.close()

            self.assertIsNotNone(row, "Trade row must be logged in DB")
            self.assertEqual(row[0], 888999)
            self.assertEqual(row[1], "XAUUSD")
            self.assertEqual(row[2], "LONDON", "session_name must not fall back to UNKNOWN default")
            self.assertEqual(row[3], 1, "is_prime_session must be True (1)")
            self.assertAlmostEqual(row[4], 38.5, places=2, msg="ADX must not fall back to 0.0 default")
            self.assertAlmostEqual(row[5], 30.0, places=2)
            self.assertAlmostEqual(row[6], 12.0, places=2)
            self.assertAlmostEqual(row[7], 1.8, places=2, msg="spread_pips must not fall back to 0.0 default")
            self.assertIn("BULLISH", row[8])
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_c2_decision_engine_risk_engine_drawdown_consistency(self):
        """C2-CONSISTENCY: Verify DecisionEngine and RiskEngine never report conflicting drawdown authorization."""
        dec_engine = DecisionEngine()
        risk_engine = RiskEngine(max_drawdown_pct=10.0, is_backtest=True)

        ctx = MarketContext(
            symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=60000.0,
            bid=59995.0,
            ask=60005.0,
            structure=StructureContext(bias="BULLISH", bos=True),
            liquidity=LiquidityContext(sweep_detected=True),
            volatility=VolatilityContext(atr=500.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=30.0, adx=30.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={"TREND_BULL": 0.9}, confidence=0.85)

        # Scenario A: 12% drawdown (exceeds 10.0% max limit)
        # DecisionEngine quality gate check MUST fail on Drawdown Safety Guard
        dec_high_dd = dec_engine.evaluate(
            context=ctx,
            regime=regime,
            analyst_reports={},
            devil_report=MagicMock(penalty_score=2.0, threats_detected=[], invalidation_risk_coefficient=1.0),
            account_balance=8800.0,
            current_drawdown_pct=12.0
        )
        self.assertIn("Drawdown Safety Guard", dec_high_dd.quality_gate.checks)
        self.assertFalse(dec_high_dd.quality_gate.checks["Drawdown Safety Guard"], "Drawdown Safety Guard must fail at 12% DD")
        self.assertFalse(dec_high_dd.quality_gate.passed, "Quality gate must not pass at 12% DD")
        self.assertNotEqual(dec_high_dd.decision, "EXECUTE")

        # RiskEngine authorization under 12% drawdown ($8,800 equity vs $10,000 balance)
        high_dd_account = AccountSnapshot(login=1, server="Test", balance=10000.0, equity=8800.0, margin=0.0, free_margin=8800.0, margin_level=0.0, leverage=100)
        risk_high_dd = risk_engine.authorize_execution(
            decision=dec_high_dd,
            account=high_dd_account,
            positions=[],
            symbol_info={"trade_contract_size": 1.0, "volume_min": 0.01, "volume_max": 10.0, "volume_step": 0.01},
            current_spread_pips=2.0
        )
        self.assertFalse(risk_high_dd["authorized"], "RiskEngine must block trade at 12% DD")

        # Scenario B: 2% drawdown (well within 10.0% max limit)
        dec_normal_dd = dec_engine.evaluate(
            context=ctx,
            regime=regime,
            analyst_reports={},
            devil_report=MagicMock(penalty_score=2.0, threats_detected=[], invalidation_risk_coefficient=1.0),
            account_balance=9800.0,
            current_drawdown_pct=2.0
        )
        self.assertTrue(dec_normal_dd.quality_gate.checks["Drawdown Safety Guard"], "Drawdown Safety Guard must pass at 2% DD")

    def test_d1_online_ml_and_trade_memory_learning_loop(self):
        """D1-LEARNING: Verify orchestrator populates _pending_features, journals trade, and updates ML on trade close."""
        orch = JarvisOrchestrator(mode="paper")

        orch.mt5_client.get_account_snapshot = MagicMock(return_value=AccountSnapshot(
            login=123, server="Test", balance=10000.0, equity=10000.0, margin=0.0,
            free_margin=10000.0, margin_level=0.0, leverage=100, trade_allowed=True
        ))

        mock_decision = DecisionObject(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            regime=RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={"TREND_BULL": 0.8}, confidence=0.8),
            bias="BUY",
            probabilities={"buy": 0.85},
            strategy="MOMENTUM_BREAKOUT",
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2425.0,
            risk_reward_ratio=2.5,
            calculated_risk_percent=0.5,
            expected_value=25.0,
            model_confidence=0.85,
            adversarial_penalty=5.0,
            invalidation_levels=[],
            bull_case=[],
            bear_case=[],
            risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={}),
            decision="EXECUTE",
            execution_authorized=True
        )
        orch.decision_engine.evaluate = MagicMock(return_value=mock_decision)

        orch.execution_engine.execute_decision = MagicMock(return_value={
            "status": "FILLED",
            "ticket": 999333,
            "price": 2400.0,
            "sl": 2390.0,
            "tp": 2425.0
        })

        # Run cycle for symbol
        res = orch.run_cycle_for_symbol("XAUUSD")
        self.assertEqual(res.get("execution", {}).get("status"), "FILLED")

        # 1. Assert _pending_features populated
        self.assertIn(999333, orch._pending_features, "Ticket 999333 must be cached in _pending_features")
        self.assertIn("features", orch._pending_features[999333])
        self.assertEqual(orch._pending_features[999333]["strategy"], "MOMENTUM_BREAKOUT")

        # 2. Assert trade_memory recorded trade on entry
        recent = orch.trade_memory.fetch_recent_trades(1)
        self.assertTrue(len(recent) > 0, "Trade memory must have recorded the opened trade")
        self.assertEqual(recent[0].get("ticket"), 999333)

        # 3. Simulate trade close event
        initial_training_steps = orch.ml_predictor.training_steps
        orch._on_trade_closed({
            "ticket": 999333,
            "symbol": "XAUUSD",
            "pnl": 50.0,
            "exit_price": 2420.0,
            "equity": 10050.0
        })

        # 4. Assert ML predictor received online update and pending features popped
        self.assertNotIn(999333, orch._pending_features, "Ticket must be popped from _pending_features after close")
        self.assertEqual(len(orch.ml_predictor._grad_buffer), 1, "ML grad buffer must record gradient step")

        # After 2 more trade closes (batch_size=3), training_steps increments
        dummy_feat = orch.ml_predictor.extract_feature_vector(
            context=MarketContext(symbol="XAUUSD", timestamp=datetime.now(timezone.utc), current_price=2400.0, bid=2399.8, ask=2400.2, structure=StructureContext(bias="BULLISH"), liquidity=LiquidityContext(), volatility=VolatilityContext(), momentum=MomentumContext(), session=SessionContext()),
            regime=RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.8),
            tentative_bias="BUY"
        )
        orch._pending_features[999334] = {"features": dummy_feat}
        orch._pending_features[999335] = {"features": dummy_feat}
        orch._on_trade_closed({"ticket": 999334, "pnl": 20.0, "exit_price": 2410.0, "equity": 10070.0})
        orch._on_trade_closed({"ticket": 999335, "pnl": -10.0, "exit_price": 2395.0, "equity": 10060.0})
        self.assertEqual(orch.ml_predictor.training_steps, initial_training_steps + 1, "ML training_steps must increment when mini-batch completes")

        # 5. Assert trade_memory row was updated with exit metrics
        closed_rows = [t for t in orch.trade_memory.fetch_recent_trades(1) if t.get("ticket") == 999333]
        self.assertTrue(len(closed_rows) > 0)
        self.assertEqual(closed_rows[0].get("exit_price"), 2420.0)
        self.assertEqual(closed_rows[0].get("is_win"), 1)

    def test_d2_per_symbol_regime_classification_isolation(self):
        """D2-REGIME: Verify regime classification state is per-symbol and free of cross-contamination."""
        classifier = MarketRegimeClassifier()

        bull_ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", higher_highs=True, higher_lows=True, bos=True, bos_type="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(state="NORMAL"),
            momentum=MomentumContext(trend_score=80.0, adx=35.0),
            session=SessionContext(is_prime_session=True)
        )

        range_ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="RANGING"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(state="COMPRESSION"),
            momentum=MomentumContext(trend_score=0.0, adx=12.0),
            session=SessionContext(is_prime_session=True)
        )

        # 1. Classify XAUUSD (Initial Bullish)
        r1_xau = classifier.classify_regime(bull_ctx, previous_regime=None, previous_persistence=0)
        self.assertEqual(r1_xau.primary_regime, MarketRegime.TREND_BULL)
        self.assertFalse(r1_xau.regime_transition, "First scan has no transition")
        self.assertEqual(r1_xau.regime_persistence, 0)

        # 2. Classify EURUSD (Range) in parallel or interleaved
        r1_eur = classifier.classify_regime(range_ctx, previous_regime=None, previous_persistence=0)
        self.assertEqual(r1_eur.primary_regime, MarketRegime.RANGE)
        self.assertFalse(r1_eur.regime_transition, "EURUSD first scan has no transition")
        self.assertEqual(r1_eur.regime_persistence, 0)

        # 3. Classify XAUUSD again (Still Bullish)
        # Using XAUUSD's own previous state: (TREND_BULL, 0)
        r2_xau = classifier.classify_regime(bull_ctx, previous_regime=r1_xau.primary_regime, previous_persistence=r1_xau.regime_persistence)
        self.assertEqual(r2_xau.primary_regime, MarketRegime.TREND_BULL)
        self.assertFalse(r2_xau.regime_transition, "XAUUSD must NOT report a transition caused by EURUSD's intervening scan")
        self.assertEqual(r2_xau.regime_persistence, 1, "XAUUSD persistence must increment to 1")

        # 4. Classify XAUUSD Transition to Range
        r3_xau = classifier.classify_regime(range_ctx, previous_regime=r2_xau.primary_regime, previous_persistence=r2_xau.regime_persistence)
        self.assertEqual(r3_xau.primary_regime, MarketRegime.RANGE)
        self.assertTrue(r3_xau.regime_transition, "XAUUSD must report regime transition when its own regime changes")
        self.assertEqual(r3_xau.regime_persistence, 0, "Persistence resets on transition")

if __name__ == '__main__':
    unittest.main()
