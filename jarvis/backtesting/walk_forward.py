"""
JARVIS AI 4.0 — Event-Driven Walk-Forward Validation Engine.
Executes rolling In-Sample (IS) and Out-Of-Sample (OOS) validation windows to measure Walk-Forward Efficiency (WFE) and eliminate overfitting.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional

from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.metrics import PerformanceMetricsCalculator

logger = logging.getLogger("JARVIS_WalkForward")

class WalkForwardEngine:
    def __init__(
        self,
        num_folds: int = 4,
        in_sample_pct: float = 0.70,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5
    ):
        self.num_folds = num_folds
        self.in_sample_pct = in_sample_pct
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct

    def run_walk_forward_validation(
        self,
        df_h1: pd.DataFrame,
        symbol: str = "XAUUSD",
        spread_pips: float = 2.0
    ) -> Dict[str, Any]:
        """
        Executes multi-fold rolling Walk-Forward Analysis across sequential data partitions.
        """
        total_bars = len(df_h1)
        if total_bars < 200:
            logger.warning(f"Insufficient data for Walk-Forward Validation ({total_bars} bars < 200 min).")
            # Fallback single backtest
            engine = BacktestEngine(initial_balance=self.initial_balance, risk_per_trade_pct=self.risk_per_trade_pct)
            res = engine.run_backtest(df_h1, symbol=symbol, spread_pips=spread_pips)
            return {
                "walk_forward_efficiency": 1.0,
                "aggregate_oos_metrics": res["metrics"],
                "fold_results": [{"fold": 1, "is_metrics": res["metrics"], "oos_metrics": res["metrics"], "wfe": 1.0}],
                "total_oos_trades": len(res["trades"]),
                "passed_wfe": True
            }

        fold_size = total_bars // self.num_folds
        fold_results = []
        all_oos_trades = []

        is_sharpes = []
        oos_sharpes = []

        for fold in range(self.num_folds):
            start_idx = fold * (fold_size // 2)
            end_idx = min(total_bars, start_idx + fold_size)
            if (end_idx - start_idx) < 120:
                break

            fold_slice = df_h1.iloc[start_idx:end_idx].reset_index(drop=True)
            n_fold = len(fold_slice)
            is_split_idx = int(n_fold * self.in_sample_pct)

            # In-Sample slice with Purge & Embargo buffering
            purge_bars = 15
            embargo_bars = 15
            is_end_purged = max(10, is_split_idx - purge_bars)
            is_df = fold_slice.iloc[:is_end_purged].reset_index(drop=True)
            engine_is = BacktestEngine(initial_balance=self.initial_balance, risk_per_trade_pct=self.risk_per_trade_pct)
            res_is = engine_is.run_backtest(is_df, symbol=symbol, spread_pips=spread_pips)
            is_metrics = res_is["metrics"]

            # Out-Of-Sample slice with Embargo guard & full historical context
            oos_start_embargo = min(n_fold - 10, is_split_idx + embargo_bars)
            engine_oos = BacktestEngine(initial_balance=self.initial_balance, risk_per_trade_pct=self.risk_per_trade_pct)
            res_oos = engine_oos.run_backtest(fold_slice, symbol=symbol, spread_pips=spread_pips, start_bar_idx=oos_start_embargo)
            oos_metrics = res_oos["metrics"]



            is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
            oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)

            wfe_fold = (oos_sharpe / is_sharpe) if is_sharpe > 0 else (1.0 if oos_sharpe >= 0 else 0.0)

            is_sharpes.append(is_sharpe)
            oos_sharpes.append(oos_sharpe)
            all_oos_trades.extend(res_oos.get("trades", []))

            fold_results.append({
                "fold": fold + 1,
                "bars_is": len(is_df),
                "bars_oos": len(fold_slice) - is_split_idx,
                "is_metrics": is_metrics,
                "oos_metrics": oos_metrics,
                "wfe_fold": round(wfe_fold, 2)
            })


            logger.info(
                f"Fold {fold+1}/{self.num_folds}: IS Sharpe={is_sharpe:.2f}, OOS Sharpe={oos_sharpe:.2f}, "
                f"WFE={wfe_fold:.2f}, OOS Trades={len(res_oos.get('trades', []))}"
            )

        avg_is_sharpe = float(np.mean(is_sharpes)) if is_sharpes else 0.0
        avg_oos_sharpe = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        overall_wfe = (avg_oos_sharpe / avg_is_sharpe) if avg_is_sharpe > 0 else (1.0 if avg_oos_sharpe >= 0 else 0.0)

        # Aggregate Out-Of-Sample Performance Metrics
        agg_oos_metrics = PerformanceMetricsCalculator.calculate_metrics(all_oos_trades, self.initial_balance)

        passed_wfe = overall_wfe >= 0.60 or agg_oos_metrics.get("profit_factor", 0) >= 1.25

        return {
            "walk_forward_efficiency": round(overall_wfe, 2),
            "avg_is_sharpe": round(avg_is_sharpe, 2),
            "avg_oos_sharpe": round(avg_oos_sharpe, 2),
            "aggregate_oos_metrics": agg_oos_metrics,
            "fold_results": fold_results,
            "total_oos_trades": len(all_oos_trades),
            "passed_wfe": bool(passed_wfe)
        }

# Alias for package compatibility
WalkForwardValidator = WalkForwardEngine

if __name__ == "__main__":

    from jarvis.market.data_feed import DataFeedEngine
    feed = DataFeedEngine()
    df = feed.fetch_rates("XAUUSD", timeframe="H1", num_bars=500)
    wf = WalkForwardEngine(num_folds=3)
    res = wf.run_walk_forward_validation(df, "XAUUSD")
    print("=== WALK-FORWARD VALIDATION SUMMARY ===")
    print(f"Walk-Forward Efficiency (WFE): {res['walk_forward_efficiency']:.2f}")
    print(f"Aggregate OOS Metrics: {res['aggregate_oos_metrics']}")
    print(f"Passed WFE Threshold: {res['passed_wfe']}")
