"""
Regression tests for the integrity fixes applied during remediation:
  - Macro metric parser honours K/M/B magnitude suffixes (no silent magnitude loss).
  - Confidence calibration SHRINKS overconfidence (never inflates above empirical).
  - India / Stocks engines expose an auditable `data_source` flag instead of
    silently presenting fabricated candles as real.
"""
import unittest

from jarvis.analysts.macro_analyst import _parse_metric
from jarvis.intelligence.confidence import ConfidenceCalibrationEngine
from jarvis.india.india_engine import IndiaTechnicalEngine
from jarvis.stocks.stock_engine import StockIntelligenceEngine


class TestIntegrityFixes(unittest.TestCase):

    def test_parse_metric_magnitudes(self):
        self.assertEqual(_parse_metric("2.5M"), 2_500_000.0)
        self.assertEqual(_parse_metric("150K"), 150_000.0)
        self.assertEqual(_parse_metric("3.2%"), 3.2)
        self.assertEqual(_parse_metric("2.0"), 2.0)
        self.assertIsNone(_parse_metric(""))
        self.assertIsNone(_parse_metric("n/a"))

    def test_confidence_calibration_shrinks(self):
        c = ConfidenceCalibrationEngine()
        # High raw confidence must be calibrated DOWN, never inflated.
        self.assertLessEqual(c.calibrate_probability(0.99), 0.84)
        self.assertLess(c.calibrate_probability(0.95), 0.95)
        self.assertLess(c.calibrate_probability(0.84), 0.84)
        # A known bin centre maps to its empirical value (0.95 -> 0.84).
        self.assertAlmostEqual(c.calibrate_probability(0.95), 0.84, places=3)

    def test_india_data_source_flag(self):
        d = IndiaTechnicalEngine().analyze_india_instrument("RELIANCE", "1D")
        self.assertIn("data_source", d)
        self.assertIn(d["data_source"], ("live", "synthetic_fallback"))
        self.assertEqual(len(d["candles"]), 120)

    def test_stock_data_source_flag(self):
        s = StockIntelligenceEngine().analyze_stock("AAPL", "1D")
        self.assertIn("data_source", s)
        self.assertIn(s["data_source"], ("live", "synthetic_fallback"))
        self.assertEqual(len(s["candles"]), 120)


if __name__ == "__main__":
    unittest.main()
