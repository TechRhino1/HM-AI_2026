import unittest
import pandas as pd
import numpy as np
from jarvis.market.market_context import MarketContextEngine
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.analysts.parallel_runner import ParallelAnalystCluster
from jarvis.analysts.devil_advocate import DevilAdvocateAnalyst
from jarvis.market.data_feed import DataFeedEngine

class TestAnalysts(unittest.TestCase):
    def setUp(self):
        self.feed = DataFeedEngine()
        self.context_engine = MarketContextEngine()
        self.regime_classifier = MarketRegimeClassifier()
        self.cluster = ParallelAnalystCluster(timeout_sec=2.0)
        self.devil = DevilAdvocateAnalyst()

    def test_parallel_analysts_execution_latency(self):
        mtf = self.feed.fetch_multi_timeframe("XAUUSD")
        context = self.context_engine.build_context("XAUUSD", mtf)
        regime = self.regime_classifier.classify_regime(context)

        reports, devil_report = self.cluster.run_all_parallel(context, regime, "BUY")

        # Verify all 6 analyst reports are returned
        expected_roles = ["STRUCTURE", "MOMENTUM", "LIQUIDITY", "VOLATILITY", "MACRO", "RISK"]
        for role in expected_roles:
            self.assertIn(role, reports)
            self.assertGreaterEqual(reports[role].score, 0.0)
            self.assertLessEqual(reports[role].score, 100.0)

        # Verify Devil's Advocate output
        self.assertIsNotNone(devil_report)
        self.assertGreaterEqual(devil_report.penalty_score, 0.0)
        self.assertLessEqual(devil_report.penalty_score, 50.0)
        self.assertGreaterEqual(devil_report.invalidation_risk_coefficient, 0.2)
        self.assertLessEqual(devil_report.invalidation_risk_coefficient, 1.0)

    def test_devil_advocate_penalty_scoring(self):
        mtf = self.feed.fetch_multi_timeframe("XAUUSD")
        context = self.context_engine.build_context("XAUUSD", mtf)
        regime = self.regime_classifier.classify_regime(context)

        # Test critique against BUY
        critique_buy = self.devil.critique_opportunity(context, regime, "BUY")
        self.assertEqual(critique_buy.counter_bias, "BEARISH")
        self.assertTrue(len(critique_buy.invalidation_triggers) > 0)

        # Test critique against SELL
        critique_sell = self.devil.critique_opportunity(context, regime, "SELL")
        self.assertEqual(critique_sell.counter_bias, "BULLISH")
        self.assertTrue(len(critique_sell.invalidation_triggers) > 0)

if __name__ == "__main__":
    unittest.main()
