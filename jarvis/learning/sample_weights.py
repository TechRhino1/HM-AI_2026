"""
JARVIS AI 4.0 — Sample Uniqueness & Overlapping Weighting Engine.
Implements Marcos López de Prado's Sample Uniqueness Weighting algorithm to handle
overlapping return periods across trade records, preventing ML model overfitting.
"""
import numpy as np
from typing import List, Dict, Any

class SampleUniquenessWeightEngine:
    """Calculates sample uniqueness weights based on concurrent trade label overlaps."""

    @staticmethod
    def calculate_concurrency(trades: List[Dict[str, Any]]) -> np.ndarray:
        """Computes the number of concurrent active trade labels at each sample index."""
        if not trades:
            return np.array([])

        num_trades = len(trades)
        concurrency = np.ones(num_trades, dtype=float)

        for i in range(num_trades):
            t_i_start = i
            t_i_end = i + trades[i].get("duration_bars", 5)
            overlap_count = 1
            for j in range(num_trades):
                if i == j:
                    continue
                t_j_start = j
                t_j_end = j + trades[j].get("duration_bars", 5)
                if max(t_i_start, t_j_start) <= min(t_i_end, t_j_end):
                    overlap_count += 1
            concurrency[i] = overlap_count

        return concurrency

    @classmethod
    def get_sample_weights(cls, trades: List[Dict[str, Any]]) -> np.ndarray:
        """Returns normalized uniqueness weights (sum to 1.0) for ML training."""
        if not trades:
            return np.array([])

        concurrency = cls.calculate_concurrency(trades)
        uniqueness = 1.0 / np.maximum(1.0, concurrency)
        
        # Absolute PnL magnitude scaling to prioritize high-conviction trades
        pnl_mags = np.array([abs(t.get("pnl", 0.0) or t.get("expected_value", 1.0)) for t in trades], dtype=float)
        if np.sum(pnl_mags) > 0:
            pnl_mags = pnl_mags / np.mean(pnl_mags)
        else:
            pnl_mags = np.ones_like(uniqueness)

        weights = uniqueness * pnl_mags
        if np.sum(weights) > 0:
            weights = weights / np.sum(weights)
        return weights
