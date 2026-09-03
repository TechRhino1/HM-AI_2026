"""
Unit tests for Historical Data Range Detection, Incremental Acquisition, and LRU Cache.
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from jarvis.historical.storage import StorageEngine
from jarvis.historical.metadata_db import MetadataDB
from jarvis.historical.quality_engine import DataQualityEngine
from jarvis.historical.acquisition import AcquisitionEngine
from jarvis.historical.historical_engine import HistoricalDataEngine


class TestHistoricalAcquisitionAndEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage = StorageEngine(base_data_dir=os.path.join(self.test_dir, "data"))
        self.metadata_db = MetadataDB(db_path=os.path.join(self.test_dir, "metadata", "test.db"))
        self.quality_engine = DataQualityEngine()
        self.acq = AcquisitionEngine(self.storage, self.metadata_db, self.quality_engine)
        self.engine = HistoricalDataEngine(
            base_data_dir=os.path.join(self.test_dir, "data"),
            db_path=os.path.join(self.test_dir, "metadata", "test.db")
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_missing_ranges_empty_repository(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, tzinfo=timezone.utc)
        missing = self.acq.calculate_missing_ranges("XAUUSD", "H1", start, end)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0], (start, end))

    def test_missing_ranges_fully_covered(self):
        # Register a 6-month dataset
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, tzinfo=timezone.utc)
        self.metadata_db.register_dataset(
            dataset_id="test_xau_h1",
            broker_server=self.acq.broker_server,
            symbol="XAUUSD",
            timeframe="H1",
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            row_count=3000,
            checksum="fake",
            quality_score=100.0,
            file_path="/tmp/fake.parquet",
            file_size_bytes=1000
        )

        # Request subset within [2026-01-01, 2026-06-30]
        req_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        req_end = datetime(2026, 5, 1, tzinfo=timezone.utc)
        missing = self.acq.calculate_missing_ranges("XAUUSD", "H1", req_start, req_end)
        self.assertEqual(len(missing), 0)

    def test_missing_ranges_extension(self):
        # Existing range: Jan 1 -> Jun 30
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, tzinfo=timezone.utc)
        self.metadata_db.register_dataset(
            dataset_id="test_xau_h1",
            broker_server=self.acq.broker_server,
            symbol="XAUUSD",
            timeframe="H1",
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            row_count=3000,
            checksum="fake",
            quality_score=100.0,
            file_path="/tmp/fake.parquet",
            file_size_bytes=1000
        )

        # Request Jan 1 -> Aug 31
        req_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        req_end = datetime(2026, 8, 31, tzinfo=timezone.utc)
        missing = self.acq.calculate_missing_ranges("XAUUSD", "H1", req_start, req_end)
        # Should only identify [Jun 30, Aug 31] as missing!
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0][0], end)
        self.assertEqual(missing[0][1], req_end)

    def test_historical_engine_lru_cache_reuse(self):
        # Create and save a dataset
        dates = pd.date_range("2026-01-01", periods=100, freq="1h", tz="UTC")
        df = pd.DataFrame({
            "time": dates,
            "open": np.linspace(2000, 2050, 100),
            "high": np.linspace(2005, 2055, 100),
            "low": np.linspace(1995, 2045, 100),
            "close": np.linspace(2002, 2052, 100),
            "tick_volume": [100] * 100,
            "spread": [2.0] * 100,
            "real_volume": [0] * 100
        })
        self.engine.storage.write_dataset_atomic(
            broker_server=self.engine.broker_server,
            symbol="BTCUSD",
            timeframe="H1",
            df=df,
            version=1
        )
        self.engine.metadata_db.register_dataset(
            dataset_id=f"{self.engine.broker_server}_BTCUSD_H1_v1",
            broker_server=self.engine.broker_server,
            symbol="BTCUSD",
            timeframe="H1",
            start_time=df["time"].iloc[0].isoformat(),
            end_time=df["time"].iloc[-1].isoformat(),
            row_count=100,
            checksum="test",
            quality_score=100.0,
            file_path="/fake",
            file_size_bytes=100
        )

        # 1st query: Cache Miss
        df1 = self.engine.get_market_data("BTCUSD", "H1", auto_download=False)
        self.assertEqual(len(df1), 100)
        self.assertEqual(self.engine._cache_misses, 1)
        self.assertEqual(self.engine._cache_hits, 0)

        # 2nd query: Cache Hit (Zero disk read!)
        df2 = self.engine.get_market_data("BTCUSD", "H1", auto_download=False)
        self.assertEqual(len(df2), 100)
        self.assertEqual(self.engine._cache_misses, 1)
        self.assertEqual(self.engine._cache_hits, 1)


if __name__ == "__main__":
    unittest.main()
