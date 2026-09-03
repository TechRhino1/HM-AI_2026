"""
Integration test for BacktestEngine using HistoricalDataEngine.
"""
import unittest
from jarvis.backtesting.engine import BacktestEngine
from jarvis.historical.historical_engine import HISTORICAL_DATA_ENGINE


class TestBacktestWithHistoricalEngine(unittest.TestCase):

    def test_run_backtest_with_historical_engine(self):
        # We already downloaded XAUUSD H1 into the repository
        engine = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
        res = engine.run_backtest(symbol="XAUUSD", timeframe="H1")

        self.assertIn("symbol", res)
        self.assertEqual(res["symbol"], "XAUUSD")
        self.assertIn("metrics", res)
        self.assertIn("dataset_version", res)
        self.assertTrue(res["dataset_version"] >= 1)
        self.assertIn("final_balance", res)


if __name__ == "__main__":
    unittest.main()
