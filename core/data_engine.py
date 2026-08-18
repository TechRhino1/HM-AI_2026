import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
import MetaTrader5 as mt5

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1 if hasattr(mt5, "TIMEFRAME_M1") else 1,
    "M5": mt5.TIMEFRAME_M5 if hasattr(mt5, "TIMEFRAME_M5") else 5,
    "M15": mt5.TIMEFRAME_M15 if hasattr(mt5, "TIMEFRAME_M15") else 15,
    "M30": mt5.TIMEFRAME_M30 if hasattr(mt5, "TIMEFRAME_M30") else 30,
    "H1": mt5.TIMEFRAME_H1 if hasattr(mt5, "TIMEFRAME_H1") else 16385,
    "H4": mt5.TIMEFRAME_H4 if hasattr(mt5, "TIMEFRAME_H4") else 16388,
    "D1": mt5.TIMEFRAME_D1 if hasattr(mt5, "TIMEFRAME_D1") else 16408,
}

class MultiTimeframeDataEngine:
    def __init__(self, mt5_client: Any, logger: Any = None):
        self.mt5_client = mt5_client
        self.logger = logger

    def fetch_rates(self, symbol: str, timeframe: str = "H1", num_bars: int = 250) -> pd.DataFrame:
        if self.mt5_client.mode == "dry_run" or not self.mt5_client.is_connected:
            return self._generate_synthetic_rates(symbol, timeframe, num_bars)

        resolved_symbol = self.mt5_client.resolve_symbol_name(symbol)
        mt5_tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(resolved_symbol, mt5_tf, 0, num_bars)
        if rates is None or len(rates) == 0:
            if self.logger:
                self.logger.warning(f"Could not fetch rates for {symbol} [{timeframe}]. Falling back to synthetic.")
            return self._generate_synthetic_rates(symbol, timeframe, num_bars)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
        return df[["time", "open", "high", "low", "close", "volume"]]

    def fetch_multi_timeframe_data(self, symbol: str, timeframes: Optional[Dict[str, str]] = None, num_bars: int = 250) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = {
                "macro": "D1",
                "context": "H4",
                "primary": "H1",
                "setup": "M15",
                "timing": "M5"
            }

        mtf_data = {}
        for role, tf in timeframes.items():
            mtf_data[role] = self.fetch_rates(symbol, timeframe=tf, num_bars=num_bars)
        return mtf_data

    def _generate_synthetic_rates(self, symbol: str, timeframe: str, num_bars: int) -> pd.DataFrame:
        np.random.seed(42 if "XAU" in symbol else 100)
        base_price = 2000.0 if "XAU" in symbol else (1.0850 if "EUR" in symbol else 65000.0)
        returns = np.random.normal(0.0001, 0.003, num_bars)
        prices = base_price * np.exp(np.cumsum(returns))

        dates = pd.date_range(end=pd.Timestamp.now(), periods=num_bars, freq="1h")
        highs = prices * (1 + np.abs(np.random.normal(0.001, 0.001, num_bars)))
        lows = prices * (1 - np.abs(np.random.normal(0.001, 0.001, num_bars)))
        opens = (highs + lows) / 2 + np.random.normal(0, 0.5, num_bars)
        closes = prices
        volumes = np.random.randint(100, 5000, num_bars)

        df = pd.DataFrame({
            "time": dates,
            "open": opens,
            "high": np.maximum(highs, np.maximum(opens, closes)),
            "low": np.minimum(lows, np.minimum(opens, closes)),
            "close": closes,
            "volume": volumes
        })
        return df
