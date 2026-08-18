import numpy as np
import pandas as pd
from typing import List, Dict, Any

class PerformanceMetricsCalculator:
    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]], initial_balance: float = 10000.0) -> Dict[str, Any]:
        if not trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "net_profit": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "expectancy": 0.0
            }

        pnls = [t.get("pnl", 0.0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = (len(wins) / len(trades)) * 100.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_profit = gross_profit - gross_loss

        profit_factor = round(gross_profit / (gross_loss + 1e-9), 2)

        # Drawdown calculation
        equity_curve = [initial_balance]
        for p in pnls:
            equity_curve.append(equity_curve[-1] + p)

        equity_arr = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdowns = (peak - equity_arr) / peak * 100.0
        max_dd_pct = round(float(np.max(drawdowns)), 2)

        # Sharpe ratio
        returns = np.array(pnls) / initial_balance
        std_ret = np.std(returns)
        sharpe = round((np.mean(returns) / (std_ret + 1e-9)) * np.sqrt(252), 2) if len(returns) > 1 else 0.0

        expectancy = round(net_profit / len(trades), 2)

        return {
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 2),
            "net_profit": round(net_profit, 2),
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd_pct,
            "expectancy": expectancy
        }
