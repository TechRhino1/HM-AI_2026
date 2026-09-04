"""
JARVIS AI 4.0 — Complete 6-Month Multi-Symbol Historical Backtest Runner.
Downloads/validates real 6-month MT5 history across all 13 institutional symbols,
executes backtests, performs 6-fold walk-forward validation, and computes portfolio metrics.
"""
import os
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.historical.historical_engine import HISTORICAL_DATA_ENGINE
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.walk_forward import WalkForwardEngine
from jarvis.backtesting.metrics import PerformanceMetricsCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AllSymbolsBacktest")

SYMBOLS = [
    "XAUUSD", "BTCUSD", "ETHUSD", "SOLUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
    "US500", "NAS100", "US30", "WTI"
]

ASSET_CLASS_MAP = {
    "XAUUSD": "Metal",
    "BTCUSD": "Crypto",
    "ETHUSD": "Crypto",
    "SOLUSD": "Crypto",
    "EURUSD": "Forex",
    "GBPUSD": "Forex",
    "USDJPY": "Forex",
    "AUDUSD": "Forex",
    "USDCHF": "Forex",
    "US500": "Index",
    "NAS100": "Index",
    "US30": "Index",
    "WTI": "Commodity"
}


def run_complete_6month_backtest():
    print("=" * 115)
    print("         JARVIS AI 4.0 — COMPLETE 6-MONTH HISTORICAL BACKTEST (ALL 13 SYMBOLS)")
    print("         Historical Data Engine: Local Parquet Data Lake + Real MT5 Execution")
    print("=" * 115)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=182)

    # Phase 1: Ingest & Cache 6-Month Real MT5 Data for All Symbols
    print("\n[PHASE 1] Ensuring 6-Month Real Market Data Lake for all 13 symbols...")
    print(f"{'Symbol':<10} | {'Class':<10} | {'Status':<14} | {'Bars':<8} | {'Quality':<8} | {'Date Range'}")
    print("-" * 115)

    datasets_meta = {}
    for sym in SYMBOLS:
        t0 = time.time()
        res = HISTORICAL_DATA_ENGINE.download(sym, timeframe="H1", start=start_time, end=end_time, force=False)
        df = HISTORICAL_DATA_ENGINE.get_market_data(sym, timeframe="H1", start=start_time, end=end_time)
        datasets_meta[sym] = {
            "df": df,
            "status": res.get("status", "OK"),
            "rows": len(df),
            "quality_score": res.get("quality_score", 100.0),
            "manifest": res.get("manifest", {})
        }
        start_date_str = str(df['time'].iloc[0])[:10] if not df.empty else "N/A"
        end_date_str = str(df['time'].iloc[-1])[:10] if not df.empty else "N/A"
        q_score = res.get("quality_score", 100.0)
        status_str = res.get("status", "SYNC_SUCCESS")
        print(f"{sym:<10} | {ASSET_CLASS_MAP.get(sym, 'Unknown'):<10} | {status_str:<14} | {len(df):<8} | {q_score:<8.1f} | {start_date_str} to {end_date_str}")

    # Phase 2: Run Continuous Backtest & Walk-Forward Validation
    print("\n[PHASE 2] Executing Event-Driven Backtests & 6-Fold Walk-Forward Validations...")
    all_results = {}
    all_trades: List[Dict[str, Any]] = []
    initial_balance = 10000.0

    for sym in SYMBOLS:
        df = datasets_meta[sym]["df"]
        if df.empty or len(df) < 50:
            print(f"[-] Insufficient data for {sym} ({len(df)} bars), skipping.")
            continue

        print(f"[BACKTEST] Running {sym} ({len(df)} H1 bars)...", end=" ", flush=True)
        t_start = time.time()

        # Run Backtest
        bt_engine = BacktestEngine(initial_balance=initial_balance, risk_per_trade_pct=0.5)
        bt_res = bt_engine.run_backtest(df, symbol=sym)

        # Run Walk-Forward Validation
        wf_engine = WalkForwardEngine(num_folds=6, in_sample_pct=0.70, initial_balance=initial_balance)
        wf_res = wf_engine.run_walk_forward_validation(df, symbol=sym)

        m = bt_res.get("metrics", {})
        oos_m = wf_res.get("aggregate_oos_metrics", {})

        m["symbol"] = sym
        m["asset_class"] = ASSET_CLASS_MAP.get(sym, "Unknown")
        m["bars_tested"] = len(df)
        m["in_sample_win_rate"] = m.get("win_rate_pct", 0.0)
        m["oos_win_rate"] = oos_m.get("win_rate_pct", m.get("win_rate_pct", 0.0))
        m["oos_profit_factor"] = oos_m.get("profit_factor", m.get("profit_factor", 0.0))
        m["wfe"] = wf_res.get("walk_forward_efficiency", 1.0)
        m["final_balance"] = bt_res.get("final_balance", initial_balance)
        m["net_profit"] = m["final_balance"] - initial_balance
        m["roi_pct"] = (m["net_profit"] / initial_balance) * 100.0

        trades = bt_res.get("trades", [])
        for tr in trades:
            tr["symbol"] = sym
        all_trades.extend(trades)

        all_results[sym] = m
        elapsed = time.time() - t_start
        print(f"Done ({elapsed:.1f}s) -> {m.get('total_trades', 0)} trades | WinRate: {m.get('win_rate_pct', 0.0):.1f}% | Profit: ${m['net_profit']:+,.2f} | PF: {m.get('profit_factor', 0.0):.2f}")

    # Phase 3: Display Detailed Multi-Symbol Performance Table
    print("\n" + "=" * 135)
    print("                                      JARVIS AI 4.0 — 6-MONTH BACKTEST SUMMARY TABLE")
    print("=" * 135)
    print(f"{'Symbol':<8} | {'Class':<9} | {'Bars':<6} | {'Trades':<7} | {'Win %':<7} | {'OOS Win%':<8} | {'Profit Factor':<13} | {'Net Profit':<12} | {'ROI %':<8} | {'Max DD %':<8} | {'Sharpe':<6} | {'WFE':<5}")
    print("-" * 135)

    total_net_profit = 0.0
    total_trades_count = 0
    total_wins = 0

    for sym in SYMBOLS:
        if sym not in all_results:
            continue
        res = all_results[sym]
        total_net_profit += res.get("net_profit", 0.0)
        total_trades_count += res.get("total_trades", 0)
        total_wins += res.get("winning_trades", 0)

        print(
            f"{sym:<8} | "
            f"{res.get('asset_class'):<9} | "
            f"{res.get('bars_tested'):<6} | "
            f"{res.get('total_trades'):<7} | "
            f"{res.get('win_rate_pct', 0.0):<6.1f}% | "
            f"{res.get('oos_win_rate', 0.0):<7.1f}% | "
            f"{res.get('profit_factor', 0.0):<13.2f} | "
            f"${res.get('net_profit', 0.0):<+11.2f} | "
            f"{res.get('roi_pct', 0.0):<+7.1f}% | "
            f"{res.get('max_drawdown_pct', 0.0):<7.2f}% | "
            f"{res.get('sharpe_ratio', 0.0):<6.2f} | "
            f"{res.get('wfe', 0.0):<5.2f}"
        )

    print("=" * 135)

    # Phase 4: Aggregate Portfolio Level Performance
    portfolio_metrics = PerformanceMetricsCalculator.calculate_metrics(all_trades, initial_balance)
    portfolio_roi = ((portfolio_metrics.get("net_profit", 0.0)) / initial_balance) * 100.0

    print("\n" + "=" * 80)
    print("                    COMBINED 13-ASSET PORTFOLIO METRICS")
    print("=" * 80)
    print(f"Total Combined Trades Executed : {portfolio_metrics.get('total_trades', 0)}")
    print(f"Overall Portfolio Win Rate     : {portfolio_metrics.get('win_rate_pct', 0.0):.2f}%")
    print(f"Portfolio Profit Factor        : {portfolio_metrics.get('profit_factor', 0.0):.2f}")
    print(f"Combined Net Profit ($)        : ${portfolio_metrics.get('net_profit', 0.0):+,.2f}")
    print(f"Combined Portfolio Growth ROI  : {portfolio_roi:+.2f}%")
    print(f"Portfolio Max Drawdown         : {portfolio_metrics.get('max_drawdown_pct', 0.0):.2f}%")
    print(f"Portfolio Sharpe Ratio         : {portfolio_metrics.get('sharpe_ratio', 0.0):.2f}")
    print(f"Portfolio Sortino Ratio        : {portfolio_metrics.get('sortino_ratio', 0.0):.2f}")
    print("=" * 80 + "\n")

    # Save summary report to JSON
    report_output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "period_days": 182,
        "symbols_count": len(all_results),
        "symbol_results": all_results,
        "portfolio_metrics": portfolio_metrics
    }
    out_file = os.path.join(BASE_DIR, "backtest_6month_all_symbols.json")
    with open(out_file, "w") as f:
        json.dump(report_output, f, indent=2, default=str)
    print(f"[REPORT] Complete 6-month backtest saved to: {out_file}")

    return report_output


if __name__ == "__main__":
    run_complete_6month_backtest()
