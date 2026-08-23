import unittest
import pandas as pd
import numpy as np
from jarvis.market.market_structure import MarketStructureEngine

class TestMarketStructureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MarketStructureEngine(pivot_window=3)

    def test_higher_highs_and_lows(self):
        # Oscillating uptrend wave data creating distinct Higher Highs (HH) and Higher Lows (HL)
        prices = [
            100, 102, 106, 110, 108, 104, 105, 109, 115, 120, 117, 112, 114, 118, 125, 130, 126, 121, 124, 130, 136, 140, 135, 131, 134, 140, 148, 155, 150, 146, 150, 158, 165
        ]
        dates = pd.date_range(end=pd.Timestamp.now(), periods=len(prices), freq="1h")
        df = pd.DataFrame({
            "time": dates,
            "open": prices,
            "high": [p + 2.0 for p in prices],
            "low": [p - 2.0 for p in prices],
            "close": [p + 0.5 for p in prices],
            "volume": [1000] * len(prices)
        })

        res = self.engine.analyze_structure(df)
        self.assertTrue(hasattr(res, "bias"))
        self.assertTrue(res.higher_highs)
        self.assertTrue(res.higher_lows)
        self.assertEqual(res.bias, "BULLISH")

if __name__ == "__main__":
    unittest.main()
