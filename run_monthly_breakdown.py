"""
JARVIS AI 4.0 — Month-by-Month Multi-Asset Backtest Performance Suite.
Evaluates performance across 6 individual monthly partitions (720 H1 bars per month) for XAUUSD & BTCUSD.
"""
import sys
import logging
import pandas as pd
import numpy as np

from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine

logging.basicConfig(level=logging.WARNING)

def run_monthly_breakdown(symbols: list = ["XAUUSD", "BTCUSD"], bars_per_month: int = 720, num_months: int = 6):
    feed = DataFeedEngine()
    total_bars = bars_per_month * num_months

    month_names = ["Month 1 (Mar)", "Month 2 (Apr)", "Month 3 (May)", "Month 4 (Jun)", "Month 5 (Jul)", "Month 6 (Aug)"]

    print("=" * 95)
    print("          JARVIS AI 4.0 — MONTH-BY-MONTH HISTORICAL PERFORMANCE BREAKDOWN")
    print("=" * 95)

    for symbol in symbols:
        df_full = feed.fetch_rates(symbol, timeframe="H1", num_bars=total_bars)
        balance = 10000.0

        print(f"\n>>> SYMBOL: {symbol} (Starting Capital: ${balance:,.2f}) <<<")
        print(f"{'Month':<16} | {'Trades':<8} | {'Wins':<6} | {'Losses':<8} | {'Win Rate %':<12} | {'Profit Factor':<15} | {'Net Profit ($)':<15} | {'Ending Balance':<15}")
        print("-" * 105)

        total_wins = 0
        total_losses = 0
        total_trades = 0

        for m_idx in range(num_months):
            start_b = m_idx * bars_per_month
            end_b = (m_idx + 1) * bars_per_month
            df_month = df_full.iloc[start_b:end_b].reset_index(drop=True)

            engine = BacktestEngine(initial_balance=balance, risk_per_trade_pct=0.5)
            res = engine.run_backtest(df_month, symbol=symbol, spread_pips=2.5 if "XAU" in symbol else 15.0)
            m = res["metrics"]

            trades = m.get("total_trades", 0)
            wins = m.get("wins", 0)
            losses = m.get("losses", 0)
            win_rate = m.get("win_rate_pct", 0.0)
            pf = m.get("profit_factor", 0.0)
            net_p = m.get("net_profit", 0.0)
            balance = res["final_balance"]

            total_trades += trades
            total_wins += wins
            total_losses += losses

            m_name = month_names[m_idx] if m_idx < len(month_names) else f"Month {m_idx+1}"
            print(f"{m_name:<16} | {trades:<8} | {wins:<6} | {losses:<8} | {win_rate:<11.2f}% | {pf:<15.2f} | ${net_p:<14.2f} | ${balance:<14.2f}")

        overall_wr = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
        print("-" * 105)
        print(f"{'6-MONTH TOTAL':<16} | {total_trades:<8} | {total_wins:<6} | {total_losses:<8} | {overall_wr:<11.2f}% | {'-':<15} | ${balance - 10000.0:<14.2f} | ${balance:<14.2f}")
        print("=" * 105)

if __name__ == "__main__":
    run_monthly_breakdown(["XAUUSD", "BTCUSD"])
