"""
JARVIS AI 3.0 — Cross-Asset Dynamic Correlation Engine.
Calculates dynamic rolling correlations between Gold, USD Majors, Indices, and Crypto to prevent concentrated risk exposure.
"""
import pandas as pd
from typing import Dict, Any

class DynamicCorrelationEngine:
    def __init__(self, rolling_window: int = 30):
        self.rolling_window = rolling_window

    def compute_correlation_matrix(self, price_series_map: Dict[str, pd.Series]) -> Dict[str, Dict[str, float]]:
        """Computes pairwise rolling correlation matrix across given asset price series."""
        if len(price_series_map) < 2:
            return {}

        df = pd.DataFrame(price_series_map).dropna()
        if len(df) < 5:
            return {}

        returns_df = df.pct_change().dropna()
        corr_matrix = returns_df.tail(self.rolling_window).corr()

        result = {}
        for sym1 in corr_matrix.columns:
            result[sym1] = {}
            for sym2 in corr_matrix.columns:
                val = corr_matrix.loc[sym1, sym2]
                result[sym1][sym2] = round(float(val), 2) if not pd.isna(val) else 0.0

        return result

    _DEFAULT_CORRELATIONS = {
        ("EURUSD", "GBPUSD"): 0.82,
        ("EURUSD", "USDJPY"): -0.65,
        ("EURUSD", "USDCHF"): -0.88,
        ("GBPUSD", "USDJPY"): -0.55,
        ("XAUUSD", "EURUSD"): 0.45,
        ("XAUUSD", "USDJPY"): -0.40,
        ("XAUUSD", "BTCUSD"): 0.25,
        ("BTCUSD", "EURUSD"): 0.15,
        ("BTCUSD", "USDJPY"): -0.10,
    }

    def get_correlation(self, symbol_a: str, symbol_b: str) -> float:
        """Returns pairwise correlation between two symbols (1.0 for same symbol)."""
        from jarvis.data.symbol_registry import resolve
        canon_a = resolve(symbol_a).canonical
        canon_b = resolve(symbol_b).canonical

        if canon_a == canon_b:
            return 1.0

        pair = (canon_a, canon_b)
        rev_pair = (canon_b, canon_a)

        if pair in self._DEFAULT_CORRELATIONS:
            return self._DEFAULT_CORRELATIONS[pair]
        if rev_pair in self._DEFAULT_CORRELATIONS:
            return self._DEFAULT_CORRELATIONS[rev_pair]

        return 0.0

    def get_correlated_exposure_risk(
        self,
        target_symbol: str,
        open_symbols: list,
        corr_matrix: Dict[str, Dict[str, float]],
        threshold: float = 0.70
    ) -> Dict[str, Any]:
        """Checks if opening target_symbol creates excessive correlated exposure with already open symbols."""
        conflicts = []
        for sym in open_symbols:
            if sym == target_symbol:
                continue
            corr = corr_matrix.get(target_symbol, {}).get(sym, 0.0) if corr_matrix else self.get_correlation(target_symbol, sym)
            if abs(corr) >= threshold:
                conflicts.append({
                    "symbol": sym,
                    "correlation": corr,
                    "relationship": "HIGHLY_POSITIVE" if corr > 0 else "HIGHLY_INVERSE"
                })

        return {
            "has_correlated_risk": len(conflicts) > 0,
            "conflicts": conflicts
        }

