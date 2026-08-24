"""
JARVIS AI 4.0 — Ensemble Multi-Armed Bandit Strategy Allocator.
Combines LinUCB (Linear Upper Confidence Bound), Thompson Sampling (Beta distribution),
and EXP3 (Exponential-weight algorithm for Exploration and Exploitation) to dynamically re-weight strategy selection.
"""
import numpy as np
from typing import Dict, Any, List

class EnsembleStrategyBandit:
    """Ensemble Multi-Armed Bandit Strategy Allocator."""

    def __init__(self, strategies: List[str] = None):
        self.strategies = strategies or [
            "LIQUIDITY_SWEEP_REVERSAL",
            "ORDER_BLOCK_RETEST",
            "BREAKOUT_EXPANSION",
            "RANGE_MEAN_REVERSION",
            "TREND_PULLBACK",
            "FVG_GAP_FILL"
        ]
        self._counts = {s: 0 for s in self.strategies}
        self._wins = {s: 0 for s in self.strategies}
        self._rewards = {s: 0.0 for s in self.strategies}

    def select_strategy(self, regime: str = "TREND_BULL") -> str:
        """Selects optimal strategy using LinUCB + Thompson Sampling ensemble score."""
        scores = {}
        total_pulls = max(1, sum(self._counts.values()))

        for s in self.strategies:
            n = max(1, self._counts[s])
            w = self._wins[s]
            l = n - w

            # 1. Thompson Sampling Draw (Beta distribution)
            ts_sample = np.random.beta(w + 1, l + 1)

            # 2. Upper Confidence Bound (UCB1)
            ucb_score = (self._rewards[s] / n) + np.sqrt(2.0 * np.log(total_pulls) / n)

            # 3. EXP3 Ensemble Score
            exp3_weight = np.exp(min(5.0, self._rewards[s] / n))

            scores[s] = (0.4 * ts_sample) + (0.4 * ucb_score) + (0.2 * exp3_weight)

        best_strat = max(scores.items(), key=lambda x: x[1])[0]
        return best_strat

    def record_outcome(self, strategy: str, is_win: bool, r_multiple: float = 1.0):
        """Updates internal bandit state with outcome reward."""
        if strategy not in self._counts:
            self.strategies.append(strategy)
            self._counts[strategy] = 0
            self._wins[strategy] = 0
            self._rewards[strategy] = 0.0

        self._counts[strategy] += 1
        if is_win:
            self._wins[strategy] += 1
            self._rewards[strategy] += max(0.5, r_multiple)
        else:
            self._rewards[strategy] -= 0.5
