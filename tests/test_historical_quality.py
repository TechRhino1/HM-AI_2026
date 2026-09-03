"""
Unit tests for Historical Market Data Quality & Anomaly Engine.
"""
import unittest
import pandas as pd
import numpy as np

from jarvis.historical.quality_engine import DataQualityEngine


class TestDataQualityEngine(unittest.TestCase):

    def setUp(self):
        self.engine = DataQualityEngine()
        dates = pd.date_range("2026-01-01", periods=50, freq="1h", tz="UTC")
        self.clean_df = pd.DataFrame({
            "time": dates,
            "open": np.linspace(100, 110, 50),
            "high": np.linspace(102, 112, 50),
            "low": np.linspace(98, 108, 50),
            "close": np.linspace(101, 111, 50),
            "tick_volume": [200] * 50,
            "spread": [1.5] * 50,
            "real_volume": [0] * 50
        })

    def test_clean_data_score_100(self):
        report = self.engine.audit_ohlcv(self.clean_df, "XAUUSD", "H1")
        self.assertEqual(report.quality_score, 100.0)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.anomalies), 0)

    def test_impossible_ohlc_detected(self):
        corrupt_df = self.clean_df.copy()
        # Make High < Low on bar 10
        corrupt_df.loc[10, "high"] = 90.0
        corrupt_df.loc[10, "low"] = 105.0

        report = self.engine.audit_ohlcv(corrupt_df, "XAUUSD", "H1")
        self.assertTrue(report.quality_score < 100.0)
        types = [a.anomaly_type for a in report.anomalies]
        self.assertIn("IMPOSSIBLE_OHLC_HIGH_LT_LOW", types)

    def test_zero_or_negative_price_detected(self):
        corrupt_df = self.clean_df.copy()
        corrupt_df.loc[5, "close"] = -10.0
        report = self.engine.audit_ohlcv(corrupt_df, "XAUUSD", "H1")
        self.assertTrue(report.quality_score < 100.0)
        self.assertFalse(report.is_valid)
        types = [a.anomaly_type for a in report.anomalies]
        self.assertIn("ZERO_OR_NEGATIVE_PRICE", types)

    def test_duplicate_timestamps_detected(self):
        corrupt_df = self.clean_df.copy()
        # Duplicate timestamp on bar 12
        corrupt_df.loc[12, "time"] = corrupt_df.loc[11, "time"]
        report = self.engine.audit_ohlcv(corrupt_df, "XAUUSD", "H1")
        self.assertTrue(report.quality_score < 100.0)
        types = [a.anomaly_type for a in report.anomalies]
        self.assertIn("DUPLICATE_TIMESTAMPS", types)

    def test_out_of_order_timestamps_detected(self):
        corrupt_df = self.clean_df.copy()
        # Swap timestamps
        t_temp = corrupt_df.loc[20, "time"]
        corrupt_df.loc[20, "time"] = corrupt_df.loc[25, "time"]
        corrupt_df.loc[25, "time"] = t_temp
        report = self.engine.audit_ohlcv(corrupt_df, "XAUUSD", "H1")
        types = [a.anomaly_type for a in report.anomalies]
        self.assertIn("OUT_OF_ORDER_TIMESTAMPS", types)


if __name__ == "__main__":
    unittest.main()
