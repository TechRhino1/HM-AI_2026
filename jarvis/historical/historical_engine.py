"""
JARVIS AI 4.0 — Unified Backtest & Research Historical Market Data Engine.
Provides a single, institutional API for querying, downloading, validating,
and versioning historical market data across all strategies, backtests, and replay sessions.
"""
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import pandas as pd

from jarvis.historical.storage import StorageEngine
from jarvis.historical.metadata_db import MetadataDB
from jarvis.historical.quality_engine import DataQualityEngine
from jarvis.historical.acquisition import AcquisitionEngine
from jarvis.historical.regime_tagger import HistoricalRegimeTagger

logger = logging.getLogger("JARVIS_HistoricalEngine")


class HistoricalDataEngine:
    """
    Unified institutional historical market data engine for JARVIS 4.0.
    Ensures data is downloaded once from MT5, validated, versioned, and reused everywhere.
    """

    def __init__(
        self,
        base_data_dir: Optional[str] = None,
        db_path: Optional[str] = None
    ):
        self.storage = StorageEngine(base_data_dir=base_data_dir)
        self.metadata_db = MetadataDB(db_path=db_path)
        self.quality_engine = DataQualityEngine()
        self.acquisition = AcquisitionEngine(
            storage=self.storage,
            metadata_db=self.metadata_db,
            quality_engine=self.quality_engine
        )
        self.regime_tagger = HistoricalRegimeTagger()

        # In-Memory LRU Cache: {cache_key: (DataFrame, timestamp)}
        self._lru_cache: Dict[str, Tuple[pd.DataFrame, float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def broker_server(self) -> str:
        return self.acquisition.broker_server

    def _get_cache_key(self, symbol: str, timeframe: str, start: Optional[str], end: Optional[str]) -> str:
        return f"{self.broker_server}:{symbol.upper()}:{timeframe.upper()}:{start}:{end}"

    def get_market_data(
        self,
        symbol: str,
        timeframe: str = "H1",
        start: Optional[Any] = None,
        end: Optional[Any] = None,
        num_bars: Optional[int] = None,
        with_regimes: bool = False,
        auto_download: bool = True
    ) -> pd.DataFrame:
        """
        Primary data query method.
        First checks in-memory LRU cache -> then checks local Parquet lake -> downloads missing delta if needed.
        """
        sym_u = symbol.upper()
        tf_u = timeframe.upper()

        # Normalize start/end
        start_str = pd.to_datetime(start, utc=True).isoformat() if start else None
        end_str = pd.to_datetime(end, utc=True).isoformat() if end else None

        cache_key = self._get_cache_key(sym_u, tf_u, start_str, end_str)
        if cache_key in self._lru_cache:
            self._cache_hits += 1
            cached_df, _ = self._lru_cache[cache_key]
            if num_bars is not None and len(cached_df) > num_bars:
                return cached_df.iloc[-num_bars:].copy()
            return cached_df.copy()

        self._cache_misses += 1

        # Check local Parquet storage
        df = self.storage.read_dataset(
            broker_server=self.broker_server,
            symbol=sym_u,
            timeframe=tf_u,
            start_time=start_str,
            end_time=end_str
        )

        # If data is insufficient and auto_download is True, sync from MT5
        needs_download = df.empty
        if not df.empty and num_bars is not None and len(df) < num_bars:
            needs_download = True

        if needs_download and auto_download:
            req_end = pd.to_datetime(end, utc=True).to_pydatetime() if end else datetime.now(timezone.utc)
            if start:
                req_start = pd.to_datetime(start, utc=True).to_pydatetime()
            elif num_bars:
                # Estimate start based on num_bars
                hours = max(24, num_bars * (4 if tf_u == "H4" else (24 if tf_u == "D1" else 1)))
                req_start = req_end - timedelta(hours=hours)
            else:
                req_start = req_end - timedelta(days=180)  # Default 6 months

            self.acquisition.sync_range(sym_u, tf_u, req_start, req_end)
            df = self.storage.read_dataset(
                broker_server=self.broker_server,
                symbol=sym_u,
                timeframe=tf_u,
                start_time=start_str,
                end_time=end_str
            )

        if df.empty:
            logger.warning(f"No historical data available for {sym_u} {tf_u}")
            return pd.DataFrame()

        if with_regimes:
            df = self.regime_tagger.tag_regimes(df)

        if num_bars is not None and len(df) > num_bars:
            res_df = df.iloc[-num_bars:].copy().reset_index(drop=True)
        else:
            res_df = df.copy().reset_index(drop=True)

        # Store in LRU Cache (cap at 20 DataFrames in memory)
        if len(self._lru_cache) >= 20:
            oldest_key = min(self._lru_cache.keys(), key=lambda k: self._lru_cache[k][1])
            self._lru_cache.pop(oldest_key, None)
        self._lru_cache[cache_key] = (res_df.copy(), time.time())

        return res_df

    def get_ohlcv(
        self, symbol: str, timeframe: str = "H1", start: Optional[Any] = None, end: Optional[Any] = None, num_bars: Optional[int] = None
    ) -> pd.DataFrame:
        return self.get_market_data(symbol, timeframe, start=start, end=end, num_bars=num_bars, with_regimes=False)

    def get_spread(
        self, symbol: str, timeframe: str = "H1", start: Optional[Any] = None, end: Optional[Any] = None
    ) -> pd.Series:
        df = self.get_market_data(symbol, timeframe, start=start, end=end)
        if df.empty or "spread" not in df.columns:
            return pd.Series(dtype=float)
        return df.set_index("time")["spread"]

    def get_symbol_metadata(self, symbol: str) -> Dict[str, Any]:
        specs = self.metadata_db.get_symbol_specs(self.broker_server, symbol.upper())
        if not specs:
            specs = self.acquisition.fetch_contract_specs(symbol.upper())
        return specs

    def has_data(
        self, symbol: str, timeframe: str = "H1", start: Optional[Any] = None, end: Optional[Any] = None, num_bars: Optional[int] = None
    ) -> bool:
        df = self.storage.read_dataset(
            broker_server=self.broker_server,
            symbol=symbol.upper(),
            timeframe=timeframe.upper()
        )
        if df.empty:
            return False
        if num_bars and len(df) < num_bars:
            return False
        return True

    def get_available_range(self, symbol: str, timeframe: str = "H1") -> List[Tuple[str, str]]:
        return self.metadata_db.get_available_ranges(self.broker_server, symbol.upper(), timeframe.upper())

    def get_missing_ranges(
        self, symbol: str, timeframe: str, start: Any, end: Any
    ) -> List[Tuple[datetime, datetime]]:
        s_dt = pd.to_datetime(start, utc=True).to_pydatetime()
        e_dt = pd.to_datetime(end, utc=True).to_pydatetime()
        return self.acquisition.calculate_missing_ranges(symbol.upper(), timeframe.upper(), s_dt, e_dt)

    def download(
        self, symbol: str, timeframe: str = "H1", start: Optional[Any] = None, end: Optional[Any] = None, force: bool = False
    ) -> Dict[str, Any]:
        req_end = pd.to_datetime(end, utc=True).to_pydatetime() if end else datetime.now(timezone.utc)
        req_start = pd.to_datetime(start, utc=True).to_pydatetime() if start else (req_end - timedelta(days=180))
        return self.acquisition.sync_range(symbol.upper(), timeframe.upper(), req_start, req_end, force_redownload=force)

    def download_missing(
        self, symbol: str, timeframe: str, start: Any, end: Any
    ) -> Dict[str, Any]:
        return self.download(symbol, timeframe, start=start, end=end, force=False)

    def update_latest(self, symbol: str, timeframe: str = "H1", days: int = 7) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        return self.download(symbol, timeframe, start=start, end=now, force=False)

    def validate(self, symbol: str, timeframe: str = "H1") -> Dict[str, Any]:
        df = self.storage.read_dataset(self.broker_server, symbol.upper(), timeframe.upper())
        if df.empty:
            return {"status": "EMPTY", "quality_score": 0.0, "is_valid": False}
        rep = self.quality_engine.audit_ohlcv(df, symbol.upper(), timeframe.upper())
        return rep.to_dict()

    def repair(self, symbol: str, timeframe: str = "H1") -> Dict[str, Any]:
        """Cleans and rewrites corrupted records by deduplicating and re-sorting."""
        df = self.storage.read_dataset(self.broker_server, symbol.upper(), timeframe.upper())
        if df.empty:
            return {"status": "EMPTY"}
        clean_df = self.storage.normalize_ohlcv_dataframe(df)
        rep = self.quality_engine.audit_ohlcv(clean_df, symbol.upper(), timeframe.upper())
        latest = self.metadata_db.get_latest_dataset(self.broker_server, symbol.upper(), timeframe.upper())
        v = (latest["version"] + 1) if latest else 1
        manifest = self.storage.write_dataset_atomic(
            broker_server=self.broker_server,
            symbol=symbol.upper(),
            timeframe=timeframe.upper(),
            df=clean_df,
            version=v,
            quality_score=rep.quality_score
        )
        self.metadata_db.register_dataset(
            dataset_id=manifest["dataset_id"],
            broker_server=self.broker_server,
            symbol=symbol.upper(),
            timeframe=timeframe.upper(),
            start_time=manifest["start_time"],
            end_time=manifest["end_time"],
            row_count=manifest["row_count"],
            checksum=manifest["checksum_sha256"],
            quality_score=rep.quality_score,
            file_path=manifest["file_path"],
            file_size_bytes=manifest["file_size_bytes"],
            version=v
        )
        return {"status": "REPAIRED", "version": v, "quality_score": rep.quality_score, "rows": manifest["row_count"]}

    def create_snapshot(self, symbol: str, timeframe: str = "H1", snapshot_name: Optional[str] = None) -> str:
        s_name = snapshot_name or f"{symbol.upper()}_{timeframe.upper()}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        return self.storage.create_snapshot(self.broker_server, symbol.upper(), timeframe.upper(), s_name)

    def get_dataset_version(self, symbol: str, timeframe: str = "H1") -> Optional[int]:
        meta = self.metadata_db.get_latest_dataset(self.broker_server, symbol.upper(), timeframe.upper())
        return meta["version"] if meta else None

    def list_datasets(self, symbol: Optional[str] = None, timeframe: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.metadata_db.list_datasets(broker_server=self.broker_server, symbol=symbol, timeframe=timeframe)

    def get_engine_stats(self) -> Dict[str, Any]:
        stats = self.metadata_db.get_storage_stats()
        total_queries = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_queries * 100.0) if total_queries > 0 else 100.0
        stats.update({
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate_pct": round(hit_rate, 2),
            "broker_server": self.broker_server,
            "in_memory_cached_datasets": len(self._lru_cache)
        })
        return stats


# Global Singleton Instance
HISTORICAL_DATA_ENGINE = HistoricalDataEngine()
