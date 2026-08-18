"""
JARVIS AI 3.0 — Contextual Multi-Armed Bandit Strategy Optimizer.
Implements Upper Confidence Bound (UCB1) and Thompson Sampling for dynamic strategy probability allocation.
"""
import os
import json
import numpy as np
from typing import Dict, List, Any, Optional

class StrategyBandit:
    """Multi-Armed Bandit strategy optimizer balancing exploration vs exploitation."""
    
    STRATEGIES = [
        "MICRO_ACCOUNT_ADAPTIVE",
        "TREND_FOLLOWING",
        "TREND_PULLBACK",
        "BREAKOUT_EXPANSION",
        "LIQUIDITY_SWEEP_REVERSAL",
        "RANGE_MEAN_REVERSION",
        "CHOCH_STRUCTURAL_REVERSAL"
    ]

    def __init__(self, state_file: str = "jarvis_bandit_state.json", exploration_c: float = 0.5):
        self.state_file = state_file
        self.c = exploration_c
        self.counts: Dict[str, int] = {s: 5 for s in self.STRATEGIES}
        self.rewards: Dict[str, float] = {s: 3.0 for s in self.STRATEGIES}
        self._load_state()

    def get_strategy_boosts(self) -> Dict[str, float]:
        """Calculates normalized probability adjustments via UCB1."""
        total_pulls = sum(self.counts.values())
        if total_pulls == 0:
            return {s: 1.0 for s in self.STRATEGIES}

        ucb_scores = {}
        for s in self.STRATEGIES:
            n = self.counts[s]
            avg_reward = self.rewards[s] / max(1, n)
            exploration_bonus = self.c * np.sqrt(np.log(total_pulls) / max(1, n))
            ucb_scores[s] = max(0.1, avg_reward + exploration_bonus)

        total_score = sum(ucb_scores.values())
        return {s: round(v / total_score, 3) for s, v in ucb_scores.items()}

    def record_outcome(self, strategy: str, is_win: int, r_multiple: float = 1.0):
        """Updates strategy bandit statistics after a closed trade."""
        if strategy not in self.counts:
            self.counts[strategy] = 0
            self.rewards[strategy] = 0.0

        self.counts[strategy] += 1
        # Reward function: Win gives +1.0 * R-multiple, Loss gives -0.5
        reward_val = (1.0 * max(1.0, r_multiple)) if is_win else -0.5
        self.rewards[strategy] = max(0.0, self.rewards[strategy] + reward_val)

        self._save_state()

    def _save_state(self):
        try:
            data = {"counts": self.counts, "rewards": self.rewards}
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                self.counts = data.get("counts", self.counts)
                self.rewards = data.get("rewards", self.rewards)
            except Exception:
                pass
