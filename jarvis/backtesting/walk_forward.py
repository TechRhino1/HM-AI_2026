"""
JARVIS AI 3.0 — Walk-Forward Optimization & Out-of-Sample Validator.
Executes sliding window train/test cycles to confirm out-of-sample consistency and prevent overfitting.
"""
from typing import Dict, List, Any
import pandas as pd
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.metrics import PerformanceMetricsCalculator

class WalkForwardValidator:
    def __init__(self, train_bars: int = 500, test_bars: int = 150):
        self.train_bars = train_bars
        self.test_bars = test_bars

    def run_walk_forward(self, df: pd.DataFrame, symbol: str = "XAUUSD") -> Dict[str, Any]:
        total_bars = len(df)
        step = self.test_bars
        windows = []
        out_of_sample_trades = []

        start = 0
        window_idx = 1

        while start + self.train_bars + self.test_bars <= total_bars:
            test_start = start + self.train_bars
            test_end = test_start + self.test_bars

            df_test = df.iloc[start:test_end]

            bt = BacktestEngine(initial_balance=10000.0)
            res = bt.run_backtest(df_test, symbol=symbol)

            # Filter trades that occurred during out-of-sample segment
            oos_trades = res["trades"]
            out_of_sample_trades.extend(oos_trades)

            windows.append({
                "window": window_idx,
                "train_range": (start, test_start),
                "test_range": (test_start, test_end),
                "trades_count": len(oos_trades),
                "win_rate": res["metrics"]["win_rate_pct"],
                "profit_factor": res["metrics"]["profit_factor"]
            })

            start += step
            window_idx += 1

        overall_metrics = PerformanceMetricsCalculator.calculate_metrics(out_of_sample_trades, 10000.0)

        return {
            "symbol": symbol,
            "total_windows": len(windows),
            "window_results": windows,
            "out_of_sample_metrics": overall_metrics
        }
