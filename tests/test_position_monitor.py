import unittest
from unittest.mock import MagicMock
from datetime import datetime
from jarvis.data.schemas import PositionSnapshot
from jarvis.execution.position_monitor import PositionMonitorEngine, JARVIS_MAGIC_NUMBER

class TestPositionMonitorManualClassification(unittest.TestCase):
    def setUp(self):
        self.mt5_client = MagicMock()
        self.data_feed = MagicMock()
        self.context_engine = MagicMock()
        self.state_manager = MagicMock()
        self.event_bus = MagicMock()

        self.monitor = PositionMonitorEngine(
            mt5_client=self.mt5_client,
            data_feed=self.data_feed,
            context_engine=self.context_engine,
            state_manager=self.state_manager,
            event_bus=self.event_bus,
        )

    def test_jarvis_ai_trade_not_classified_as_manual(self):
        pos = PositionSnapshot(
            ticket=101,
            symbol="XAUUSD",
            type="BUY",
            volume=0.02,
            open_price=2400.0,
            current_price=2405.0,
            sl=2390.0,
            tp=2420.0,
            profit=10.0,
            swap=0.0,
            commission=0.0,
            open_time=datetime.now(),
            magic=JARVIS_MAGIC_NUMBER,
            comment=""
        )
        self.assertFalse(self.monitor._is_manual_trade(pos))

    def test_manual_trade_with_comment(self):
        pos = PositionSnapshot(
            ticket=102,
            symbol="XAUUSD",
            type="BUY",
            volume=0.02,
            open_price=2400.0,
            current_price=2405.0,
            sl=2390.0,
            tp=2420.0,
            profit=10.0,
            swap=0.0,
            commission=0.0,
            open_time=datetime.now(),
            magic=JARVIS_MAGIC_NUMBER,
            comment="Manual trade from mobile"
        )
        self.assertTrue(self.monitor._is_manual_trade(pos))

    def test_manual_trade_with_desk_comment(self):
        pos = PositionSnapshot(
            ticket=103,
            symbol="EURUSD",
            type="SELL",
            volume=0.05,
            open_price=1.0850,
            current_price=1.0840,
            sl=1.0880,
            tp=1.0800,
            profit=5.0,
            swap=0.0,
            commission=0.0,
            open_time=datetime.now(),
            magic=JARVIS_MAGIC_NUMBER,
            comment="DESK order"
        )
        self.assertTrue(self.monitor._is_manual_trade(pos))

    def test_manual_trade_wrong_magic(self):
        pos = PositionSnapshot(
            ticket=104,
            symbol="XAUUSD",
            type="BUY",
            volume=0.01,
            open_price=2400.0,
            current_price=2405.0,
            sl=2390.0,
            tp=2420.0,
            profit=10.0,
            swap=0.0,
            commission=0.0,
            open_time=datetime.now(),
            magic=0,
            comment=""
        )
        self.assertTrue(self.monitor._is_manual_trade(pos))

if __name__ == "__main__":
    unittest.main()
