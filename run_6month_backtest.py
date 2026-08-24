"""
JARVIS AI 4.0 — 6-Month Multi-Asset Backtest Suite (XAUUSD & BTCUSD).
Executes backtest over 4,320 H1 bars (6 months of continuous trading) to evaluate performance metrics.
"""
import sys
import logging
import pandas as pd
import numpy as np

from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.walk_forward import WalkForwardEngine

logging.basicConfig(level=logging.WARNING)

def run_6month_backtest(symbols: list = ["XAUUSD", "BTCUSD"], num_bars: int = 4320):
    feed = DataFeedEngine()

    print("=" * 85)
    print("          JARVIS AI 4.0 — 6-MONTH HISTORICAL PERFORMANCE REPORT (4,320 H1 BARS)")
    print("=" * 85)

    results = {}

    for symbol in symbols:
        df = feed.fetch_rates(symbol, timeframe="H1", num_bars=num_bars)

        # Execute Backtest
        bt_engine = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
        res_bt = bt_engine.run_backtest(df, symbol=symbol, spread_pips=2.5 if "XAU" in symbol else 15.0)
        m = res_bt["metrics"]

        # Execute Walk-Forward Evaluation
        wf_engine = WalkForwardEngine(num_folds=4, initial_balance=10000.0)
        res_wf = wf_engine.run_walk_forward_validation(df, symbol=symbol, spread_pips=2.5 if "XAU" in symbol else 15.0)
        m_oos = res_wf["aggregate_oos_metrics"]

        results[symbol] = {
            "bt_metrics": m,
            "oos_metrics": m_oos,
            "final_balance": res_bt["final_balance"],
            "wfe": res_wf["walk_forward_efficiency"],
            "passed_wfe": res_wf["passed_wfe"]
        }

    print("\n--- 6-MONTH PERFORMANCE SUMMARY TABLE ---")
    print(f"{'Performance Metric':<28} | {'XAUUSD (Gold)':<25} | {'BTCUSD (Bitcoin)':<25}")
    print("-" * 85)

    res_xau = results.get("XAUUSD", {})
    res_btc = results.get("BTCUSD", {})
    m_xau = res_xau.get("bt_metrics", {})
    m_btc = res_btc.get("bt_metrics", {})
    oos_xau = res_xau.get("oos_metrics", {})
    oos_btc = res_btc.get("oos_metrics", {})

    print(f"{'Total Trades Executed':<28} | {m_xau.get('total_trades', 0):<25} | {m_btc.get('total_trades', 0):<25}")
    print(f"{'Winning Trades':<28} | {m_xau.get('wins', 0):<25} | {m_btc.get('wins', 0):<25}")
    print(f"{'Losing Trades':<28} | {m_xau.get('losses', 0):<25} | {m_btc.get('losses', 0):<25}")
    print(f"{'In-Sample Win Rate %':<28} | {m_xau.get('win_rate_pct', 0.0):<24.2f}% | {m_btc.get('win_rate_pct', 0.0):<24.2f}%")
    print(f"{'Out-Of-Sample (OOS) Win Rate':<28} | {oos_xau.get('win_rate_pct', 0.0):<24.2f}% | {oos_btc.get('win_rate_pct', 0.0):<24.2f}%")
    print(f"{'Profit Factor':<28} | {m_xau.get('profit_factor', 0.0):<25.2f} | {m_btc.get('profit_factor', 0.0):<25.2f}")
    print(f"{'Out-Of-Sample Profit Factor':<28} | {oos_xau.get('profit_factor', 0.0):<25.2f} | {oos_btc.get('profit_factor', 0.0):<25.2f}")
    print(f"{'Net Profit ($)':<28} | ${m_xau.get('net_profit', 0.0):<24.2f} | ${m_btc.get('net_profit', 0.0):<24.2f}")
    print(f"{'Final Account Balance':<28} | ${res_xau.get('final_balance', 10000.0):<24.2f} | ${res_btc.get('final_balance', 10000.0):<24.2f}")
    print(f"{'Sharpe Ratio':<28} | {m_xau.get('sharpe_ratio', 0.0):<25.2f} | {m_btc.get('sharpe_ratio', 0.0):<25.2f}")
    print(f"{'Sortino Ratio':<28} | {m_xau.get('sortino_ratio', 0.0):<25.2f} | {m_btc.get('sortino_ratio', 0.0):<25.2f}")
    print(f"{'Max Drawdown %':<28} | {m_xau.get('max_drawdown_pct', 0.0):<24.2f}% | {m_btc.get('max_drawdown_pct', 0.0):<24.2f}%")
    print(f"{'Walk-Forward Efficiency (WFE)':<28} | {res_xau.get('wfe', 0.0):<25.2f} | {res_btc.get('wfe', 0.0):<25.2f}")
    print("=" * 85)

if __name__ == "__main__":
    run_6month_backtest(["XAUUSD", "BTCUSD"], num_bars=4320)
