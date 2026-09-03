"""
Unit tests for Historical Market Data Lake Storage and Metadata DB.
"""
import os
import shutil
import tempfile
import unittest
import pandas as pd
import numpy as np

from jarvis.historical.storage import StorageEngine
from jarvis.historical.metadata_db import MetadataDB


class TestHistoricalStorageAndMetadata(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage = StorageEngine(base_data_dir=os.path.join(self.test_dir, "data"))
        self.metadata_db = MetadataDB(db_path=os.path.join(self.test_dir, "metadata", "test_meta.db"))

        # Create sample DataFrame
        dates = pd.date_range("2026-01-01", periods=100, freq="1h", tz="UTC")
        self.sample_df = pd.DataFrame({
            "time": dates,
            "open": np.linspace(2000, 2050, 100),
            "high": np.linspace(2005, 2055, 100),
            "low": np.linspace(1995, 2045, 100),
            "close": np.linspace(2002, 2052, 100),
            "tick_volume": np.random.randint(100, 500, 100),
            "spread": [2.0] * 100,
            "real_volume": [0] * 100
        })

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normalize_ohlcv_dataframe(self):
        clean_df = self.storage.normalize_ohlcv_dataframe(self.sample_df)
        self.assertEqual(len(clean_df), 100)
        self.assertTrue("time" in clean_df.columns)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(clean_df["time"]))

    def test_atomic_parquet_write_and_checksum(self):
        manifest = self.storage.write_dataset_atomic(
            broker_server="TestBroker",
            symbol="XAUUSD",
            timeframe="H1",
            df=self.sample_df,
            version=1,
            quality_score=98.5
        )
        self.assertEqual(manifest["symbol"], "XAUUSD")
        self.assertEqual(manifest["row_count"], 100)
        self.assertTrue(os.path.exists(manifest["file_path"]))
        self.assertTrue(len(manifest["checksum_sha256"]) == 64)

        # Read back
        df_read = self.storage.read_dataset("TestBroker", "XAUUSD", "H1")
        self.assertEqual(len(df_read), 100)
        self.assertEqual(df_read["close"].iloc[-1], self.sample_df["close"].iloc[-1])

    def test_read_with_pushdown_filter(self):
        self.storage.write_dataset_atomic(
            broker_server="TestBroker",
            symbol="EURUSD",
            timeframe="M15",
            df=self.sample_df,
            version=1
        )
        # Filter middle 50 rows
        s_filter = "2026-01-02 00:00:00+00:00"
        e_filter = "2026-01-03 00:00:00+00:00"
        filtered_df = self.storage.read_dataset(
            "TestBroker", "EURUSD", "M15", start_time=s_filter, end_time=e_filter
        )
        self.assertTrue(len(filtered_df) > 0)
        self.assertTrue(len(filtered_df) < 100)

    def test_metadata_db_registration_and_ranges(self):
        self.metadata_db.register_dataset(
            dataset_id="TestBroker_BTCUSD_H1_v1",
            broker_server="TestBroker",
            symbol="BTCUSD",
            timeframe="H1",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-05T00:00:00Z",
            row_count=96,
            checksum="abc123sha",
            quality_score=99.0,
            file_path="/tmp/fake.parquet",
            file_size_bytes=12345,
            version=1
        )
        dataset = self.metadata_db.get_dataset("TestBroker_BTCUSD_H1_v1")
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset["row_count"], 96)

        ranges = self.metadata_db.get_available_ranges("TestBroker", "BTCUSD", "H1")
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0][0], "2026-01-01T00:00:00Z")

    def test_symbol_specs_persistence(self):
        specs = {
            "digits": 2,
            "point": 0.01,
            "tick_size": 0.01,
            "contract_size": 1.0,
            "margin_currency": "USD"
        }
        self.metadata_db.save_symbol_specs("TestBroker", "BTCUSD", specs)
        saved = self.metadata_db.get_symbol_specs("TestBroker", "BTCUSD")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["digits"], 2)


if __name__ == "__main__":
    unittest.main()
