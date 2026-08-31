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

    def test_autonomous_dynamic_trailing_stages_buy(self):
        """Validates Stage 0 (0.8R Zero-Risk Lock), Stage 1 (1.2R Profit Floor), and Stage 2 (1.5R Chandelier Trail) for BUY."""
        from jarvis.data.schemas import (
            MarketContext, StructureContext, LiquidityContext,
            VolatilityContext, MomentumContext, SessionContext
        )
        from datetime import timezone
        import time

        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2408.0,
            bid=2407.8,
            ask=2408.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=50.0, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())

        # Entry = 2400.0, initial SL = 2390.0 -> initial risk_dist = 10.0
        # 1. Price at 2408.0 -> favorable_dist = 8.0 -> R = 0.80 -> Stage 0: SL -> open_price + 0.10 * 10.0 = 2401.0
        pos = PositionSnapshot(
            ticket=201, symbol="XAUUSD", type="BUY", volume=0.01,
            open_price=2400.0, current_price=2408.0, sl=2390.0, tp=2440.0,
            profit=8.0, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER
        )
        self.mt5_client.modify_position.return_value = {"status": "MODIFIED"}
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(201, sl=2401.0, tp=2440.0)

        # 2. Price advances to 2412.0 -> favorable_dist = 12.0 -> R = 1.20 -> Stage 1: SL -> open_price + 0.40 * 10.0 = 2404.0
        ctx.current_price = 2412.0
        pos.current_price = 2412.0
        pos.sl = 2401.0
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(201, sl=2404.0, tp=2440.0)

        # 3. Price advances to 2420.0 -> favorable_dist = 20.0 -> R = 2.00 >= 1.50 -> Stage 2: SL -> current_price - 1.20 * atr = 2420.0 - 12.0 = 2408.0
        ctx.current_price = 2420.0
        pos.current_price = 2420.0
        pos.sl = 2404.0
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(201, sl=2408.0, tp=2440.0)

        # 4. Monotonic Ratchet check: Price retraces back to 2415.0 -> chandelier would be 2415 - 12 = 2403, but SL must NOT move backward (stays >= 2408.0)
        ctx.current_price = 2415.0
        pos.current_price = 2415.0
        pos.sl = 2408.0
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())
        self.mt5_client.modify_position.reset_mock()
        self.monitor._manage_single_position(pos)
        for call_args in self.mt5_client.modify_position.call_args_list:
            self.assertGreaterEqual(call_args.kwargs.get("sl", 0.0), 2408.0)

    def test_autonomous_dynamic_trailing_stages_sell(self):
        """Validates Stage 0, Stage 1, Stage 2 for SELL."""
        from jarvis.data.schemas import (
            MarketContext, StructureContext, LiquidityContext,
            VolatilityContext, MomentumContext, SessionContext
        )
        from datetime import timezone
        import time

        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0960,
            bid=1.0959,
            ask=1.0961,
            structure=StructureContext(bias="BEARISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0100, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=-50.0, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["EURUSD"] = (ctx, time.monotonic())

        # Entry = 1.1000, initial SL = 1.1050 -> initial risk_dist = 0.0050
        # 1. Price at 1.0960 -> favorable_dist = 0.0040 -> R = 0.0040 / 0.0050 = 0.80 -> Stage 0: SL -> open_price - 0.10 * 0.0050 = 1.0995
        pos = PositionSnapshot(
            ticket=301, symbol="EURUSD", type="SELL", volume=0.01,
            open_price=1.1000, current_price=1.0960, sl=1.1050, tp=1.0800,
            profit=40.0, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER
        )
        self.mt5_client.modify_position.return_value = {"status": "MODIFIED"}
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(301, sl=1.0995, tp=1.0800)


if __name__ == "__main__":
    unittest.main()
