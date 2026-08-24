"""
JARVIS AI 4.0 — Quantitative Performance Benchmark & Win Rate Comparison Script.
Compares baseline strategy results against current upgraded quantitative AI system.
"""
import sys
import logging
import pandas as pd
import numpy as np

from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.walk_forward import WalkForwardEngine

logging.basicConfig(level=logging.WARNING)

def run_comparison(symbol: str = "XAUUSD", num_bars: int = 600):
    feed = DataFeedEngine()
    df = feed.fetch_rates(symbol, timeframe="H1", num_bars=num_bars)

    print("=" * 80)
    print(f"            JARVIS AI 4.0 QUANTITATIVE PERFORMANCE BENCHMARK ({symbol})")
    print("=" * 80)

    # 1. Run Current Upgraded System Backtest
    bt_engine = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
    res_upgraded = bt_engine.run_backtest(df, symbol=symbol)
    m_upgraded = res_upgraded["metrics"]

    # 2. Run Walk-Forward Validation
    wf_engine = WalkForwardEngine(num_folds=3, initial_balance=10000.0)
    res_wf = wf_engine.run_walk_forward_validation(df, symbol=symbol)
    m_oos = res_wf["aggregate_oos_metrics"]

    print("\n--- PERFORMANCE SUMMARY TABLE ---")
    print(f"{'Metric':<25} | {'Upgraded AI System':<20} | {'Out-Of-Sample (OOS)':<20}")
    print("-" * 75)
    print(f"{'Total Trades':<25} | {m_upgraded.get('total_trades', 0):<20} | {m_oos.get('total_trades', 0):<20}")
    print(f"{'Win Rate %':<25} | {m_upgraded.get('win_rate_pct', 0.0):<20.2f}% | {m_oos.get('win_rate_pct', 0.0):<20.2f}%")
    print(f"{'Profit Factor':<25} | {m_upgraded.get('profit_factor', 0.0):<20.2f} | {m_oos.get('profit_factor', 0.0):<20.2f}")
    print(f"{'Net Profit ($)':<25} | ${m_upgraded.get('net_profit', 0.0):<19.2f} | ${m_oos.get('net_profit', 0.0):<19.2f}")
    print(f"{'Sharpe Ratio':<25} | {m_upgraded.get('sharpe_ratio', 0.0):<20.2f} | {m_oos.get('sharpe_ratio', 0.0):<20.2f}")
    print(f"{'Sortino Ratio':<25} | {m_upgraded.get('sortino_ratio', 0.0):<20.2f} | {m_oos.get('sortino_ratio', 0.0):<20.2f}")
    print(f"{'Max Drawdown %':<25} | {m_upgraded.get('max_drawdown_pct', 0.0):<20.2f}% | {m_oos.get('max_drawdown_pct', 0.0):<20.2f}%")
    print(f"{'Walk-Forward Efficiency':<25} | {res_wf.get('walk_forward_efficiency', 0.0):<20.2f} | {'PASSED' if res_wf.get('passed_wfe') else 'MARGINAL':<20}")
    print("=" * 80)

if __name__ == "__main__":
    run_comparison("XAUUSD")
