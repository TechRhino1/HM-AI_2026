"""
JARVIS AI 3.0 — Multi-Timeframe Data Feed Engine.
Provides thread-safe, timeout-guarded OHLCV data streaming from MT5 with realistic synthetic fallback generation.
"""
import time
import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
from jarvis.application.timeout_guard import TimeoutGuard

logger = logging.getLogger("JARVIS_DataFeed")

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_M1")) else 1,
    "M5": mt5.TIMEFRAME_M5 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_M5")) else 5,
    "M15": mt5.TIMEFRAME_M15 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_M15")) else 15,
    "M30": mt5.TIMEFRAME_M30 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_M30")) else 30,
    "H1": mt5.TIMEFRAME_H1 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_H1")) else 16385,
    "H4": mt5.TIMEFRAME_H4 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_H4")) else 16388,
    "D1": mt5.TIMEFRAME_D1 if (MT5_AVAILABLE and hasattr(mt5, "TIMEFRAME_D1")) else 16408,
}

class DataFeedEngine:
    def __init__(self, mt5_client: Any = None, timeout_sec: float = 3.0):
        self.mt5_client = mt5_client
        self.timeout_sec = timeout_sec
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_sec = 2.0

    def fetch_rates(self, symbol: str, timeframe: str = "H1", num_bars: int = 300, include_current_bar: bool = False) -> pd.DataFrame:
        cache_key = f"{symbol}_{timeframe}_{num_bars}_{include_current_bar}"
        now = time.time()
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl_sec:
                return entry["df"]

        def _fetch():
            if not MT5_AVAILABLE or self.mt5_client is None or getattr(self.mt5_client, "mode", "dry_run") == "dry_run":
                df = self._generate_realistic_rates(symbol, timeframe, num_bars)
                df.attrs["data_source"] = "SYNTHETIC_FALLBACK"
                return df

            resolved_sym = self.mt5_client.resolve_symbol_name(symbol) if hasattr(self.mt5_client, "resolve_symbol_name") else symbol
            mt5_tf = TF_MAP.get(timeframe, 16385)
            start_pos = 0 if include_current_bar else 1
            rates = mt5.copy_rates_from_pos(resolved_sym, mt5_tf, start_pos, num_bars)
            if rates is None or len(rates) == 0:
                # Fallback to pos 0 if start_pos returns empty
                rates = mt5.copy_rates_from_pos(resolved_sym, mt5_tf, 0, num_bars)
            if rates is None or len(rates) == 0:
                logger.warning(f"MT5 returned 0 rates for {symbol} ({timeframe}). Falling back to synthetic rates.")
                df = self._generate_realistic_rates(symbol, timeframe, num_bars)
                df.attrs["data_source"] = "SYNTHETIC_FALLBACK"
                return df

            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.rename(columns={"tick_volume": "volume"}, inplace=True)
            res_df = df[["time", "open", "high", "low", "close", "volume"]].copy()
            res_df.attrs["data_source"] = "LIVE_MT5"
            return res_df


        def _fallback_gen():
            df = self._generate_realistic_rates(symbol, timeframe, num_bars)
            df.attrs["data_source"] = "SYNTHETIC_FALLBACK"
            return df

        df_result = TimeoutGuard.run_sync(
            _fetch,
            timeout_sec=self.timeout_sec,
            default=_fallback_gen,
            task_name=f"DataFeed_fetch_{symbol}_{timeframe}"
        )

        if "data_source" not in df_result.attrs:
            df_result.attrs["data_source"] = "SYNTHETIC_FALLBACK"

        self._cache[cache_key] = {"df": df_result, "timestamp": now}
        return df_result

    def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: Optional[Dict[str, str]] = None,
        num_bars: int = 250
    ) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = {
                "macro": "D1",
                "context": "H4",
                "primary": "H1",
                "setup": "M15",
                "timing": "M5"
            }

        result = {}
        for role, tf in timeframes.items():
            result[role] = self.fetch_rates(symbol, timeframe=tf, num_bars=num_bars)
        return result

    def _generate_realistic_rates(self, symbol: str, timeframe: str, num_bars: int) -> pd.DataFrame:
        """Generates realistic institutional market price series with trend cycles, liquidity sweeps, and volatility clusters."""
        import zlib
        seed = zlib.crc32(f"{symbol.upper()}_{timeframe}".encode("utf-8"))
        np.random.seed(seed)
        
        base_price = 2400.0 if any(k in symbol.upper() for k in ["XAU", "GOLD"]) else (
            1.0850 if "EUR" in symbol.upper() else (
                1.2700 if "GBP" in symbol.upper() else (
                    155.0 if "JPY" in symbol.upper() else 65000.0
                )
            )
        )
        vol = 0.0012 if "EUR" in symbol.upper() else (0.0025 if "XAU" in symbol.upper() else 0.005)

        # Generate regime cycles: Bullish expansion -> Consolidation -> Pullback -> Breakout
        returns = []
        regimes = [0.0006, 0.0001, -0.0005, 0.0008, 0.0002, -0.0004]
        reg_idx = 0
        cycle_len = 200

        for i in range(num_bars):
            if i > 0 and i % cycle_len == 0:
                reg_idx = (reg_idx + 1) % len(regimes)
            drift = regimes[reg_idx]
            noise = np.random.normal(drift, vol * 0.6)
            returns.append(noise)


        returns = np.array(returns)
        prices = base_price * np.exp(np.cumsum(returns))

        freq_map = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D"}
        freq = freq_map.get(timeframe, "1h")
        import datetime
        dates = pd.date_range(end=pd.Timestamp.now(tz=datetime.timezone.utc).tz_localize(None), periods=num_bars, freq=freq)

        closes = prices
        opens = np.roll(closes, 1)
        opens[0] = base_price

        bodies = np.abs(closes - opens)
        wick_upper = bodies * np.abs(np.random.normal(0.15, 0.10, num_bars)) + (vol * prices * 0.15)
        wick_lower = bodies * np.abs(np.random.normal(0.15, 0.10, num_bars)) + (vol * prices * 0.15)


        highs = np.maximum(opens, closes) + wick_upper
        lows = np.minimum(opens, closes) - wick_lower
        volumes = np.random.randint(800, 4500, num_bars).astype(float)

        return pd.DataFrame({
            "time": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes
        })


