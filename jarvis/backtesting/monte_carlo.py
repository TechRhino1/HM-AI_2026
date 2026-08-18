"""
JARVIS AI 3.0 — Monte Carlo Resampling & Risk of Ruin Simulator.
Simulates randomized trade sequences, slippage variance, and maximum drawdown distributions.
"""
from typing import List, Dict, Any
import numpy as np

class MonteCarloSimulator:
    def __init__(self, num_simulations: int = 500):
        self.num_simulations = num_simulations

    def run_simulation(self, trades: List[Dict[str, Any]], initial_balance: float = 10000.0) -> Dict[str, Any]:
        if not trades:
            return {"simulations": 0, "var_95_pct": 0.0, "max_dd_median_pct": 0.0, "risk_of_ruin_pct": 0.0}

        pnls = np.array([t["pnl"] for t in trades])
        n_trades = len(pnls)

        final_balances = []
        max_drawdowns = []
        ruin_count = 0

        for _ in range(self.num_simulations):
            # Resample trade returns with replacement
            sampled_pnls = np.random.choice(pnls, size=n_trades, replace=True)
            # Add stochastic slippage noise
            noise = np.random.normal(0.0, 2.0, size=n_trades)
            sim_pnls = sampled_pnls + noise

            eq_curve = [initial_balance]
            for p in sim_pnls:
                eq_curve.append(eq_curve[-1] + p)

            eq_curve = np.array(eq_curve)
            if np.any(eq_curve <= initial_balance * 0.5):
                ruin_count += 1

            final_balances.append(eq_curve[-1])

            # Calculate max DD for this path
            running_max = np.maximum.accumulate(eq_curve)
            drawdowns = (running_max - eq_curve) / (running_max + 1e-9) * 100.0
            max_drawdowns.append(np.max(drawdowns))

        final_balances = np.array(final_balances)
        max_drawdowns = np.array(max_drawdowns)

        var_95 = np.percentile(final_balances, 5)
        median_dd = np.median(max_drawdowns)
        max_dd_95th = np.percentile(max_drawdowns, 95)
        risk_of_ruin = (ruin_count / self.num_simulations) * 100.0

        return {
            "num_simulations": self.num_simulations,
            "median_final_balance": round(float(np.median(final_balances)), 2),
            "var_95_balance": round(float(var_95), 2),
            "max_dd_median_pct": round(float(median_dd), 2),
            "max_dd_95th_percentile_pct": round(float(max_dd_95th), 2),
            "risk_of_ruin_pct": round(float(risk_of_ruin), 2)
        }
