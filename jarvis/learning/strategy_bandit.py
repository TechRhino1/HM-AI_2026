"""
JARVIS AI 3.0 — Contextual Multi-Armed Bandit Strategy Optimizer.
Implements Upper Confidence Bound (UCB1) and Thompson Sampling for dynamic strategy probability allocation.
"""
import os
import json
import threading
import numpy as np
from typing import Dict, List, Any, Optional

class StrategyBandit:
    """Multi-Armed Bandit strategy optimizer balancing exploration vs exploitation."""
    
    STRATEGIES = [
        "MICRO_ACCOUNT_ADAPTIVE",
        "MICRO_LIQUIDITY_SWEEP",
        "M1_M5_FVG_SCALP",
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
        self._lock = threading.Lock()
        
        # Dict[regime, Dict[strategy, value]]
        self.counts: Dict[str, Dict[str, int]] = {}
        self.rewards: Dict[str, Dict[str, float]] = {}
        
        self._load_state()

    def get_strategy_boosts(self, current_regime: Optional[str] = None) -> Dict[str, float]:
        """Calculates normalized probability adjustments via UCB1."""
        with self._lock:
            # Fallback to aggregate if no regime specified or no data for regime
            use_regime = current_regime if current_regime and current_regime in self.counts else None
            
            if use_regime:
                counts = self.counts[use_regime]
                rewards = self.rewards[use_regime]
            else:
                # Aggregate across all regimes
                counts = {s: 0 for s in self.STRATEGIES}
                rewards = {s: 0.0 for s in self.STRATEGIES}
                for reg_counts in self.counts.values():
                    for s, c in reg_counts.items():
                        counts[s] += c
                for reg_rewards in self.rewards.values():
                    for s, r in reg_rewards.items():
                        rewards[s] += r
                
                # If completely empty, init baseline
                if not self.counts:
                    counts = {s: 5 for s in self.STRATEGIES}
                    rewards = {s: 3.0 for s in self.STRATEGIES}

            total_pulls = sum(counts.values())
            if total_pulls == 0:
                return {s: 1.0 for s in self.STRATEGIES}

            ucb_scores = {}
            for s in self.STRATEGIES:
                n = counts.get(s, 0)
                avg_reward = rewards.get(s, 0.0) / max(1, n)
                exploration_bonus = self.c * np.sqrt(np.log(total_pulls) / max(1, n))
                ucb_scores[s] = max(0.1, avg_reward + exploration_bonus)

            total_score = sum(ucb_scores.values())
            return {s: round(v / total_score, 3) for s, v in ucb_scores.items()}

    def record_outcome(self, strategy: str, is_win: int, r_multiple: float = 1.0, regime: str = "GLOBAL"):
        """Updates strategy bandit statistics after a closed trade."""
        with self._lock:
            reg_key = str(regime or "GLOBAL").upper()
            if reg_key not in self.counts:
                self.counts[reg_key] = {s: 5 for s in self.STRATEGIES}
                self.rewards[reg_key] = {s: 3.0 for s in self.STRATEGIES}

            # Map strategy to known canonical strategy if needed
            strat_key = str(strategy or "").upper()
            if strat_key not in self.counts[reg_key]:
                matched = None
                for s in self.STRATEGIES:
                    if s in strat_key or strat_key in s:
                        matched = s
                        break
                strat_key = matched if matched else self.STRATEGIES[0]

            # Exponential decay
            for reg in self.rewards:
                for s in self.rewards[reg]:
                    self.rewards[reg][s] *= 0.98

            self.counts[reg_key][strat_key] += 1
            # Reward function: Win gives +1.0 * R-multiple, Loss gives -0.5 (allow true negative tracking §14)
            reward_val = (1.0 * max(1.0, float(r_multiple))) if is_win else -0.5
            self.rewards[reg_key][strat_key] = self.rewards[reg_key][strat_key] + reward_val

            self._save_state_internal()

    def _save_state(self):
        with self._lock:
            self._save_state_internal()
            
    def _save_state_internal(self):
        try:
            data = {"counts": self.counts, "rewards": self.rewards}
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_state(self):
        with self._lock:
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, "r") as f:
                        data = json.load(f)
                    self.counts = data.get("counts", self.counts)
                    self.rewards = data.get("rewards", self.rewards)
                except Exception:
                    pass
