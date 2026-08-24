"""
JARVIS AI 4.0 — Fractional Differentiation Feature Transformer Module.
Implements Marcos López de Prado's Fixed-Width Window Fractional Differentiation (0 < d < 1)
to achieve stationarity (ADF test p < 0.05) while preserving maximum memory / long-range dependence in feature signals.
"""
import numpy as np
import pandas as pd
from typing import List, Union

class FractionalDifferentiationTransformer:
    """Fixed-Width Window Fractional Differentiation Engine."""

    @staticmethod
    def get_weights(d: float, size: int) -> np.ndarray:
        """Generates binomial expansion weights for fractional differencing parameter d."""
        w = [1.0]
        for k in range(1, size):
            w.append(-w[-1] / k * (d - k + 1))
        return np.array(w[::-1])

    @classmethod
    def frac_diff_fixed_width(cls, series: pd.Series, d: float = 0.40, threshold: float = 1e-4) -> pd.Series:
        """
        Applies fixed-width window fractional differencing to a price or indicator series.
        :param series: Raw input pandas Series
        :param d: Fractional differencing order (typically 0.35 to 0.45)
        :param threshold: Weight cutoff threshold to preserve memory window
        """
        if series is None or len(series) < 10:
            return series

        # 1. Compute weights cutoff
        w = cls.get_weights(d, len(series))
        w_abs = np.abs(w)
        cum_w = np.cumsum(w_abs) / np.sum(w_abs)
        skip = int(np.searchsorted(cum_w, threshold))
        w = w[skip:]
        width = len(w)

        if width < 1 or width > len(series):
            width = min(20, len(series))
            w = cls.get_weights(d, width)

        # 2. Apply sliding dot product window
        res = {}
        vals = series.values
        for i in range(width - 1, len(series)):
            window = vals[i - width + 1:i + 1]
            if np.isnan(window).any():
                continue
            res[series.index[i]] = np.dot(w, window)

        return pd.Series(res, dtype=float)

    @classmethod
    def transform_dataframe(cls, df: pd.DataFrame, cols: List[str] = None, d: float = 0.40) -> pd.DataFrame:
        """Transforms specified numeric columns using fractional differencing."""
        df_out = df.copy()
        if cols is None:
            cols = [c for c in ["close", "high", "low", "open", "vwap"] if c in df.columns]

        for col in cols:
            if col in df_out.columns:
                fd_series = cls.frac_diff_fixed_width(df_out[col], d=d)
                df_out[f"{col}_fracdiff"] = fd_series.reindex(df_out.index).ffill().bfill()

        return df_out
