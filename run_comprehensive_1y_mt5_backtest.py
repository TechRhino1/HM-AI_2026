import sys
import os
import json
import logging
logging.disable(logging.CRITICAL)

import pandas as pd
import numpy as np
from datetime import datetime

from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.metrics import PerformanceMetricsCalculator
from jarvis.data.symbol_registry import resolve as resolve_symbol
import MetaTrader5 as mt5

def run_1y_backtest():
    print("=" * 125)
    print("             JARVIS AI 4.0 -- COMPREHENSIVE 1-YEAR REAL MT5 HISTORICAL BENCHMARK (8,760 H1 BARS)")
    print("=" * 125)

    mt5_active = mt5.initialize()
    if not mt5_active:
        print(f"ERROR: MT5 failed to initialize: {mt5.last_error()}")
        return

    acc = mt5.account_info()
    print(f"[MT5 Broker Connected] Server: {acc.server} | Account #{acc.login} | Broker: {acc.company} | Leverage: 1:{acc.leverage}")
    print("-" * 125)

    symbol_configs = [
        {"name": "XAUUSD", "broker_sym": "GOLD.i#", "asset_class": "COMMODITY"},
        {"name": "BTCUSD", "broker_sym": "BTCUSD#", "asset_class": "CRYPTO"},
        {"name": "EURUSD", "broker_sym": "EURUSD",  "asset_class": "FOREX"},
        {"name": "GBPUSD", "broker_sym": "GBPUSD",  "asset_class": "FOREX"},
        {"name": "USDJPY", "broker_sym": "USDJPY",  "asset_class": "FOREX"},
    ]

    all_symbol_results = {}
    all_trades = []
    total_initial_balance = len(symbol_configs) * 10000.0
    total_final_balance = 0.0
    all_rejection_stats = {}

    for cfg in symbol_configs:
        sym = cfg["name"]
        broker_sym = cfg["broker_sym"]
        mt5.symbol_select(broker_sym, True)
        
        # Pull 8,760 H1 bars (1 full calendar year)
        rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_H1, 0, 8760)
        if rates is None or len(rates) < 50:
            print(f"Error: Unable to fetch MT5 rates for {sym} [{broker_sym}]")
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={"tick_volume": "volume"}, inplace=True)
        df = df[["time", "open", "high", "low", "close", "volume"]].copy()

        t_start = df["time"].iloc[0].strftime("%Y-%m-%d %H:%M")
        t_end = df["time"].iloc[-1].strftime("%Y-%m-%d %H:%M")
        last_price = df["close"].iloc[-1]
        print(f"Loaded {len(df)} REAL MT5 H1 bars for {sym} [{broker_sym}] | {t_start} -> {t_end} | Latest Price: {last_price}")

        spec = resolve_symbol(sym)
        engine = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5, commission_per_lot=5.0)
        
        print(f"  -> Simulating 1-year event-driven execution for {sym} ({len(df)} H1 bars)...")
        res = engine.run_backtest(df, symbol=sym, spread_pips=spec.typical_spread_pips)

        trades = res.get("trades", [])
        m = res.get("metrics", {})
        final_bal = res.get("final_balance", 10000.0)
        net_pnl = final_bal - 10000.0
        roi_pct = (net_pnl / 10000.0) * 100.0

        m["symbol"] = sym
        m["broker_sym"] = broker_sym
        m["start_time"] = t_start
        m["end_time"] = t_end
        m["bar_count"] = len(df)
        m["final_balance"] = final_bal
        m["net_profit"] = net_pnl
        m["roi_pct"] = roi_pct
        m["rejections"] = res.get("rejection_stats", {})

        # Compute additional trade metrics
        wins = [t for t in trades if t.get("is_win", False)]
        losses = [t for t in trades if not t.get("is_win", False)]
        m["win_count"] = len(wins)
        m["loss_count"] = len(losses)
        m["win_rate"] = (len(wins) / len(trades) * 100.0) if trades else 0.0
        
        m["avg_win_dollar"] = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0.0
        m["avg_loss_dollar"] = (abs(sum(t["pnl"] for t in losses)) / len(losses)) if losses else 0.0
        m["realized_rr"] = (m["avg_win_dollar"] / m["avg_loss_dollar"]) if m["avg_loss_dollar"] > 0 else 0.0
        m["avg_planned_rr"] = (sum(t.get("planned_rr", 0.0) for t in trades) / len(trades)) if trades else 0.0

        # Holding period
        m["avg_bars_held"] = (sum(t.get("bars_held", 1) for t in trades) / len(trades)) if trades else 0.0

        # Streak calculation
        max_consec_wins = 0
        max_consec_losses = 0
        cur_wins = 0
        cur_losses = 0
        for t in trades:
            if t.get("is_win"):
                cur_wins += 1
                cur_losses = 0
                max_consec_wins = max(max_consec_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_consec_losses = max(max_consec_losses, cur_losses)
        m["max_consec_wins"] = max_consec_wins
        m["max_consec_losses"] = max_consec_losses

        all_symbol_results[sym] = m
        total_final_balance += final_bal
        all_trades.extend(trades)
        
        for rk, rv in res.get("rejection_stats", {}).items():
            all_rejection_stats[rk] = all_rejection_stats.get(rk, 0) + rv

    mt5.shutdown()

    # Calculate Portfolio Aggregate Metrics
    portfolio_pnl = total_final_balance - total_initial_balance
    portfolio_roi = (portfolio_pnl / total_initial_balance) * 100.0
    portfolio_metrics = PerformanceMetricsCalculator.calculate_metrics(all_trades, total_initial_balance)
    
    port_wins = [t for t in all_trades if t.get("is_win", False)]
    port_losses = [t for t in all_trades if not t.get("is_win", False)]
    avg_win_p = (sum(t["pnl"] for t in port_wins) / len(port_wins)) if port_wins else 0.0
    avg_loss_p = (abs(sum(t["pnl"] for t in port_losses)) / len(port_losses)) if port_losses else 0.0
    realized_rr_p = (avg_win_p / avg_loss_p) if avg_loss_p > 0 else 0.0
    avg_planned_rr_p = (sum(t.get("planned_rr", 0.0) for t in all_trades) / len(all_trades)) if all_trades else 0.0
    avg_bars_p = (sum(t.get("bars_held", 1) for t in all_trades) / len(all_trades)) if all_trades else 0.0

    p_wins = 0
    p_losses = 0
    p_max_cw = 0
    p_max_cl = 0
    # Sort all trades chronologically if open_time exists
    all_trades_sorted = sorted(all_trades, key=lambda x: str(x.get("open_time", x.get("exit_time", ""))))
    for t in all_trades_sorted:
        if t.get("is_win"):
            p_wins += 1
            p_losses = 0
            p_max_cw = max(p_max_cw, p_wins)
        else:
            p_losses += 1
            p_wins = 0
            p_max_cl = max(p_max_cl, p_losses)

    print("\n" + "=" * 125)
    print("                                1-YEAR MULTI-ASSET PERFORMANCE SUMMARY TABLE")
    print("=" * 125)
    header = f"{'Metric':<32} | " + " | ".join(f"{sym:<13}" for sym in all_symbol_results.keys()) + f" | {'PORTFOLIO':<13}"
    print(header)
    print("-" * len(header))

    def fmt_curr(v): return f""
    def fmt_signed(v): return f""
    def fmt_pct(v): return f"{v:.2f}%"

    rows = [
        ("Historical Date Span", lambda m: f"{m['start_time'][:7]}->{m['end_time'][:7]}", f"12-18 Months"),
        ("Total Bars Simulated", lambda m: f"{m['bar_count']:,d} H1", f"{len(symbol_configs)*8760:,d} H1"),
        ("Initial Balance ($)", lambda m: ",000.00", f""),
        ("Final Balance ($)", lambda m: fmt_curr(m['final_balance']), fmt_curr(total_final_balance)),
        ("Net Profit / Loss ($)", lambda m: fmt_signed(m['net_profit']), fmt_signed(portfolio_pnl)),
        ("1-Year ROI Growth %", lambda m: f"{m['roi_pct']:+.2f}%", f"{portfolio_roi:+.2f}%"),
        ("Total Trades Executed", lambda m: f"{m.get('total_trades', 0):d}", f"{len(all_trades):d}"),
        ("Winning Trades", lambda m: f"{m.get('win_count', 0):d}", f"{len(port_wins):d}"),
        ("Losing Trades", lambda m: f"{m.get('loss_count', 0):d}", f"{len(port_losses):d}"),
        ("Win Rate %", lambda m: fmt_pct(m.get('win_rate', 0.0)), fmt_pct((len(port_wins)/max(1, len(all_trades)))*100.0)),
        ("Profit Factor", lambda m: f"{m.get('profit_factor', 0.0):.2f}", f"{portfolio_metrics.get('profit_factor', 0.0):.2f}"),
        ("Expectancy per Trade ($)", lambda m: fmt_signed(m.get('expectancy_dollars', 0.0)), fmt_signed(portfolio_metrics.get('expectancy_dollars', 0.0))),
        ("Average Win ($)", lambda m: fmt_curr(m.get('avg_win_dollar', 0.0)), fmt_curr(avg_win_p)),
        ("Average Loss ($)", lambda m: fmt_curr(m.get('avg_loss_dollar', 0.0)), fmt_curr(avg_loss_p)),
        ("Realized R:R Ratio", lambda m: f"1:{m.get('realized_rr', 0.0):.2f}", f"1:{realized_rr_p:.2f}"),
        ("Average Planned R:R", lambda m: f"1:{m.get('avg_planned_rr', 0.0):.2f}", f"1:{avg_planned_rr_p:.2f}"),
        ("Max Consecutive Wins", lambda m: f"{m.get('max_consec_wins', 0):d}", f"{p_max_cw:d}"),
        ("Max Consecutive Losses", lambda m: f"{m.get('max_consec_losses', 0):d}", f"{p_max_cl:d}"),
        ("Avg Holding Period (Hours)", lambda m: f"{m.get('avg_bars_held', 0.0):.1f}h", f"{avg_bars_p:.1f}h"),
        ("Max Drawdown ($)", lambda m: fmt_curr(m.get('max_drawdown_dollars', 0.0)), fmt_curr(portfolio_metrics.get('max_drawdown_dollars', 0.0))),
        ("Max Drawdown %", lambda m: fmt_pct(m.get('max_drawdown_pct', 0.0)), fmt_pct(portfolio_metrics.get('max_drawdown_pct', 0.0))),
        ("Sharpe Ratio", lambda m: f"{m.get('sharpe_ratio', 0.0):.2f}", f"{portfolio_metrics.get('sharpe_ratio', 0.0):.2f}"),
        ("Sortino Ratio", lambda m: f"{m.get('sortino_ratio', 0.0):.2f}", f"{portfolio_metrics.get('sortino_ratio', 0.0):.2f}"),
        ("Calmar Ratio", lambda m: f"{m.get('calmar_ratio', 0.0):.2f}", f"{portfolio_metrics.get('calmar_ratio', 0.0):.2f}"),
    ]

    for label, fn, p_val in rows:
        row_str = f"{label:<32} | " + " | ".join(f"{fn(all_symbol_results[sym]):<13}" for sym in all_symbol_results.keys()) + f" | {p_val:<13}"
        print(row_str)

    print("=" * len(header))

    # --- STRATEGY-BY-STRATEGY BREAKDOWN ---
    print("\n" + "=" * 115)
    print("                                STRATEGY-BY-STRATEGY PERFORMANCE BREAKDOWN")
    print("=" * 115)
    strat_groups = {}
    for t in all_trades:
        st = t.get("strategy", "UNKNOWN")
        if st not in strat_groups:
            strat_groups[st] = []
        strat_groups[st].append(t)

    strat_header = f"{'Strategy Name':<28} | {'Trades':<8} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'Gross Win':<12} | {'Gross Loss':<12} | {'Net PnL':<12} | {'PF':<6} | {'Avg PnL':<10}"
    print(strat_header)
    print("-" * len(strat_header))

    for st, s_trades in sorted(strat_groups.items(), key=lambda x: len(x[1]), reverse=True):
        s_wins = [t for t in s_trades if t.get("is_win")]
        s_losses = [t for t in s_trades if not t.get("is_win")]
        s_wr = (len(s_wins) / len(s_trades)) * 100.0
        s_gross_win = sum(t["pnl"] for t in s_wins)
        s_gross_loss = abs(sum(t["pnl"] for t in s_losses))
        s_net = sum(t["pnl"] for t in s_trades)
        s_pf = (s_gross_win / s_gross_loss) if s_gross_loss > 0 else (99.0 if s_gross_win > 0 else 0.0)
        s_avg = s_net / len(s_trades)
        print(f"{st:<28} | {len(s_trades):<8d} | {len(s_wins):<6d} | {len(s_losses):<6d} | {s_wr:>8.2f}% |  |  |  | {s_pf:>6.2f} | ")
    print("=" * len(strat_header))

    # --- PERFORMANCE BY MARKET REGIME ---
    print("\n" + "=" * 115)
    print("                                PERFORMANCE BY DETECTED MARKET REGIME")
    print("=" * 115)
    reg_groups = {}
    for t in all_trades:
        r = t.get("regime", "GLOBAL")
        if r not in reg_groups:
            reg_groups[r] = []
        reg_groups[r].append(t)

    reg_header = f"{'Market Regime':<25} | {'Trades':<8} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'Net PnL':<14} | {'Profit Factor':<14} | {'Avg PnL/Trade':<14}"
    print(reg_header)
    print("-" * len(reg_header))

    for r, r_trades in sorted(reg_groups.items(), key=lambda x: len(x[1]), reverse=True):
        r_wins = [t for t in r_trades if t.get("is_win")]
        r_losses = [t for t in r_trades if not t.get("is_win")]
        r_wr = (len(r_wins) / len(r_trades)) * 100.0
        r_gw = sum(t["pnl"] for t in r_wins)
        r_gl = abs(sum(t["pnl"] for t in r_losses))
        r_net = sum(t["pnl"] for t in r_trades)
        r_pf = (r_gw / r_gl) if r_gl > 0 else (99.0 if r_gw > 0 else 0.0)
        r_avg = r_net / len(r_trades)
        print(f"{r:<25} | {len(r_trades):<8d} | {len(r_wins):<6d} | {len(r_losses):<6d} | {r_wr:>8.2f}% |  | {r_pf:>14.2f} | ")
    print("=" * len(reg_header))

    # --- MONTHLY PERFORMANCE BREAKDOWN ---
    print("\n" + "=" * 115)
    print("                                MONTHLY PERFORMANCE BREAKDOWN")
    print("=" * 115)
    month_groups = {}
    for t in all_trades:
        t_time = t.get("open_time") or t.get("exit_time")
        m_key = "UNKNOWN"
        if t_time is not None:
            if hasattr(t_time, "strftime"):
                m_key = t_time.strftime("%Y-%m")
            else:
                m_key = str(t_time)[:7]
        if m_key not in month_groups:
            month_groups[m_key] = []
        month_groups[m_key].append(t)

    month_header = f"{'Month (YYYY-MM)':<18} | {'Trades':<8} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'Gross Win':<12} | {'Gross Loss':<12} | {'Net PnL':<12} | {'PF':<6}"
    print(month_header)
    print("-" * len(month_header))

    cum_m_pnl = 0.0
    for m_key in sorted(month_groups.keys()):
        m_trades = month_groups[m_key]
        m_wins = [t for t in m_trades if t.get("is_win")]
        m_losses = [t for t in m_trades if not t.get("is_win")]
        m_wr = (len(m_wins) / len(m_trades)) * 100.0 if m_trades else 0.0
        m_gw = sum(t["pnl"] for t in m_wins)
        m_gl = abs(sum(t["pnl"] for t in m_losses))
        m_net = sum(t["pnl"] for t in m_trades)
        m_pf = (m_gw / m_gl) if m_gl > 0 else (99.0 if m_gw > 0 else 0.0)
        cum_m_pnl += m_net
        print(f"{m_key:<18} | {len(m_trades):<8d} | {len(m_wins):<6d} | {len(m_losses):<6d} | {m_wr:>8.2f}% |  |  |  | {m_pf:>6.2f}")
    print("=" * len(month_header))

    # --- EXIT REASON DISTRIBUTION ---
    print("\n" + "=" * 115)
    print("                                TRADE EXIT REASON DISTRIBUTION")
    print("=" * 115)
    exit_groups = {}
    for t in all_trades:
        res_k = t.get("result", "UNKNOWN")
        if res_k not in exit_groups:
            exit_groups[res_k] = []
        exit_groups[res_k].append(t)

    exit_header = f"{'Exit Reason':<22} | {'Count':<8} | {'Share %':<10} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'Net PnL':<14} | {'Avg PnL/Trade':<14}"
    print(exit_header)
    print("-" * len(exit_header))

    for ex, e_trades in sorted(exit_groups.items(), key=lambda x: len(x[1]), reverse=True):
        e_wins = [t for t in e_trades if t.get("is_win")]
        e_losses = [t for t in e_trades if not t.get("is_win")]
        e_wr = (len(e_wins) / len(e_trades)) * 100.0
        e_net = sum(t["pnl"] for t in e_trades)
        e_share = (len(e_trades) / len(all_trades)) * 100.0
        e_avg = e_net / len(e_trades)
        print(f"{ex:<22} | {len(e_trades):<8d} | {e_share:>8.1f}% | {len(e_wins):<6d} | {len(e_losses):<6d} | {e_wr:>8.2f}% |  | ")
    print("=" * len(exit_header))

    # --- MISSED OPPORTUNITIES & QUALITY GATE REJECTIONS ---
    print("\n" + "=" * 115)
    print("                     TOP QUALITY GATE REJECTIONS & FILTERED OPPORTUNITIES")
    print("=" * 115)
    sorted_rejections = sorted(all_rejection_stats.items(), key=lambda x: x[1], reverse=True)
    for r_reason, count in sorted_rejections[:15]:
        print(f"  [Filtered x{count:>5d} times] {r_reason}")

    # Save detailed JSON report for deep analysis
    report_dict = {
        "timestamp": datetime.now().isoformat(),
        "total_initial_balance": total_initial_balance,
        "total_final_balance": total_final_balance,
        "net_profit": portfolio_pnl,
        "roi_pct": portfolio_roi,
        "portfolio_metrics": portfolio_metrics,
        "symbols": all_symbol_results,
        "strategies": {st: {"trades": len(tr), "net_pnl": sum(t["pnl"] for t in tr), "win_rate": sum(1 for t in tr if t["is_win"])/len(tr)} for st, tr in strat_groups.items()},
        "regimes": {r: {"trades": len(tr), "net_pnl": sum(t["pnl"] for t in tr), "win_rate": sum(1 for t in tr if t["is_win"])/len(tr)} for r, tr in reg_groups.items()},
        "monthly": {m: {"trades": len(tr), "net_pnl": sum(t["pnl"] for t in tr), "win_rate": sum(1 for t in tr if t["is_win"])/len(tr)} for m, tr in month_groups.items()},
        "exits": {ex: {"trades": len(tr), "net_pnl": sum(t["pnl"] for t in tr), "win_rate": sum(1 for t in tr if t["is_win"])/len(tr)} for ex, tr in exit_groups.items()},
        "rejections": all_rejection_stats,
        "all_trades": all_trades
    }
    with open("baseline_1y_backtest_report.json", "w") as f:
        json.dump(report_dict, f, default=str, indent=2)
    print(f"\n[Artifact Saved] Detailed backtest report dumped to baseline_1y_backtest_report.json")

if __name__ == "__main__":
    run_1y_backtest()
