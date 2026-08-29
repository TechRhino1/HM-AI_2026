import sys
import logging
logging.disable(logging.CRITICAL)

import pandas as pd
from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.metrics import PerformanceMetricsCalculator
from jarvis.data.symbol_registry import resolve as resolve_symbol

import MetaTrader5 as mt5

def run_multi_asset_backtest():
    print("=" * 115)
    print("             JARVIS AI 4.0 -- REAL MT5 HISTORICAL DATA QUANTITATIVE BACKTEST (4,380 H1 BARS)")
    print("=" * 115)
    
    mt5_active = mt5.initialize()
    if not mt5_active:
        print(f"Warning: MT5 failed to initialize: {mt5.last_error()}. Falling back to DataFeedEngine.")
        feed = DataFeedEngine()
    else:
        acc = mt5.account_info()
        print(f"[MT5 Feed] Connected to: {acc.server} | Account #{acc.login} | Broker: {acc.company}")
        print("-" * 115)
        feed = None

    symbol_configs = [
        {"name": "XAUUSD", "broker_sym": "GOLD.i#"},
        {"name": "BTCUSD", "broker_sym": "BTCUSD#"},
        {"name": "EURUSD", "broker_sym": "EURUSD"},
        {"name": "GBPUSD", "broker_sym": "GBPUSD"},
        {"name": "USDJPY", "broker_sym": "USDJPY"},
    ]
    
    summary_results = {}
    total_trades_all = 0
    total_net_pnl_all = 0.0
    
    for cfg in symbol_configs:
        sym = cfg["name"]
        broker_sym = cfg["broker_sym"]
        df = None
        
        if mt5_active:
            mt5.symbol_select(broker_sym, True)
            rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_H1, 0, 4380)
            if rates is not None and len(rates) >= 50:
                df = pd.DataFrame(rates)
                df["time"] = pd.to_datetime(df["time"], unit="s")
                df.rename(columns={"tick_volume": "volume"}, inplace=True)
                df = df[["time", "open", "high", "low", "close", "volume"]].copy()
                t_start = df["time"].iloc[0].strftime("%Y-%m-%d")
                t_end = df["time"].iloc[-1].strftime("%Y-%m-%d")
                last_price = df["close"].iloc[-1]
                print(f"Loaded {len(df)} REAL MT5 H1 bars for {sym} [{broker_sym}] from {t_start} to {t_end} (Price: {last_price})")

        if df is None or len(df) < 50:
            if feed is None:
                feed = DataFeedEngine()
            print(f"Fetching synthetic rates for {sym}...")
            df = feed.fetch_rates(sym, timeframe="H1", num_bars=4380)
            t_start = "SYNTHETIC"
            t_end = "SYNTHETIC"

        print(f"Running chronological event-driven simulation for {sym} ({len(df)} H1 bars)...")
        spec = resolve_symbol(sym)
        bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5, commission_per_lot=5.0)
        res = bt.run_backtest(df, symbol=sym, spread_pips=spec.typical_spread_pips)
        
        m = res.get("metrics", {})
        trades = res.get("trades", [])
        final_balance = res.get("final_balance", 10000.0)
        net_profit = final_balance - 10000.0
        roi_pct = (net_profit / 10000.0) * 100.0
        
        total_trades_all += len(trades)
        total_net_pnl_all += net_profit
        
        # Strategy breakdown
        strat_breakdown = {}
        regime_breakdown = {}
        for t in trades:
            s = t.get("strategy", "UNKNOWN")
            r = t.get("regime", "GLOBAL")
            strat_breakdown[s] = strat_breakdown.get(s, 0) + 1
            regime_breakdown[r] = regime_breakdown.get(r, 0) + 1
            
        m["final_balance"] = final_balance
        m["net_profit"] = net_profit
        m["roi_pct"] = roi_pct
        m["total_trades"] = len(trades)
        m["winning_trades"] = sum(1 for t in trades if t.get("is_win"))
        m["losing_trades"] = sum(1 for t in trades if not t.get("is_win"))
        m["win_rate_pct"] = (m["winning_trades"] / max(1, m["total_trades"])) * 100.0
        m["strat_breakdown"] = strat_breakdown
        m["regime_breakdown"] = regime_breakdown
        m["date_range"] = f"{t_start} -> {t_end}"
        summary_results[sym] = m

    if mt5_active:
        mt5.shutdown()

    # Print Table
    header = f"{'Metric':<32} | " + " | ".join(f"{sym:<14}" for sym in summary_results.keys())
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    rows = [
        ("Historical Date Range", lambda m: str(m.get('date_range', 'N/A'))[:14]),
        ("Total Trades Executed", lambda m: f"{m.get('total_trades', 0):d}"),
        ("Winning Trades", lambda m: f"{m.get('winning_trades', 0):d}"),
        ("Losing Trades", lambda m: f"{m.get('losing_trades', 0):d}"),
        ("Win Rate %", lambda m: f"{m.get('win_rate_pct', 0.0):.2f} %"),
        ("Profit Factor", lambda m: f"{m.get('profit_factor', 0.0):.2f}"),
        ("Expectancy ($)", lambda m: f"${float(m.get('expectancy_dollars', 0.0)):,.2f}"),
        ("Net Profit ($)", lambda m: f"${float(m.get('net_profit', 0.0)):+,.2f}"),
        ("Final Balance ($)", lambda m: f"${float(m.get('final_balance', 10000.0)):,.2f}"),
        ("6-Month ROI Growth %", lambda m: f"{float(m.get('roi_pct', 0.0)):+.2f} %"),
        ("Max Drawdown %", lambda m: f"{float(m.get('max_drawdown_pct', 0.0)):.2f} %"),
        ("Max Drawdown ($)", lambda m: f"${float(m.get('max_drawdown_dollars', 0.0)):,.2f}"),
        ("Sharpe Ratio", lambda m: f"{m.get('sharpe_ratio', 0.0):.2f}"),
        ("Sortino Ratio", lambda m: f"{m.get('sortino_ratio', 0.0):.2f}"),
        ("Calmar Ratio", lambda m: f"{m.get('calmar_ratio', 0.0):.2f}"),
    ]
    
    for label, fn in rows:
        row_str = f"{label:<32} | " + " | ".join(f"{fn(summary_results[sym]):<14}" for sym in summary_results.keys())
        print(row_str)
        
    print("=" * len(header))
    print(f"PORTFOLIO TOTAL: Total Trades={total_trades_all} | Cumulative Net Profit=${total_net_pnl_all:+,.2f}")
    print("=" * len(header))
    
    # Analyze regimes and strategy distributions
    print("\n--- REGIME & STRATEGY CONFLUENCE DISTRIBUTION ---")
    for sym, m in summary_results.items():
        print(f"[{sym}] Strategies: {m.get('strat_breakdown', {})}")
        print(f"[{sym}] Regimes   : {m.get('regime_breakdown', {})}")
        
    print("\n--- QUANTITATIVE SYSTEM OPTIMIZATION ANALYSIS ---")
    for sym, m in summary_results.items():
        wr = m.get("win_rate_pct", 0.0)
        pf = m.get("profit_factor", 0.0)
        dd = m.get("max_drawdown_pct", 0.0)
        if wr >= 60.0 and pf >= 1.5 and dd <= 5.0:
            print(f"-> [{sym}] OPTIMAL: High mathematical edge (WinRate={wr:.1f}%, PF={pf:.2f}, MaxDD={dd:.1f}%).")
        elif wr < 50.0:
            print(f"-> [{sym}] TUNING RECOMMENDATION: WinRate ({wr:.1f}%) can be improved by tightening gate policy hurdle for low-volatility regimes.")
        elif dd > 5.0:
            print(f"-> [{sym}] TUNING RECOMMENDATION: Drawdown ({dd:.1f}%) can be dampened by scaling position size down during chop.")
        else:
            print(f"-> [{sym}] STABLE: Positive statistical expectancy (PF={pf:.2f}).")

if __name__ == "__main__":
    run_multi_asset_backtest()
