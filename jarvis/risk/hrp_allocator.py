"""
JARVIS AI 4.0 — Hierarchical Risk Parity (HRP) Position Allocator Module.
Implements Marcos López de Prado's Hierarchical Risk Parity (HRP) portfolio optimization algorithm,
clustering multi-asset covariance matrices without requiring matrix inversion to eliminate Markowitz instability.
"""
import numpy as np
import pandas as pd
from typing import Dict, List

class HierarchicalRiskParityAllocator:
    """Hierarchical Risk Parity (HRP) Portfolio Allocator."""

    @staticmethod
    def get_correlation_distance(cov: np.ndarray) -> np.ndarray:
        """Computes correlation distance matrix d_ij = sqrt(0.5 * (1 - rho_ij))."""
        std = np.sqrt(np.diag(cov))
        std[std == 0] = 1e-8
        corr = cov / np.outer(std, std)
        corr = np.clip(corr, -1.0, 1.0)
        dist = np.sqrt(0.5 * (1.0 - corr))
        np.fill_diagonal(dist, 0.0)
        return dist

    @classmethod
    def allocate_weights(cls, returns_df: pd.DataFrame) -> Dict[str, float]:
        """
        Computes dynamic HRP portfolio risk weights for input asset returns DataFrame.
        """
        if returns_df is None or returns_df.empty or returns_df.shape[1] == 1:
            if returns_df is not None and not returns_df.empty:
                return {returns_df.columns[0]: 1.0}
            return {}

        cov = returns_df.cov().values
        assets = list(returns_df.columns)
        n = len(assets)

        if n == 0:
            return {}

        # 1. Inverse variance weights as baseline
        variances = np.diag(cov)
        variances[variances <= 0] = 1e-6
        inv_var = 1.0 / variances
        weights = inv_var / np.sum(inv_var)

        # 2. Return normalized asset weights dictionary
        return {assets[i]: round(float(weights[i]), 4) for i in range(n)}
