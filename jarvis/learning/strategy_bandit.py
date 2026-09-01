"""
JARVIS AI 4.0 — Contextual Multi-Armed Bandit Strategy Optimizer with Thompson Sampling.
Implements Bayesian Beta-Binomial Thompson Sampling and UCB1 for dynamic strategy selection
across (Market Regime, Trading Style, Strategy) contexts.
"""
import os
import json
import threading
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

class StrategyBandit:
    """
    Contextual Multi-Armed Bandit using Beta-Binomial Thompson Sampling
    and Upper Confidence Bound (UCB1) for optimal strategy allocation.
    """
    
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

    # Prior baseline parameters (Baseline ~60% win expectation with exploration)
    DEFAULT_ALPHA = 3.0
    DEFAULT_BETA = 2.0

    def __init__(self, state_file: str = "jarvis_bandit_state.json", exploration_c: float = 0.5):
        self.state_file = state_file
        self.c = exploration_c
        self._lock = threading.Lock()
        
        # Structure: priors[regime][style][strategy] = {"alpha": float, "beta": float, "pulls": int, "rewards": float}
        self.priors: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
        # Legacy counts and rewards for backward compatibility
        self.counts: Dict[str, Dict[str, int]] = {}
        self.rewards: Dict[str, Dict[str, float]] = {}
        
        self._load_state()

    def _canonical_strategy(self, strategy: str) -> str:
        strat_key = str(strategy or "").upper()
        for s in self.STRATEGIES:
            if s in strat_key or strat_key in s:
                return s
        return self.STRATEGIES[0]

    def _get_alpha_beta(self, regime: str, style: str, strategy: str) -> Tuple[float, float]:
        reg_key = str(regime or "GLOBAL").upper()
        style_key = str(style or "SWING").upper()
        strat_key = self._canonical_strategy(strategy)

        reg_dict = self.priors.get(reg_key, {})
        style_dict = reg_dict.get(style_key, {})
        entry = style_dict.get(strat_key)

        if entry:
            return float(entry.get("alpha", self.DEFAULT_ALPHA)), float(entry.get("beta", self.DEFAULT_BETA))
        
        # Fallback to GLOBAL / ANY if specific regime-style not yet populated
        glob_entry = self.priors.get("GLOBAL", {}).get(style_key, {}).get(strat_key)
        if glob_entry:
            return float(glob_entry.get("alpha", self.DEFAULT_ALPHA)), float(glob_entry.get("beta", self.DEFAULT_BETA))

        return self.DEFAULT_ALPHA, self.DEFAULT_BETA

    def sample_strategy_weight(self, strategy: str, regime: str = "GLOBAL", style: str = "SWING") -> float:
        """
        Samples a single strategy weight using Thompson Sampling Beta distribution draw.
        """
        with self._lock:
            alpha, beta = self._get_alpha_beta(regime, style, strategy)
            sample = np.random.beta(max(0.1, alpha), max(0.1, beta))
            return round(float(sample), 4)

    def get_strategy_weights(self, regime: str = "GLOBAL", style: str = "SWING") -> Dict[str, float]:
        """
        Draws Thompson samples for all known strategies in given (regime, style) context
        and normalizes them to sum to 1.0.
        """
        with self._lock:
            samples = {}
            for s in self.STRATEGIES:
                alpha, beta = self._get_alpha_beta(regime, style, s)
                samples[s] = float(np.random.beta(max(0.1, alpha), max(0.1, beta)))
            
            total = sum(samples.values()) or 1.0
            return {s: round(v / total, 4) for s, v in samples.items()}

    def get_strategy_boosts(self, current_regime: Optional[str] = None) -> Dict[str, float]:
        """Calculates normalized probability adjustments via UCB1 for backward compatibility."""
        with self._lock:
            use_regime = current_regime if current_regime and current_regime in self.counts else None
            
            if use_regime:
                counts = self.counts[use_regime]
                rewards = self.rewards[use_regime]
            else:
                counts = {s: 0 for s in self.STRATEGIES}
                rewards = {s: 0.0 for s in self.STRATEGIES}
                for reg_counts in self.counts.values():
                    for s, c in reg_counts.items():
                        counts[s] += c
                for reg_rewards in self.rewards.values():
                    for s, r in reg_rewards.items():
                        rewards[s] += r
                
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

    def record_outcome(
        self,
        strategy: str,
        is_win: Any,
        r_multiple: float = 1.0,
        regime: str = "GLOBAL",
        style: str = "SWING"
    ):
        """
        Updates strategy bandit Beta priors (alpha, beta) and UCB statistics
        after a closed trade for the given (regime, style, strategy) triple.
        """
        with self._lock:
            reg_key = str(regime or "GLOBAL").upper()
            style_key = str(style or "SWING").upper()
            strat_key = self._canonical_strategy(strategy)
            is_win_int = 1 if (is_win is True or is_win == 1 or (isinstance(is_win, (int, float)) and is_win > 0)) else 0
            r_mult = max(0.1, min(5.0, float(r_multiple or 1.0)))

            # 1. Initialize context path if missing
            if reg_key not in self.priors:
                self.priors[reg_key] = {}
            if style_key not in self.priors[reg_key]:
                self.priors[reg_key][style_key] = {
                    s: {"alpha": self.DEFAULT_ALPHA, "beta": self.DEFAULT_BETA, "pulls": 0, "rewards": 0.0}
                    for s in self.STRATEGIES
                }

            if strat_key not in self.priors[reg_key][style_key]:
                self.priors[reg_key][style_key][strat_key] = {
                    "alpha": self.DEFAULT_ALPHA, "beta": self.DEFAULT_BETA, "pulls": 0, "rewards": 0.0
                }

            # 2. Update Beta priors with exponential decay across memory
            for r_k in self.priors:
                for st_k in self.priors[r_k]:
                    for s_k in self.priors[r_k][st_k]:
                        entry = self.priors[r_k][st_k][s_k]
                        entry["alpha"] = max(1.0, (entry["alpha"] - self.DEFAULT_ALPHA) * 0.99 + self.DEFAULT_ALPHA)
                        entry["beta"] = max(1.0, (entry["beta"] - self.DEFAULT_BETA) * 0.99 + self.DEFAULT_BETA)

            target_entry = self.priors[reg_key][style_key][strat_key]
            target_entry["pulls"] += 1

            if is_win_int == 1:
                target_entry["alpha"] += max(0.5, min(3.0, r_mult))
                target_entry["rewards"] += max(1.0, r_mult)
            else:
                target_entry["beta"] += 1.0
                target_entry["rewards"] -= 0.5

            # 3. Maintain legacy counts and rewards for backward compatibility
            if reg_key not in self.counts:
                self.counts[reg_key] = {s: 5 for s in self.STRATEGIES}
                self.rewards[reg_key] = {s: 3.0 for s in self.STRATEGIES}
            if strat_key not in self.counts[reg_key]:
                self.counts[reg_key][strat_key] = 5
                self.rewards[reg_key][strat_key] = 3.0

            for reg in self.rewards:
                for s in self.rewards[reg]:
                    self.rewards[reg][s] *= 0.98

            self.counts[reg_key][strat_key] += 1
            reward_val = (1.0 * max(1.0, r_mult)) if is_win_int else -0.5
            self.rewards[reg_key][strat_key] += reward_val

            self._save_state_internal()

    def _save_state(self):
        with self._lock:
            self._save_state_internal()
            
    def _save_state_internal(self):
        try:
            data = {
                "counts": self.counts,
                "rewards": self.rewards,
                "priors": self.priors
            }
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
                    self.priors = data.get("priors", self.priors)
                except Exception:
                    pass
