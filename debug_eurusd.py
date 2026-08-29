import sys
import logging
import pandas as pd
from jarvis.market.data_feed import DataFeedEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.data.symbol_registry import resolve as resolve_symbol
import MetaTrader5 as mt5

logging.basicConfig(level=logging.ERROR)

def debug_eurusd():
    mt5.initialize()
    symbol = "EURUSD"
    broker_sym = "EURUSD"
    mt5.symbol_select(broker_sym, True)
    rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_H1, 0, 1000)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()

    spec = resolve_symbol(symbol)
    bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5, commission_per_lot=5.0)
    res = bt.run_backtest(df, symbol=symbol, spread_pips=spec.typical_spread_pips)

    trades = res.get("trades", [])
    for t in trades:
        res_str = "[WIN] " if t.get('pnl', 0) > 0 else "[LOSS]"
        print(f"{res_str} {t.get('strategy', 'UNK')} | {t.get('type')} | PNL: ${t.get('pnl', 0):.2f} | Entry: {t.get('entry')} | SL: {t.get('sl')} | TP: {t.get('tp')}")
        print(f"    Exit Reason: {t.get('result')} | Exit Price: {t.get('exit')}")

    mt5.shutdown()

if __name__ == "__main__":
    debug_eurusd()
