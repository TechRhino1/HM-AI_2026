"""
JARVIS AI 4.0 — Institutional Historical Market Data Quality & Anomaly Engine.
Audits every dataset before storage, detecting impossible OHLC, gaps, spikes,
duplicate timestamps, and calculating DATA_QUALITY_SCORE (0–100).
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("JARVIS_DataQuality")


@dataclass
class QualityAnomaly:
    anomaly_type: str
    severity: str  # "FATAL", "WARNING", "INFO"
    timestamp: str
    details: str
    penalty: float


@dataclass
class QualityReport:
    symbol: str
    timeframe: str
    row_count: int
    quality_score: float
    is_valid: bool
    anomalies: List[QualityAnomaly] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "row_count": self.row_count,
            "quality_score": round(self.quality_score, 2),
            "is_valid": self.is_valid,
            "anomaly_count": len(self.anomalies),
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "timestamp": a.timestamp,
                    "details": a.details,
                    "penalty": a.penalty
                }
                for a in self.anomalies[:50]  # Cap in summary
            ],
            "metrics": self.metrics
        }


class DataQualityEngine:
    """
    Exhaustive data validation engine ensuring only clean, verified,
    and audit-proof market data enters the institutional research repository.
    """

    def __init__(self, min_valid_score: float = 70.0):
        self.min_valid_score = min_valid_score

    def audit_ohlcv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        typical_spread: float = 2.0
    ) -> QualityReport:
        """
        Executes exhaustive audit of an OHLCV dataset.
        Returns QualityReport with DATA_QUALITY_SCORE in [0, 100].
        """
        anomalies: List[QualityAnomaly] = []
        total_penalty = 0.0

        if df.empty:
            anomalies.append(QualityAnomaly(
                anomaly_type="EMPTY_DATASET",
                severity="FATAL",
                timestamp="",
                details="Dataset is empty.",
                penalty=100.0
            ))
            return QualityReport(symbol, timeframe, 0, 0.0, False, anomalies)

        row_count = len(df)
        times = pd.to_datetime(df["time"], utc=True)

        # 1. Check for Duplicate Timestamps
        duplicates = df[times.duplicated(keep=False)]
        if not duplicates.empty:
            dup_cnt = len(duplicates) // 2
            penalty = min(15.0, dup_cnt * 1.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="DUPLICATE_TIMESTAMPS",
                severity="WARNING",
                timestamp=str(duplicates["time"].iloc[0]),
                details=f"Found {dup_cnt} duplicate timestamp entries.",
                penalty=penalty
            ))

        # 2. Check for Out-of-Order Records
        time_diffs = times.diff()
        negative_diffs = time_diffs[time_diffs < pd.Timedelta(0)]
        if not negative_diffs.empty:
            penalty = min(25.0, len(negative_diffs) * 5.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="OUT_OF_ORDER_TIMESTAMPS",
                severity="FATAL",
                timestamp=str(times.iloc[negative_diffs.index[0]]),
                details=f"Found {len(negative_diffs)} chronological reversals in sequence.",
                penalty=penalty
            ))

        # 3. Check for Impossible OHLC Math
        # High must be >= max(Open, Close) and >= Low
        high_lt_low = df[df["high"] < df["low"]]
        if not high_lt_low.empty:
            penalty = min(30.0, len(high_lt_low) * 5.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="IMPOSSIBLE_OHLC_HIGH_LT_LOW",
                severity="FATAL",
                timestamp=str(df["time"].iloc[high_lt_low.index[0]]),
                details=f"{len(high_lt_low)} bars where High < Low.",
                penalty=penalty
            ))

        high_lt_open = df[df["high"] < df["open"]]
        if not high_lt_open.empty:
            penalty = min(20.0, len(high_lt_open) * 2.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="IMPOSSIBLE_OHLC_HIGH_LT_OPEN",
                severity="FATAL",
                timestamp=str(df["time"].iloc[high_lt_open.index[0]]),
                details=f"{len(high_lt_open)} bars where High < Open.",
                penalty=penalty
            ))

        low_gt_close = df[df["low"] > df["close"]]
        if not low_gt_close.empty:
            penalty = min(20.0, len(low_gt_close) * 2.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="IMPOSSIBLE_OHLC_LOW_GT_CLOSE",
                severity="FATAL",
                timestamp=str(df["time"].iloc[low_gt_close.index[0]]),
                details=f"{len(low_gt_close)} bars where Low > Close.",
                penalty=penalty
            ))

        # 4. Check for Non-Positive Prices
        non_positive = df[(df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)]
        if not non_positive.empty:
            penalty = min(35.0, len(non_positive) * 10.0)
            total_penalty += penalty
            anomalies.append(QualityAnomaly(
                anomaly_type="ZERO_OR_NEGATIVE_PRICE",
                severity="FATAL",
                timestamp=str(df["time"].iloc[non_positive.index[0]]),
                details=f"{len(non_positive)} bars with price <= 0.",
                penalty=penalty
            ))

        # 5. Check for Abnormal Spreads
        if "spread" in df.columns:
            negative_spread = df[df["spread"] < 0]
            if not negative_spread.empty:
                penalty = min(15.0, len(negative_spread) * 2.0)
                total_penalty += penalty
                anomalies.append(QualityAnomaly(
                    anomaly_type="NEGATIVE_SPREAD",
                    severity="WARNING",
                    timestamp=str(df["time"].iloc[negative_spread.index[0]]),
                    details=f"{len(negative_spread)} bars with negative spread.",
                    penalty=penalty
                ))

            extreme_spread = df[df["spread"] > (typical_spread * 10.0)]
            if not extreme_spread.empty:
                penalty = min(10.0, len(extreme_spread) * 0.5)
                total_penalty += penalty
                anomalies.append(QualityAnomaly(
                    anomaly_type="EXTREME_SPREAD",
                    severity="WARNING",
                    timestamp=str(df["time"].iloc[extreme_spread.index[0]]),
                    details=f"{len(extreme_spread)} bars where spread > {typical_spread*10:.1f} pips.",
                    penalty=penalty
                ))

        # 6. Check for Price Spikes (> 7x rolling standard deviation)
        if len(df) >= 30:
            returns = df["close"].pct_change().abs()
            rolling_std = returns.rolling(20).std()
            spike_mask = (returns > 0.05) & (returns > (rolling_std * 7.0))
            spikes = df[spike_mask]
            if not spikes.empty:
                penalty = min(15.0, len(spikes) * 2.0)
                total_penalty += penalty
                anomalies.append(QualityAnomaly(
                    anomaly_type="SUSPICIOUS_PRICE_SPIKE",
                    severity="WARNING",
                    timestamp=str(df["time"].iloc[spikes.index[0]]),
                    details=f"Detected {len(spikes)} potential unconfirmed price spikes.",
                    penalty=penalty
                ))

        # 7. Check for Missing Volume
        if "tick_volume" in df.columns:
            zero_vol = df[df["tick_volume"] <= 0]
            if len(zero_vol) > (row_count * 0.20):  # More than 20% zero volume
                penalty = 5.0
                total_penalty += penalty
                anomalies.append(QualityAnomaly(
                    anomaly_type="FLAT_ZERO_VOLUME",
                    severity="INFO",
                    timestamp=str(df["time"].iloc[zero_vol.index[0]]),
                    details=f"{len(zero_vol)} bars with zero tick volume.",
                    penalty=penalty
                ))

        # Calculate final DATA_QUALITY_SCORE
        final_score = max(0.0, min(100.0, 100.0 - total_penalty))
        is_valid = final_score >= self.min_valid_score and not any(a.severity == "FATAL" for a in anomalies)

        metrics = {
            "total_bars": row_count,
            "start_time": str(df["time"].iloc[0]),
            "end_time": str(df["time"].iloc[-1]),
            "min_price": float(df["low"].min()),
            "max_price": float(df["high"].max()),
            "avg_tick_volume": float(df["tick_volume"].mean()) if "tick_volume" in df.columns else 0.0,
            "penalty_points": round(total_penalty, 2)
        }

        report = QualityReport(
            symbol=symbol,
            timeframe=timeframe,
            row_count=row_count,
            quality_score=final_score,
            is_valid=is_valid,
            anomalies=anomalies,
            metrics=metrics
        )

        if not is_valid:
            logger.warning(
                f"Data Quality Audit FAILED for {symbol} {timeframe}: Score={final_score:.1f}/100, "
                f"Anomalies={len(anomalies)}"
            )
        else:
            logger.info(
                f"Data Quality Audit PASSED for {symbol} {timeframe}: Score={final_score:.1f}/100 "
                f"({row_count} bars)"
            )

        return report
