import unittest
import pandas as pd
import numpy as np
from engines.market_structure import MarketStructureEngine

class TestMarketStructureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MarketStructureEngine(pivot_window=3)

    def test_higher_highs_and_lows(self):
        # Synthetic uptrend data
        prices = [100 + i * 2 for i in range(30)]
        dates = pd.date_range(end=pd.Timestamp.now(), periods=30, freq="1h")
        df = pd.DataFrame({
            "time": dates,
            "open": prices,
            "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices],
            "close": [p + 0.5 for p in prices],
            "volume": [1000] * 30
        })

        res = self.engine.analyze_structure(df)
        self.assertIn("bias", res)
        self.assertIn("swing_highs", res)

if __name__ == "__main__":
    unittest.main()
