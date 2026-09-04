"""
JARVIS AI 4.0 — Local Historical Data Lake Storage Engine.
Handles atomic Parquet writes, schema normalization, versioned files,
SHA256 checksum generation, and fast filtered reads.
"""
import os
import uuid
import hashlib
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger("JARVIS_HistoricalStorage")

OHLCV_SCHEMA = pa.schema([
    ("time", pa.timestamp("ns", tz="UTC")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
    ("tick_volume", pa.int64()),
    ("spread", pa.float64()),
    ("real_volume", pa.int64()),
])

TICK_SCHEMA = pa.schema([
    ("time", pa.timestamp("ns", tz="UTC")),
    ("bid", pa.float64()),
    ("ask", pa.float64()),
    ("last", pa.float64()),
    ("volume", pa.float64()),
    ("flags", pa.int64()),
])


class StorageEngine:
    """
    Manages physical storage of historical market data in Parquet format,
    guaranteeing atomic writes, checksum verification, and structured data layout.
    """

    def __init__(self, base_data_dir: Optional[str] = None):
        if base_data_dir is None:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.base_dir = os.path.join(root_dir, "data")
        else:
            self.base_dir = base_data_dir

        self.market_dir = os.path.join(self.base_dir, "market")
        self.manifests_dir = os.path.join(self.base_dir, "manifests")
        self.snapshots_dir = os.path.join(self.base_dir, "snapshots")
        self.raw_dir = os.path.join(self.base_dir, "raw")

        for d in [self.market_dir, self.manifests_dir, self.snapshots_dir, self.raw_dir]:
            os.makedirs(d, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Sanitizes directory names (e.g. replaces spaces, colons, slashes)."""
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)

    def get_dataset_dir(self, broker_server: str, symbol: str, timeframe: str) -> str:
        b_clean = self._sanitize_name(broker_server)
        s_clean = self._sanitize_name(symbol)
        tf_clean = self._sanitize_name(timeframe.upper())
        d = os.path.join(self.market_dir, b_clean, s_clean, tf_clean)
        os.makedirs(d, exist_ok=True)
        return d

    def normalize_ohlcv_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardizes column names, dtypes, and UTC timestamps."""
        clean_df = df.copy()

        # Timestamp normalization
        if "time" not in clean_df.columns:
            if isinstance(clean_df.index, pd.DatetimeIndex):
                clean_df["time"] = clean_df.index
            else:
                for col in ["datetime", "date", "timestamp"]:
                    if col in clean_df.columns:
                        clean_df.rename(columns={col: "time"}, inplace=True)
                        break

        if "time" not in clean_df.columns:
            raise ValueError("Input DataFrame missing 'time' column or DatetimeIndex.")

        clean_df["time"] = pd.to_datetime(clean_df["time"], utc=True)

        # Standard OHLCV mapping
        col_map = {
            "Open": "open", "High": "high", "Low": "low", "Close": "close",
            "Tick_Volume": "tick_volume", "Volume": "tick_volume", "vol": "tick_volume",
            "Spread": "spread", "Real_Volume": "real_volume"
        }
        for old_c, new_c in col_map.items():
            if old_c in clean_df.columns and new_c not in clean_df.columns:
                clean_df.rename(columns={old_c: new_c}, inplace=True)

        required_cols = ["open", "high", "low", "close"]
        for rc in required_cols:
            if rc not in clean_df.columns:
                raise ValueError(f"Missing required OHLC column: '{rc}'")

        # Handle volume and tick_volume seamlessly with NaN filling
        if "tick_volume" not in clean_df.columns:
            clean_df["tick_volume"] = 1
        if "volume" not in clean_df.columns:
            clean_df["volume"] = clean_df["tick_volume"]

        clean_df["volume"] = clean_df["volume"].fillna(clean_df["tick_volume"]).fillna(1.0).astype(float)
        clean_df["tick_volume"] = clean_df["tick_volume"].fillna(clean_df["volume"]).fillna(1).astype(np.int64)

        if "spread" not in clean_df.columns:
            clean_df["spread"] = 0.0
        else:
            clean_df["spread"] = clean_df["spread"].fillna(0.0).astype(float)

        if "real_volume" not in clean_df.columns:
            clean_df["real_volume"] = 0
        else:
            clean_df["real_volume"] = clean_df["real_volume"].fillna(0).astype(np.int64)

        # Type enforcement
        clean_df["open"] = clean_df["open"].astype(float)
        clean_df["high"] = clean_df["high"].astype(float)
        clean_df["low"] = clean_df["low"].astype(float)
        clean_df["close"] = clean_df["close"].astype(float)

        # Deduplicate by timestamp and sort ascending
        clean_df = clean_df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
        return clean_df[["time", "open", "high", "low", "close", "volume", "tick_volume", "spread", "real_volume"]]

    def compute_file_checksum(self, filepath: str) -> str:
        """Computes SHA256 checksum of file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def write_dataset_atomic(
        self,
        broker_server: str,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        version: int = 1,
        quality_score: float = 100.0,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Atomically saves normalized DataFrame to Parquet with SHA256 verification
        and companion JSON manifest.
        """
        clean_df = self.normalize_ohlcv_dataframe(df)
        if clean_df.empty:
            raise ValueError(f"Cannot save empty DataFrame for {symbol} {timeframe}")

        target_dir = self.get_dataset_dir(broker_server, symbol, timeframe)
        b_clean = self._sanitize_name(broker_server)
        s_clean = self._sanitize_name(symbol)
        tf_clean = self._sanitize_name(timeframe.upper())

        dataset_id = f"{b_clean}_{s_clean}_{tf_clean}_v{version}"
        final_parquet_path = os.path.join(target_dir, f"{dataset_id}.parquet")
        tmp_parquet_path = os.path.join(target_dir, f".tmp_{uuid.uuid4().hex}.parquet")

        start_time_iso = clean_df["time"].iloc[0].isoformat()
        end_time_iso = clean_df["time"].iloc[-1].isoformat()
        row_count = len(clean_df)

        try:
            # Convert to PyArrow Table with explicit schema
            table = pa.Table.from_pandas(clean_df, schema=OHLCV_SCHEMA, preserve_index=False)
            
            # Write to temporary file with snappy compression
            pq.write_table(
                table,
                tmp_parquet_path,
                compression="SNAPPY",
                row_group_size=50000,
                version="2.6"
            )

            # Checksum verification
            checksum = self.compute_file_checksum(tmp_parquet_path)
            file_size = os.path.getsize(tmp_parquet_path)

            # Atomic swap to destination
            os.replace(tmp_parquet_path, final_parquet_path)

            # Write manifest JSON
            manifest_data = {
                "dataset_id": dataset_id,
                "broker_server": broker_server,
                "symbol": symbol,
                "timeframe": timeframe,
                "start_time": start_time_iso,
                "end_time": end_time_iso,
                "row_count": row_count,
                "file_size_bytes": file_size,
                "checksum_sha256": checksum,
                "quality_score": quality_score,
                "schema_version": "1.0",
                "version": version,
                "file_path": final_parquet_path,
                "extra": extra_metadata or {}
            }
            manifest_file = os.path.join(self.manifests_dir, f"{dataset_id}.manifest.json")
            with open(manifest_file, "w", encoding="utf-8") as mf:
                json.dump(manifest_data, mf, indent=2)

            logger.info(
                f"Atomic Parquet Saved: {dataset_id} ({row_count} rows, {file_size/1024:.1f} KB, "
                f"SHA256={checksum[:8]}...)"
            )
            return manifest_data

        except Exception as e:
            if os.path.exists(tmp_parquet_path):
                os.remove(tmp_parquet_path)
            raise IOError(f"Failed to write atomic dataset for {symbol} {timeframe}: {e}") from e

    def read_dataset(
        self,
        broker_server: str,
        symbol: str,
        timeframe: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        columns: Optional[List[str]] = None,
        version: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Reads historical dataset with optional pushdown filtering by date range.
        If version is omitted, the latest version is loaded.
        """
        target_dir = self.get_dataset_dir(broker_server, symbol, timeframe)
        b_clean = self._sanitize_name(broker_server)
        s_clean = self._sanitize_name(symbol)
        tf_clean = self._sanitize_name(timeframe.upper())

        if version is not None:
            dataset_id = f"{b_clean}_{s_clean}_{tf_clean}_v{version}"
            parquet_path = os.path.join(target_dir, f"{dataset_id}.parquet")
        else:
            # Find newest file in target_dir
            parquet_files = [f for f in os.listdir(target_dir) if f.endswith(".parquet") and not f.startswith(".tmp_")]
            if not parquet_files:
                return pd.DataFrame()
            parquet_files.sort(reverse=True)
            parquet_path = os.path.join(target_dir, parquet_files[0])

        if not os.path.exists(parquet_path):
            return pd.DataFrame()

        # Build PyArrow filters for date range pushdown
        filters = []
        if start_time is not None:
            ts_start = pd.to_datetime(start_time, utc=True).to_pydatetime()
            filters.append(("time", ">=", ts_start))
        if end_time is not None:
            ts_end = pd.to_datetime(end_time, utc=True).to_pydatetime()
            filters.append(("time", "<=", ts_end))

        pyarrow_filter = filters if filters else None

        table = pq.read_table(
            parquet_path,
            columns=columns,
            filters=pyarrow_filter
        )
        df = table.to_pandas()
        return df

    def save_raw_backup(
        self, broker_server: str, symbol: str, timeframe: str, raw_data_bytes: bytes, suffix: str = ".bin"
    ) -> str:
        """Saves immutable raw MT5 buffer before any normalization for auditability."""
        b_clean = self._sanitize_name(broker_server)
        s_clean = self._sanitize_name(symbol)
        tf_clean = self._sanitize_name(timeframe.upper())
        raw_path = os.path.join(self.raw_dir, f"{b_clean}_{s_clean}_{tf_clean}_{uuid.uuid4().hex[:8]}{suffix}")
        with open(raw_path, "wb") as f:
            f.write(raw_data_bytes)
        return raw_path

    def create_snapshot(
        self, broker_server: str, symbol: str, timeframe: str, snapshot_name: str
    ) -> str:
        """Creates an immutable frozen snapshot copy for an audit-proof backtest run."""
        df = self.read_dataset(broker_server, symbol, timeframe)
        if df.empty:
            raise ValueError(f"No data available to create snapshot for {symbol} {timeframe}")
        s_path = os.path.join(self.snapshots_dir, f"{snapshot_name}.parquet")
        table = pa.Table.from_pandas(df, schema=OHLCV_SCHEMA, preserve_index=False)
        pq.write_table(table, s_path, compression="SNAPPY")
        logger.info(f"Snapshot Created: {snapshot_name} ({len(df)} rows) -> {s_path}")
        return s_path
