"""
JARVIS AI 4.0 — Empirical Validation & Monte Carlo Comparison Suite.
Generates full statistical before-and-after comparison of regime-adaptive TP/SL/partial-close constants.
"""
import sys
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List

logging.disable(logging.CRITICAL)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.backtesting.walk_forward import WalkForwardEngine
from jarvis.backtesting.monte_carlo import MonteCarloSimulator
import jarvis.intelligence.decision_engine as de

def run_variant_experiment(variant_name: str, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
    # Patch decision engine _compute_bias_and_levels
    original_fn = de.DecisionEngine._compute_bias_and_levels

    def patched_compute_bias_and_levels(self, context, regime, analyst_reports, **kwargs):
        tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio, first_target_price, first_target_volume_pct = original_fn(
            self, context, regime, analyst_reports, **kwargs
        )
        is_strong = (
            regime.primary_regime in (de.MarketRegime.TREND_BULL, de.MarketRegime.TREND_BEAR)
            and getattr(regime, "confidence", 0.0) > 0.75
            and getattr(context.momentum, "adx", 0.0) > 25.0
        )
        is_rng = regime.primary_regime in (de.MarketRegime.RANGE, de.MarketRegime.LOW_VOLATILITY)

        if variant_name == "Variant A (Active 3.8R / 25%)":
            if is_strong:
                tp_mult = 3.8
                first_target_volume_pct = 0.25
            elif is_rng:
                tp_mult = 2.2
                first_target_volume_pct = 0.50
            else:
                tp_mult = 2.5
                first_target_volume_pct = 0.50
        elif variant_name == "Variant B (Prior 3.5R / 30%)":
            if is_strong:
                tp_mult = 3.5
                first_target_volume_pct = 0.30
            elif is_rng:
                tp_mult = 2.2
                first_target_volume_pct = 0.50
            else:
                tp_mult = 2.5
                first_target_volume_pct = 0.50
        elif variant_name == "Variant C (Flat 2.5R Baseline)":
            tp_mult = 2.5
            first_target_volume_pct = 0.50
        else:
            tp_mult = 2.5

        if tentative_bias == "BUY":
            tp_price = round(entry_price + (risk_dist * tp_mult), 2)
        elif tentative_bias == "SELL":
            tp_price = round(entry_price - (risk_dist * tp_mult), 2)
        rr_ratio = round(tp_mult, 2)

        return tentative_bias, entry_price, sl_price, tp_price, risk_dist, rr_ratio, first_target_price, first_target_volume_pct

    de.DecisionEngine._compute_bias_and_levels = patched_compute_bias_and_levels

    try:
        # 1. Backtest
        bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5)
        res_bt = bt.run_backtest(df, symbol=symbol)
        m = res_bt["metrics"]

        # 2. Walk-Forward
        wf = WalkForwardEngine(num_folds=2, in_sample_pct=0.70, initial_balance=10000.0, risk_per_trade_pct=0.5)
        res_wf = wf.run_walk_forward_validation(df, symbol=symbol)
        m_oos = res_wf["aggregate_oos_metrics"]

        # 3. Monte Carlo
        mc = MonteCarloSimulator(num_simulations=500)
        trades_for_mc = [{"pnl": t["pnl"]} for t in res_bt["trades"]] if res_bt["trades"] else [{"pnl": 0.0}]
        res_mc = mc.run_simulation(trades_for_mc, initial_balance=10000.0)

        return {
            "variant": variant_name,
            "symbol": symbol,
            "total_trades": m.get("total_trades", 0),
            "win_rate_pct": m.get("win_rate_pct", 0.0),
            "profit_factor": m.get("profit_factor", 0.0),
            "net_profit": m.get("net_profit", 0.0),
            "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": m.get("sharpe_ratio", 0.0),
            "wfe": res_wf.get("walk_forward_efficiency", 0.0),
            "oos_win_rate": m_oos.get("win_rate_pct", 0.0),
            "oos_profit_factor": m_oos.get("profit_factor", 0.0),
            "mc_median_balance": res_mc.get("median_final_balance", 10000.0),
            "mc_95_max_dd": res_mc.get("max_drawdown_95_pct", 0.0),
        }
    finally:
        de.DecisionEngine._compute_bias_and_levels = original_fn

def main():
    feed = DataFeedEngine()
    df_xau = feed.fetch_rates("XAUUSD", timeframe="H1", num_bars=400)
    df_btc = feed.fetch_rates("BTCUSD", timeframe="H1", num_bars=400)

    variants = [
        "Variant A (Active 3.8R / 25%)",
        "Variant B (Prior 3.5R / 30%)",
        "Variant C (Flat 2.5R Baseline)"
    ]

    print("\n" + "=" * 115, flush=True)
    print("      PART C (P2) — WALK-FORWARD & MONTE CARLO REGIME CONSTANTS EMPIRICAL VALIDATION REPORT", flush=True)
    print("=" * 115, flush=True)

    for market_name, sym, df in [("Trending Market (XAUUSD)", "XAUUSD", df_xau), ("Choppy / Volatile Market (BTCUSD)", "BTCUSD", df_btc)]:
        print(f"\n[REGIME TEST] {market_name} [400 H1 Bars]", flush=True)
        print("-" * 115, flush=True)
        print(f"{'Configuration':<32} | {'Win Rate':<10} | {'OOS Win Rate':<13} | {'Profit Factor':<14} | {'OOS PF':<10} | {'Max DD %':<9} | {'WFE':<6} | {'MC 95% DD':<10}", flush=True)
        print("-" * 115, flush=True)

        for v in variants:
            r = run_variant_experiment(v, sym, df)
            print(
                f"{r['variant']:<32} | "
                f"{r['win_rate_pct']:>8.2f}% | "
                f"{r['oos_win_rate']:>11.2f}% | "
                f"{r['profit_factor']:>14.2f} | "
                f"{r['oos_profit_factor']:>10.2f} | "
                f"{r['max_drawdown_pct']:>8.2f}% | "
                f"{r['wfe']:>6.2f} | "
                f"{r['mc_95_max_dd']:>9.2f}%",
                flush=True
            )
        print("-" * 115, flush=True)

    print("\n" + "=" * 115 + "\n", flush=True)

if __name__ == "__main__":
    main()
