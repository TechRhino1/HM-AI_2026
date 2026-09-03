"""
JARVIS AI 4.0 — Historical Market Data Metadata & Indexing Engine.
Manages metadata, versioning, contiguous range tracking, and quality audit logs
in an institutional SQLite repository (data/metadata/metadata.db).
"""
import os
import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import threading

logger = logging.getLogger("JARVIS_HistoricalMetadata")


class MetadataDB:
    """
    Thread-safe SQLite metadata repository tracking versioned datasets,
    contiguous time ranges, broker contract specifications, and quality logs.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            db_dir = os.path.join(base_dir, "data", "metadata")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "metadata.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_tables(self):
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS datasets (
                        dataset_id TEXT PRIMARY KEY,
                        broker_server TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        row_count INTEGER NOT NULL,
                        checksum TEXT NOT NULL,
                        quality_score REAL NOT NULL,
                        schema_version TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size_bytes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_datasets_lookup 
                    ON datasets (broker_server, symbol, timeframe, version DESC);
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_ranges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_server TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        range_start TEXT NOT NULL,
                        range_end TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ranges_lookup 
                    ON data_ranges (broker_server, symbol, timeframe, range_start);
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_specs (
                        broker_server TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        digits INTEGER,
                        point REAL,
                        tick_size REAL,
                        tick_value REAL,
                        contract_size REAL,
                        margin_currency TEXT,
                        swap_long REAL,
                        swap_short REAL,
                        swap_mode INTEGER,
                        trade_stops_level INTEGER,
                        trade_freeze_level INTEGER,
                        timezone TEXT,
                        specs_json TEXT,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (broker_server, symbol)
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS quality_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dataset_id TEXT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        anomaly_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        details TEXT,
                        action_taken TEXT,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_quality_lookup 
                    ON quality_audit_log (symbol, timeframe, created_at DESC);
                """)

    def register_dataset(
        self,
        dataset_id: str,
        broker_server: str,
        symbol: str,
        timeframe: str,
        start_time: str,
        end_time: str,
        row_count: int,
        checksum: str,
        quality_score: float,
        file_path: str,
        file_size_bytes: int,
        schema_version: str = "1.0",
        version: int = 1,
    ) -> Dict[str, Any]:
        """Registers or updates a versioned dataset in metadata repository."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    INSERT INTO datasets (
                        dataset_id, broker_server, symbol, timeframe,
                        start_time, end_time, row_count, checksum,
                        quality_score, schema_version, version, file_path,
                        file_size_bytes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dataset_id) DO UPDATE SET
                        start_time=excluded.start_time,
                        end_time=excluded.end_time,
                        row_count=excluded.row_count,
                        checksum=excluded.checksum,
                        quality_score=excluded.quality_score,
                        file_path=excluded.file_path,
                        file_size_bytes=excluded.file_size_bytes,
                        updated_at=excluded.updated_at;
                """, (
                    dataset_id, broker_server, symbol, timeframe,
                    start_time, end_time, row_count, checksum,
                    quality_score, schema_version, version, file_path,
                    file_size_bytes, now, now
                ))

                # Update data_ranges table for contiguous range querying
                conn.execute("""
                    DELETE FROM data_ranges WHERE dataset_id = ?;
                """, (dataset_id,))
                conn.execute("""
                    INSERT INTO data_ranges (
                        broker_server, symbol, timeframe, range_start, range_end, dataset_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (broker_server, symbol, timeframe, start_time, end_time, dataset_id, now))

        logger.info(
            f"Registered Dataset [{dataset_id}] {symbol} {timeframe} ({row_count} bars, "
            f"score={quality_score:.1f}, {start_time} -> {end_time})"
        )
        return {
            "dataset_id": dataset_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "rows": row_count,
            "version": version,
            "checksum": checksum,
            "quality_score": quality_score
        }

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_latest_dataset(
        self, broker_server: str, symbol: str, timeframe: str
    ) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM datasets 
            WHERE broker_server = ? AND symbol = ? AND timeframe = ?
            ORDER BY version DESC LIMIT 1;
        """, (broker_server, symbol, timeframe))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_datasets(
        self, broker_server: Optional[str] = None, symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        query = "SELECT * FROM datasets WHERE 1=1"
        params = []
        if broker_server:
            query += " AND broker_server = ?"
            params.append(broker_server)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        query += " ORDER BY symbol, timeframe, version DESC"
        cursor.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]

    def get_available_ranges(
        self, broker_server: str, symbol: str, timeframe: str
    ) -> List[Tuple[str, str]]:
        """Returns ordered list of (range_start, range_end) tuples."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT range_start, range_end FROM data_ranges
            WHERE broker_server = ? AND symbol = ? AND timeframe = ?
            ORDER BY range_start ASC;
        """, (broker_server, symbol, timeframe))
        return [(r["range_start"], r["range_end"]) for r in cursor.fetchall()]

    def save_symbol_specs(self, broker_server: str, symbol: str, specs: Dict[str, Any]):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    INSERT INTO symbol_specs (
                        broker_server, symbol, digits, point, tick_size, tick_value,
                        contract_size, margin_currency, swap_long, swap_short,
                        swap_mode, trade_stops_level, trade_freeze_level, timezone,
                        specs_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(broker_server, symbol) DO UPDATE SET
                        digits=excluded.digits,
                        point=excluded.point,
                        tick_size=excluded.tick_size,
                        tick_value=excluded.tick_value,
                        contract_size=excluded.contract_size,
                        margin_currency=excluded.margin_currency,
                        swap_long=excluded.swap_long,
                        swap_short=excluded.swap_short,
                        swap_mode=excluded.swap_mode,
                        trade_stops_level=excluded.trade_stops_level,
                        trade_freeze_level=excluded.trade_freeze_level,
                        timezone=excluded.timezone,
                        specs_json=excluded.specs_json,
                        updated_at=excluded.updated_at;
                """, (
                    broker_server, symbol,
                    specs.get("digits", 5),
                    specs.get("point", 0.00001),
                    specs.get("tick_size", specs.get("point", 0.00001)),
                    specs.get("tick_value", 1.0),
                    specs.get("contract_size", 100000.0),
                    specs.get("margin_currency", "USD"),
                    specs.get("swap_long", 0.0),
                    specs.get("swap_short", 0.0),
                    specs.get("swap_mode", 0),
                    specs.get("trade_stops_level", 0),
                    specs.get("trade_freeze_level", 0),
                    specs.get("timezone", "UTC"),
                    json.dumps(specs),
                    now
                ))

    def get_symbol_specs(self, broker_server: str, symbol: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM symbol_specs WHERE broker_server = ? AND symbol = ?
        """, (broker_server, symbol))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        if res.get("specs_json"):
            try:
                res["specs"] = json.loads(res["specs_json"])
            except Exception:
                res["specs"] = {}
        return res

    def log_quality_event(
        self,
        dataset_id: Optional[str],
        symbol: str,
        timeframe: str,
        timestamp: str,
        anomaly_type: str,
        severity: str,
        details: str,
        action_taken: str = "LOGGED"
    ):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    INSERT INTO quality_audit_log (
                        dataset_id, symbol, timeframe, timestamp,
                        anomaly_type, severity, details, action_taken, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    dataset_id, symbol, timeframe, timestamp,
                    anomaly_type, severity, details, action_taken, now
                ))

    def get_quality_logs(
        self, symbol: Optional[str] = None, timeframe: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        query = "SELECT * FROM quality_audit_log WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]

    def get_storage_stats(self) -> Dict[str, Any]:
        """Calculates total datasets, rows, and storage bytes."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_datasets,
                COALESCE(SUM(row_count), 0) as total_rows,
                COALESCE(SUM(file_size_bytes), 0) as total_bytes,
                AVG(quality_score) as avg_quality
            FROM datasets;
        """)
        row = cursor.fetchone()
        db_file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        return {
            "total_datasets": row["total_datasets"] if row else 0,
            "total_rows": row["total_rows"] if row else 0,
            "total_bytes": (row["total_bytes"] if row else 0) + db_file_size,
            "avg_quality_score": round(row["avg_quality"], 2) if row and row["avg_quality"] else 100.0,
            "db_path": self.db_path
        }
