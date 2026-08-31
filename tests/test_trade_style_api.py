import unittest
import json
from jarvis.application.state_manager import StateManager
from jarvis.market.data_feed import DataFeedEngine
from jarvis.market.market_context import MarketContextEngine

class TestTradeStyleAPI(unittest.TestCase):
    def setUp(self):
        self.state_mgr = StateManager()

    def test_state_manager_trade_style(self):
        self.state_mgr.set_trade_style("SCALP")
        self.assertEqual(self.state_mgr.trade_style, "SCALP")
        
        snap = self.state_mgr.get_state_snapshot()
        self.assertIn("trade_style", snap)
        self.assertEqual(snap["trade_style"], "SCALP")

        self.state_mgr.set_trade_style("DAY_TRADING")
        self.assertEqual(self.state_mgr.trade_style, "DAY_TRADING")
        snap = self.state_mgr.get_state_snapshot()
        self.assertEqual(snap["trade_style"], "DAY_TRADING")

        self.state_mgr.set_trade_style("SWING")
        self.assertEqual(self.state_mgr.trade_style, "SWING")
        snap = self.state_mgr.get_state_snapshot()
        self.assertEqual(snap["trade_style"], "SWING")

    def test_mtf_data_feed_styles(self):
        feed = DataFeedEngine()
        
        # Test SWING timeframes
        swing_mtf = feed.fetch_multi_timeframe("EURUSD", trade_style="SWING", num_bars=30)
        self.assertIn("primary", swing_mtf)
        self.assertIn("context", swing_mtf)
        self.assertIn("macro", swing_mtf)

        # Test DAY_TRADING timeframes
        day_mtf = feed.fetch_multi_timeframe("EURUSD", trade_style="DAY_TRADING", num_bars=30)
        self.assertIn("primary", day_mtf)
        self.assertIn("context", day_mtf)
        self.assertIn("macro", day_mtf)

        # Test SCALP timeframes
        scalp_mtf = feed.fetch_multi_timeframe("EURUSD", trade_style="SCALP", num_bars=30)
        self.assertIn("primary", scalp_mtf)
        self.assertIn("timing", scalp_mtf)

    def test_market_context_styles(self):
        feed = DataFeedEngine()
        ce = MarketContextEngine()

        scalp_mtf = feed.fetch_multi_timeframe("EURUSD", trade_style="SCALP", num_bars=30)
        ctx_scalp = ce.build_context("EURUSD", scalp_mtf, trade_style="SCALP")
        self.assertIsNotNone(ctx_scalp)
        self.assertIn("M15", ctx_scalp.mtf_alignment)
        self.assertIn("M5", ctx_scalp.mtf_alignment)

        day_mtf = feed.fetch_multi_timeframe("EURUSD", trade_style="DAY_TRADING", num_bars=30)
        ctx_day = ce.build_context("EURUSD", day_mtf, trade_style="DAY_TRADING")
        self.assertIsNotNone(ctx_day)
        self.assertIn("H1", ctx_day.mtf_alignment)
        self.assertIn("M15", ctx_day.mtf_alignment)

    def test_radar_filtering(self):
        self.state_mgr.update_radar([
            {"symbol": "EURUSD", "trade_style": "SWING", "timeframe": "D1/H4/H1", "win_prob": 80},
            {"symbol": "GBPUSD", "trade_style": "DAY_TRADING", "timeframe": "H1/M15/M5", "win_prob": 75},
            {"symbol": "XAUUSD", "trade_style": "SCALP", "timeframe": "M15/M5/M1", "win_prob": 85}
        ])
        
        opps = self.state_mgr.radar_opportunities
        self.assertEqual(len(opps), 3)

        scalp_opps = [o for o in opps if o.get("trade_style") == "SCALP"]
        self.assertEqual(len(scalp_opps), 1)
        self.assertEqual(scalp_opps[0]["symbol"], "XAUUSD")

        day_opps = [o for o in opps if o.get("trade_style") == "DAY_TRADING"]
        self.assertEqual(len(day_opps), 1)
        self.assertEqual(day_opps[0]["symbol"], "GBPUSD")

if __name__ == "__main__":
    unittest.main()
