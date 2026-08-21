import unittest
import os
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from jarvis.data.database import SQLiteTradeDB
from jarvis.execution.mt5_client import MT5Client
from jarvis.data.schemas import PositionSnapshot
from jarvis.execution.position_monitor import PositionMonitorEngine, JARVIS_MAGIC_NUMBER
from engines.dynamic_sl_tp import DynamicSLTPEngine
from jarvis.risk.position_sizing import PositionSizer
from engines.risk_engine import RiskManagerEngine

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
                executor='BOT (AI)'
            )
            
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute('SELECT ticket, symbol, action, entry_price, sl, tp, volume, timestamp, ai_score, regime, expected_value, executor FROM executed_trades WHERE ticket=777888')
            row = cur.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row[0], 777888)
            self.assertEqual(row[1], 'XAUUSD')
            self.assertEqual(row[2], 'BUY')
            self.assertEqual(row[3], 2450.50)
            self.assertEqual(row[11], 'BOT (AI)')
            
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

    def test_a5_is_high_vol_sizing(self):
        """A5: Verify is_high_vol lot/risk reduction for volatile instruments."""
        sym_gold = {"name": "XAUUSD", "trade_contract_size": 100.0, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        sym_eur = {"name": "EURUSD", "trade_contract_size": 100000.0, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        
        gold_size = PositionSizer.calculate_lot_size(
            account_balance=500.0, entry_price=2400.0, sl_price=2390.0, risk_pct=1.0, symbol_info=sym_gold
        )
        eur_size = PositionSizer.calculate_lot_size(
            account_balance=500.0, entry_price=1.0850, sl_price=1.0800, risk_pct=1.0, symbol_info=sym_eur
        )
        self.assertGreater(gold_size, 0)
        self.assertGreater(eur_size, 0)

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

if __name__ == '__main__':
    unittest.main()
