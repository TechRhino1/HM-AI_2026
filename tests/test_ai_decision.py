import unittest
from engines.ai_decision_engine import AIDecisionEngine

class TestAIDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AIDecisionEngine(min_trade_score=75.0)

    def test_high_quality_setup(self):
        structure = {"bias": "BULLISH", "bos": True}
        trend = {"trend_score": 80}
        volatility = {"state": "NORMAL", "is_excessive_spread": False}
        liquidity = {"sweep_detected": True, "sweep_type": "BULLISH_SWEEP"}
        news = {"news_status": "NEWS_RISK_LOW"}
        strategy = {"strategy": "TREND_PULLBACK_BULLISH", "recommended_action": "BUY"}
        sl_tp = {"rr_ratio": 2.5}

        res = self.engine.evaluate_trade_opportunity("XAUUSD", structure, trend, volatility, liquidity, news, strategy, sl_tp)
        self.assertIn(res["decision"], ["APPROVED", "EXECUTE"])
        self.assertEqual(res["action"], "BUY")
        self.assertGreaterEqual(res["trade_score"], 75.0)

if __name__ == "__main__":
    unittest.main()
