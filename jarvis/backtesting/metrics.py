"""
JARVIS AI 3.0 — Comprehensive Performance Metrics Calculator.
Calculates institutional performance metrics: Sharpe, Sortino, Calmar, Expectancy, Profit Factor, Max Drawdown, MFE/MAE.
"""
from typing import List, Dict, Any
import numpy as np

class PerformanceMetricsCalculator:
    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]], initial_balance: float = 10000.0) -> Dict[str, Any]:
        if not trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "expectancy_dollars": 0.0,
                "net_profit": 0.0,
                "max_drawdown_dollars": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "wins": 0,
                "losses": 0
            }

        pnls = [float(t.get("pnl", 0.0)) for t in trades]
        total_trades = len(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        net_profit = sum(pnls)
        expectancy = net_profit / total_trades

        # Drawdown calculation
        equity_curve = [initial_balance]
        for p in pnls:
            equity_curve.append(equity_curve[-1] + p)

        peak = equity_curve[0]
        max_dd_dollars = 0.0
        max_dd_pct = 0.0

        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd_dollars = peak - eq
            dd_pct = (dd_dollars / (peak + 1e-9)) * 100.0
            if dd_dollars > max_dd_dollars:
                max_dd_dollars = dd_dollars
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        # Sharpe & Sortino (per trade)
        returns = np.array(pnls) / initial_balance
        mean_ret = np.mean(returns)
        std_ret = np.std(returns) if len(returns) > 1 else 1e-6
        sharpe = float((mean_ret / (std_ret + 1e-9)) * np.sqrt(252))

        neg_returns = returns[returns < 0]
        downside_std = np.std(neg_returns) if len(neg_returns) > 1 else 1e-6
        sortino = float((mean_ret / (downside_std + 1e-9)) * np.sqrt(252))

        calmar = (net_profit / (max_dd_dollars + 1e-9)) if max_dd_dollars > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_dollars": round(expectancy, 2),
            "net_profit": round(net_profit, 2),
            "max_drawdown_dollars": round(max_dd_dollars, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "wins": win_count,
            "losses": loss_count
        }
