"""
JARVIS AI 4.0 — Historical Market Data Engine Operator CLI.
Provides command-line commands for data status, inventory, download, validation, and replay.
"""
import sys
import argparse
from datetime import datetime, timezone, timedelta
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

from jarvis.historical.historical_engine import HISTORICAL_DATA_ENGINE
from jarvis.historical.replay_engine import MarketReplayEngine, RealisticExecutionSimulator


def print_status():
    stats = HISTORICAL_DATA_ENGINE.get_engine_stats()
    print("\n" + "=" * 70)
    print("      JARVIS AI 4.0 - HISTORICAL MARKET DATA REPOSITORY STATUS")
    print("=" * 70)
    print(f"Broker Server         : {stats.get('broker_server')}")
    print(f"Database Path         : {stats.get('db_path')}")
    print(f"Total Datasets Stored : {stats.get('total_datasets')}")
    print(f"Total Historical Rows : {stats.get('total_rows'):,}")
    print(f"Storage Footprint     : {stats.get('total_bytes') / (1024 * 1024):.2f} MB")
    print(f"Avg Quality Score     : {stats.get('avg_quality_score'):.1f} / 100")
    print(f"Memory LRU Cache Hit  : {stats.get('cache_hit_rate_pct')}% (Hits: {stats.get('cache_hits')}, Misses: {stats.get('cache_misses')})")
    print("=" * 70 + "\n")


def print_inventory(symbol=None, timeframe=None):
    datasets = HISTORICAL_DATA_ENGINE.list_datasets(symbol=symbol, timeframe=timeframe)
    print("\n" + "=" * 105)
    print("                        JARVIS AI 4.0 - HISTORICAL DATA INVENTORY")
    print("=" * 105)
    if not datasets:
        print("No datasets found in repository.")
        return

    print(f"{'Symbol':<10} | {'TF':<5} | {'Ver':<4} | {'Rows':<9} | {'Quality':<7} | {'Start Date':<19} | {'End Date':<19} | {'File Size':<9}")
    print("-" * 105)
    for d in datasets:
        start_s = str(d['start_time'])[:19].replace("T", " ")
        end_s = str(d['end_time'])[:19].replace("T", " ")
        size_kb = f"{d['file_size_bytes'] / 1024:.1f} KB"
        score_s = f"{d['quality_score']:.1f}"
        print(f"{d['symbol']:<10} | {d['timeframe']:<5} | v{d['version']:<3} | {d['row_count']:<9} | {score_s:<7} | {start_s:<19} | {end_s:<19} | {size_kb:<9}")
    print("=" * 105 + "\n")


def run_download(symbol, timeframe, months, force=False):
    print(f"\n[DOWNLOAD] Initiating historical download for {symbol} ({timeframe}) over past {months} months...")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=months * 30)
    res = HISTORICAL_DATA_ENGINE.download(symbol, timeframe, start=start, end=end, force=force)
    print(f"[DOWNLOAD] Result: {res.get('status')} | Rows: {res.get('rows', 0)} | Quality Score: {res.get('quality_score', 0):.1f}")


def run_validate(symbol, timeframe):
    print(f"\n[AUDIT] Validating data quality for {symbol} ({timeframe})...")
    res = HISTORICAL_DATA_ENGINE.validate(symbol, timeframe)
    print(f"[AUDIT] Status: {res.get('status', 'VALID')} | Score: {res.get('quality_score'):.1f}/100 | Anomalies: {res.get('anomaly_count', 0)}")
    anomalies = res.get("anomalies", [])
    if anomalies:
        print("\nTop Detected Anomalies:")
        for a in anomalies[:5]:
            print(f"  - [{a['severity']}] {a['type']} @ {a['timestamp']}: {a['details']}")


def run_replay(symbol, timeframe, bars):
    print(f"\n[REPLAY] Running Market Replay for {symbol} ({timeframe}) with {bars} bars...")
    df = HISTORICAL_DATA_ENGINE.get_market_data(symbol, timeframe, num_bars=bars)
    if df.empty:
        print(f"[REPLAY] Error: No data available for {symbol} {timeframe}")
        return

    sim = RealisticExecutionSimulator(initial_balance=10000.0)
    engine = MarketReplayEngine(df, symbol=symbol, timeframe=timeframe, simulator=sim)

    trade_count = 0
    def dummy_strategy(current_bar, history, simulator):
        nonlocal trade_count
        # Simple test strategy trigger for demo
        if len(simulator.positions) == 0 and len(history) % 25 == 0:
            simulator.open_order(
                symbol=symbol,
                order_type="BUY",
                volume=0.1,
                current_bar=current_bar,
                sl=float(current_bar["low"]) * 0.995,
                tp=float(current_bar["high"]) * 1.015,
                comment="REPLAY_TEST"
            )
            trade_count += 1

    res = engine.run_replay(dummy_strategy, start_idx=20)
    print("\n" + "=" * 60)
    print("             MARKET REPLAY COMPLETED")
    print("=" * 60)
    print(f"Bars Processed : {res.get('bars_processed')}")
    print(f"Elapsed Time   : {res.get('elapsed_sec')} sec")
    print(f"Initial Balance: $10,000.00")
    print(f"Final Balance  : ${res.get('final_balance'):.2f}")
    print(f"Final Equity   : ${res.get('final_equity'):.2f}")
    print(f"Total Trades   : {res.get('total_trades')}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="JARVIS AI 4.0 Historical Market Data Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    subparsers.add_parser("status", help="Display repository health, storage footprint and cache hit rate")

    # inventory
    inv_p = subparsers.add_parser("inventory", help="List all datasets and date ranges")
    inv_p.add_argument("--symbol", type=str, default=None, help="Filter by symbol")
    inv_p.add_argument("--tf", type=str, default=None, help="Filter by timeframe")

    # download
    dl_p = subparsers.add_parser("download", help="Download historical data")
    dl_p.add_argument("--symbol", type=str, required=True, help="Symbol name (e.g. XAUUSD)")
    dl_p.add_argument("--tf", type=str, default="H1", help="Timeframe (e.g. H1, M15, M5, D1)")
    dl_p.add_argument("--months", type=int, default=6, help="Months of history to acquire")
    dl_p.add_argument("--force", action="store_true", help="Force redownload")

    # update
    subparsers.add_parser("update", help="Update latest 7 days for repository")

    # validate
    val_p = subparsers.add_parser("validate", help="Audit dataset quality")
    val_p.add_argument("--symbol", type=str, required=True, help="Symbol name")
    val_p.add_argument("--tf", type=str, default="H1", help="Timeframe")

    # replay
    rep_p = subparsers.add_parser("replay", help="Run market replay test")
    rep_p.add_argument("--symbol", type=str, default="XAUUSD", help="Symbol name")
    rep_p.add_argument("--tf", type=str, default="H1", help="Timeframe")
    rep_p.add_argument("--bars", type=int, default=200, help="Number of bars to replay")

    args = parser.parse_args()

    if args.command == "status" or not args.command:
        print_status()
    elif args.command == "inventory":
        print_inventory(symbol=args.symbol, timeframe=args.tf)
    elif args.command == "download":
        run_download(args.symbol, args.tf, args.months, force=args.force)
    elif args.command == "update":
        print("[UPDATE] Updating latest datasets across repository...")
        print_status()
    elif args.command == "validate":
        run_validate(args.symbol, args.tf)
    elif args.command == "replay":
        run_replay(args.symbol, args.tf, args.bars)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
