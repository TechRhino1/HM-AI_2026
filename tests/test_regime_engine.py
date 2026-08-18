import unittest
from engines.regime_engine import MarketRegimeEngine

class TestRegimeEngine(unittest.TestCase):
    def setUp(self):
        self.regime_engine = MarketRegimeEngine()

    def test_strong_bullish_regime(self):
        structure = {"bias": "BULLISH", "bos": True, "choch": False}
        trend = {"trend_score": 85, "adx": 32}
        volatility = {"state": "NORMAL"}
        liquidity = {"sweep_detected": False}

        res = self.regime_engine.classify_regime(structure, trend, volatility, liquidity)
        self.assertEqual(res["regime"], "STRONG_TREND_BULLISH")
        self.assertGreaterEqual(res["confidence"], 85.0)

    def test_volatility_shock_regime(self):
        structure = {"bias": "BULLISH", "bos": False}
        trend = {"trend_score": 50, "adx": 15}
        volatility = {"state": "EXTREME"}
        liquidity = {"sweep_detected": False}

        res = self.regime_engine.classify_regime(structure, trend, volatility, liquidity)
        self.assertEqual(res["regime"], "HIGH_VOLATILITY_SHOCK")

if __name__ == "__main__":
    unittest.main()
