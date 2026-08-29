import sys
import logging
import pandas as pd
from jarvis.backtesting.engine import BacktestEngine
from jarvis.data.symbol_registry import resolve as resolve_symbol
import MetaTrader5 as mt5

logging.basicConfig(level=logging.ERROR)

def debug_eurusd():
    mt5.initialize()
    symbol = "EURUSD"
    broker_sym = "EURUSD"
    mt5.symbol_select(broker_sym, True)
    rates = mt5.copy_rates_from_pos(broker_sym, mt5.TIMEFRAME_H1, 0, 4380)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()

    spec = resolve_symbol(symbol)
    bt = BacktestEngine(initial_balance=10000.0, risk_per_trade_pct=0.5, commission_per_lot=5.0)
    res = bt.run_backtest(df, symbol=symbol, spread_pips=spec.typical_spread_pips)

    trades = res.get("trades", [])
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    losses = sum(1 for t in trades if t.get('pnl', 0) <= 0)
    wr = (wins / len(trades) * 100) if trades else 0
    net = res.get('metrics', {}).get('net_profit', 0)
    print(f"Full 6 Month Backtest: {wins}W / {losses}L (Win Rate: {wr:.1f}%) | Net PNL: ")

    mt5.shutdown()

if __name__ == "__main__":
    debug_eurusd()
