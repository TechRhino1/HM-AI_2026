"""
JARVIS AI 3.0 — Platform Supervisor and CLI Manager.
"""
import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
from jarvis.application.state_manager import GLOBAL_STATE

def print_status_hud():
    snap = GLOBAL_STATE.get_state_snapshot()
    acc = snap.get("account") or {}
    print("\n" + "=" * 60)
    print("              JARVIS AI 3.0 COMMAND CENTER              ")
    print("=" * 60)
    print(f"STATUS:          {'🟢 OPERATIONAL' if not snap['safe_mode'] else '🟡 SAFE MODE'}")
    print(f"EXECUTION MODE:  {snap['execution_mode']}")
    print(f"SERVER:          {acc.get('server', 'XMGlobal-MT5')} (#{acc.get('login', 345841337)})")
    print(f"BALANCE / EQ:    ${acc.get('balance', 10000):,.2f} / ${acc.get('equity', 10000):,.2f}")
    print(f"OPEN POSITIONS:  {snap['positions_count']} trades")
    print("-" * 60)
    print("SERVICES HEALTH MATRIX:")
    for s, st in snap["services"].items():
        print(f"  ✓ {s:<18} : {st}")
    print("=" * 60 + "\n")

def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "start"

    if cmd in ["start", "launch", "run"]:
        import threading
        mode = sys.argv[2] if len(sys.argv) > 2 else "paper"
        orchestrator = JarvisOrchestrator(mode=mode)
        orchestrator.start()
        
        server_thread = threading.Thread(target=run_web_server, args=(8501,), daemon=True)
        server_thread.start()

        print_status_hud()
        print(f"🚀 JARVIS AI 3.0 ONLINE at http://localhost:8501 (Mode: {mode.upper()}). Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            orchestrator.stop()
            print("\n🛑 JARVIS AI 3.0 safely terminated.")

    elif cmd in ["status", "health", "info"]:
        print_status_hud()
    elif cmd in ["backtest", "test"]:
        from jarvis.backtesting.engine import BacktestEngine
        from jarvis.market.data_feed import DataFeedEngine
        feed = DataFeedEngine()
        df = feed.fetch_rates("XAUUSD", timeframe="H1", num_bars=500)
        bt = BacktestEngine()
        res = bt.run_backtest(df, symbol="XAUUSD")
        print("\n=== JARVIS 3.0 BACKTEST SUMMARY ===")
        for k, v in res["metrics"].items():
            print(f"  {k}: {v}")
        print(f"  Final Balance: ${res['final_balance']:,.2f}\n")
    else:
        print(f"Unknown command: '{cmd}'")
        print("Usage:")
        print("  python jarvis.py start [paper|live]  -> Start JARVIS 3.0 & Web Terminal")
        print("  python jarvis.py status              -> Display system status HUD")
        print("  python jarvis.py backtest            -> Run quantitative backtest")

if __name__ == "__main__":
    main()
