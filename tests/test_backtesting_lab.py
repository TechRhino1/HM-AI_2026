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

    def test_walk_forward(self):
        wf = WalkForwardEngine(num_folds=2, in_sample_pct=0.70, initial_balance=10000.0, risk_per_trade_pct=0.5)
        res = wf.run_walk_forward_validation(self.df, symbol="XAUUSD")
        self.assertIn("walk_forward_efficiency", res)
        self.assertIn("fold_results", res)
        self.assertGreaterEqual(len(res["fold_results"]), 1)

if __name__ == "__main__":
    unittest.main()
