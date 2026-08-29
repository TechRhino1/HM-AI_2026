import sys
import logging
import pandas as pd
from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.data.symbol_registry import resolve as resolve_symbol

logging.basicConfig(level=logging.ERROR)

def debug_eurusd():
    symbol = "EURUSD"
    feed = DataFeedEngine()
    df = feed.fetch_rates(symbol, timeframe="H1", num_bars=1000)

    spec = resolve_symbol(symbol)
    bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5, commission_per_lot=5.0)
    res = bt.run_backtest(df, symbol=symbol, spread_pips=spec.typical_spread_pips)

    trades = res.get("trades", [])
    for t in trades:
        res_str = "[WIN] " if t.get('is_win') else "[LOSS]"
        print(f"{res_str} {t.get('open_time')} | {t.get('strategy', 'UNK')} | {t.get('type')} | PNL: ${t.get('net_profit', 0):.2f} | Entry: {t.get('entry_price')} | SL: {t.get('sl_price')} | TP: {t.get('tp_price')}")
        print(f"    Exit Reason: {t.get('exit_reason')} | Exit Price: {t.get('exit_price')} | RR: {t.get('rr_ratio', 0)}")

if __name__ == "__main__":
    debug_eurusd()
