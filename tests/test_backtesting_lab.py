import unittest
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.monte_carlo import MonteCarloSimulator
from jarvis.backtesting.walk_forward import WalkForwardEngine, WalkForwardValidator
from jarvis.market.data_feed import DataFeedEngine

class TestBacktestingLab(unittest.TestCase):
    def setUp(self):
        feed = DataFeedEngine()
        self.df = feed.fetch_rates("XAUUSD", timeframe="H1", num_bars=300)

    def test_backtest_run(self):
        bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
        res = bt.run_backtest(self.df, symbol="XAUUSD")
        self.assertIn("metrics", res)
        self.assertIn("trades", res)
        self.assertGreater(res["final_balance"], 0.0)

    def test_monte_carlo(self):
        sample_trades = [
            {"pnl": 120.0}, {"pnl": -50.0}, {"pnl": 80.0}, {"pnl": 150.0}, {"pnl": -60.0},
            {"pnl": 90.0}, {"pnl": -45.0}, {"pnl": 200.0}, {"pnl": -70.0}, {"pnl": 110.0}
        ]
        mc = MonteCarloSimulator(num_simulations=100)
        res = mc.run_simulation(sample_trades, 10000.0)
        self.assertEqual(res["num_simulations"], 100)
        self.assertGreater(res["median_final_balance"], 0.0)

    def test_mtf_trade_styles(self):
        feed = DataFeedEngine()
        # SWING
        swing_data = feed.fetch_multi_timeframe("EURUSD", trade_style="SWING", num_bars=50)
        self.assertIn("macro", swing_data)
        self.assertIn("context", swing_data)
        self.assertIn("primary", swing_data)
        self.assertIn("setup", swing_data)
        self.assertIn("timing", swing_data)

        # DAY_TRADING
        day_data = feed.fetch_multi_timeframe("EURUSD", trade_style="DAY_TRADING", num_bars=50)
        self.assertIn("macro", day_data)
        self.assertIn("context", day_data)
        self.assertIn("primary", day_data)

        # SCALP
        scalp_data = feed.fetch_multi_timeframe("EURUSD", trade_style="SCALP", num_bars=50)
        self.assertIn("macro", scalp_data)
        self.assertIn("timing", scalp_data)

    def test_market_context_weighting(self):
        from jarvis.market.market_context import MarketContextEngine
        feed = DataFeedEngine()
        ce = MarketContextEngine()
        
        swing_data = feed.fetch_multi_timeframe("EURUSD", trade_style="SWING", num_bars=50)
        ctx_swing = ce.build_context("EURUSD", swing_data, trade_style="SWING")
        self.assertIn("D1", ctx_swing.mtf_alignment)
        self.assertIn("H4", ctx_swing.mtf_alignment)
        self.assertIn("H1", ctx_swing.mtf_alignment)

        day_data = feed.fetch_multi_timeframe("EURUSD", trade_style="DAY_TRADING", num_bars=50)
        ctx_day = ce.build_context("EURUSD", day_data, trade_style="DAY_TRADING")
        self.assertIn("H1", ctx_day.mtf_alignment)
        self.assertIn("M15", ctx_day.mtf_alignment)
        self.assertIn("M5", ctx_day.mtf_alignment)

if __name__ == "__main__":
    unittest.main()
