"""
JARVIS AI 4.0 — Live Multi-Asset Telemetry & Analytical Sweep Suite.
Executes live analytical cycles across XAUUSD, EURUSD, GBPUSD, USDJPY, and BTCUSD.
"""
import sys
import logging

from jarvis.application.orchestrator import JarvisOrchestrator

logging.basicConfig(level=logging.WARNING)

def run_live_sweep(symbols: list = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]):
    print("=" * 95)
    print("          JARVIS AI 4.0 — LIVE MULTI-ASSET ANALYTICAL TELEMETRY SWEEP")
    print("=" * 95)

    orchestrator = JarvisOrchestrator(mode="paper")
    print(f"{'Symbol':<10} | {'Decision':<10} | {'Bias':<8} | {'Strategy':<25} | {'WinProb %':<10} | {'Expected Value ($)':<18} | {'Quality Gate'}")
    print("-" * 95)

    for symbol in symbols:
        res = orchestrator.run_cycle_for_symbol(symbol)
        d = res.get("decision")
        if d:
            gate_status = "PASSED" if d.quality_gate.passed else f"FAILED ({', '.join(d.quality_gate.failing_reasons[:2])})"
            print(f"{symbol:<10} | {d.decision:<10} | {d.bias:<8} | {d.strategy:<25} | {d.model_confidence*100:<9.1f}% | ${d.expected_value:<17.2f} | {gate_status}")

    orchestrator.stop()
    print("=" * 95)

if __name__ == "__main__":
    run_live_sweep()
