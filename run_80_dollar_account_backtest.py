"""
JARVIS AI 4.0 — $80 Micro Account Historical Performance Suite.
Evaluates 6-month trading performance on an $80 micro-account balance (Option B risk floor & micro quality gates).
"""
import sys
import logging
import pandas as pd
import numpy as np

from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.walk_forward import WalkForwardEngine

logging.basicConfig(level=logging.WARNING)

def run_80_dollar_account_backtest(symbols: list = ["XAUUSD", "BTCUSD"], num_bars: int = 4320):
    feed = DataFeedEngine()

    print("=" * 95)
    print("          JARVIS AI 4.0 — $80 MICRO ACCOUNT HISTORICAL PERFORMANCE REPORT")
    print("=" * 95)

    for symbol in symbols:
        df_full = feed.fetch_rates(symbol, timeframe="H1", num_bars=num_bars)
        initial_balance = 80.0

        engine = BacktestEngine(initial_balance=initial_balance, risk_per_trade_pct=0.5)
        res_bt = engine.run_backtest(df_full, symbol=symbol, spread_pips=2.5 if "XAU" in symbol else 15.0)
        m = res_bt["metrics"]

        print(f"\n>>> SYMBOL: {symbol} (Starting Capital: ${initial_balance:.2f}) <<<")
        print(f"{'Performance Metric':<32} | {'$80 Micro Account Result':<25}")
        print("-" * 65)
        print(f"{'Total Trades Executed':<32} | {m.get('total_trades', 0):<25}")
        print(f"{'Winning Trades':<32} | {m.get('wins', 0):<25}")
        print(f"{'Losing Trades':<32} | {m.get('losses', 0):<25}")
        print(f"{'Win Rate %':<32} | {m.get('win_rate_pct', 0.0):<24.2f}%")
        print(f"{'Profit Factor':<32} | {m.get('profit_factor', 0.0):<25.2f}")
        print(f"{'Net Profit ($)':<32} | ${m.get('net_profit', 0.0):<24.2f}")
        print(f"{'Final Account Balance':<32} | ${res_bt.get('final_balance', 80.0):<24.2f}")
        print(f"{'Account ROI Growth %':<32} | {((res_bt.get('final_balance', 80.0) - 80.0) / 80.0 * 100.0):<24.2f}%")
        print(f"{'Sharpe Ratio':<32} | {m.get('sharpe_ratio', 0.0):<25.2f}")
        print(f"{'Max Drawdown %':<32} | {m.get('max_drawdown_pct', 0.0):<24.2f}%")
        print("=" * 65)

if __name__ == "__main__":
    run_80_dollar_account_backtest(["XAUUSD", "BTCUSD"], num_bars=4320)
