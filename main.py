"""
JARVIS AI 3.0 — Main CLI Entrypoint.
Provides command-line launching for live/paper trading, radar scans, and historical backtests.
"""
import os
import sys
import time
import argparse
import threading
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
from jarvis.backtesting.engine import BacktestEngine
from jarvis.market.data_feed import DataFeedEngine

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("JARVIS_Main")

def main():
    parser = argparse.ArgumentParser(description="JARVIS AI 3.0 — Professional Trading Intelligence Platform")
    parser.add_argument("--mode", type=str, default="live", choices=["paper", "live", "demo"], help="Execution mode")

    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Primary target symbol")
    parser.add_argument("--once", action="store_true", help="Run a single analytical radar sweep and exit")
    parser.add_argument("--backtest", action="store_true", help="Run historical backtest and exit")
    parser.add_argument("--port", type=int, default=8501, help="Web terminal port")
    args = parser.parse_args()

    if args.backtest:
        logger.info(f"--- STARTING JARVIS 3.0 HISTORICAL BACKTEST FOR {args.symbol} ---")
        feed = DataFeedEngine()
        df = feed.fetch_rates(args.symbol, timeframe="H1", num_bars=500)
        bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
        res = bt.run_backtest(df, symbol=args.symbol)

        logger.info("================================================================================")
        logger.info(f"                 JARVIS 3.0 BACKTEST RESULTS ({args.symbol})                   ")
        logger.info("================================================================================")
        for k, v in res["metrics"].items():
            logger.info(f"  {k}: {v}")
        logger.info(f"  Final Balance: ${res['final_balance']:,.2f}")
        logger.info("================================================================================")
        return

    orchestrator = JarvisOrchestrator(mode=args.mode)

    if args.once:
        logger.info(f"Executing single telemetry sweep for {args.symbol}...")
        res = orchestrator.run_cycle_for_symbol(args.symbol)
        d = res["decision"]
        logger.info(f"Result for {args.symbol}: Decision={d.decision}, Bias={d.bias}, EV=${d.expected_value:.2f}, Gate={d.quality_gate.passed}, Reasons={d.quality_gate.failing_reasons}")
        orchestrator.stop()
        return

    # Start Orchestrator loop
    orchestrator.start()

    # Start Web Dashboard Server in background thread or main
    server_thread = threading.Thread(target=run_web_server, args=(args.port,), daemon=True, name="web_server")
    server_thread.start()

    logger.info(f"JARVIS 3.0 is ONLINE in {args.mode.upper()} mode. Web Terminal at http://localhost:{args.port}")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Termination signal received. Shutting down JARVIS 3.0...")
    finally:
        orchestrator.stop()

if __name__ == "__main__":
    main()
