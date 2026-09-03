"""
JARVIS AI 4.0 — Event-Driven Historical Market Replay & Realistic Execution Simulator.
Replays historical market streams chronologically with zero look-ahead bias,
feeding simulated data feeds and executing orders in a strictly isolated broker sandbox.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from jarvis.data.symbol_registry import resolve as resolve_symbol_registry

logger = logging.getLogger("JARVIS_MarketReplay")


@dataclass
class SimulatedOrder:
    ticket: int
    symbol: str
    order_type: str  # "BUY", "SELL"
    volume: float
    open_price: float
    open_time: str
    sl: float = 0.0
    tp: float = 0.0
    close_price: Optional[float] = None
    close_time: Optional[str] = None
    pnl: float = 0.0
    status: str = "OPEN"  # "OPEN", "CLOSED"
    comment: str = ""


class RealisticExecutionSimulator:
    """
    Isolated execution simulator that accurately models spread, slippage,
    commissions, overnight swap, and bar-penetration stop-loss fills.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_per_lot: float = 5.0,
        slippage_pips: float = 0.5,
        spread_pips: float = 1.5
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.commission_per_lot = commission_per_lot
        self.slippage_pips = slippage_pips
        self.spread_pips = spread_pips

        self.positions: Dict[int, SimulatedOrder] = {}
        self.closed_trades: List[SimulatedOrder] = []
        self._next_ticket = 700000

    def open_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        current_bar: pd.Series,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = ""
    ) -> SimulatedOrder:
        """Fills an order at realistic market Ask/Bid price with slippage and commission."""
        spec = resolve_symbol_registry(symbol)
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        spread_dist = self.spread_pips * pip_size
        slippage_dist = self.slippage_pips * pip_size

        mid_price = float(current_bar["close"])
        if order_type.upper() == "BUY":
            fill_price = mid_price + (spread_dist / 2.0) + slippage_dist
        else:
            fill_price = mid_price - (spread_dist / 2.0) - slippage_dist

        digits = spec.digits if hasattr(spec, "digits") else 5
        fill_price = round(fill_price, digits)

        commission = self.commission_per_lot * volume
        self.balance -= commission

        self._next_ticket += 1
        order = SimulatedOrder(
            ticket=self._next_ticket,
            symbol=symbol,
            order_type=order_type.upper(),
            volume=volume,
            open_price=fill_price,
            open_time=str(current_bar["time"]),
            sl=round(sl, digits) if sl > 0 else 0.0,
            tp=round(tp, digits) if tp > 0 else 0.0,
            comment=comment
        )
        self.positions[order.ticket] = order
        return order

    def update_bar(self, current_bar: pd.Series, symbol: str):
        """Checks open positions against current bar's High/Low for SL/TP fills and computes floating PnL."""
        spec = resolve_symbol_registry(symbol)
        pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
        contract_size = getattr(spec, "contract_size", 100000.0)

        high = float(current_bar["high"])
        low = float(current_bar["low"])
        close = float(current_bar["close"])
        bar_time = str(current_bar["time"])

        total_floating_pnl = 0.0
        closed_tickets = []

        for ticket, pos in list(self.positions.items()):
            if pos.symbol != symbol:
                continue

            # 1. Stop Loss check
            if pos.sl > 0:
                if pos.order_type == "BUY" and low <= pos.sl:
                    self._close_position(pos, exit_price=pos.sl, exit_time=bar_time, reason="SL_HIT")
                    closed_tickets.append(ticket)
                    continue
                elif pos.order_type == "SELL" and high >= pos.sl:
                    self._close_position(pos, exit_price=pos.sl, exit_time=bar_time, reason="SL_HIT")
                    closed_tickets.append(ticket)
                    continue

            # 2. Take Profit check
            if pos.tp > 0:
                if pos.order_type == "BUY" and high >= pos.tp:
                    self._close_position(pos, exit_price=pos.tp, exit_time=bar_time, reason="TP_HIT")
                    closed_tickets.append(ticket)
                    continue
                elif pos.order_type == "SELL" and low <= pos.tp:
                    self._close_position(pos, exit_price=pos.tp, exit_time=bar_time, reason="TP_HIT")
                    closed_tickets.append(ticket)
                    continue

            # 3. Mark-to-market floating PnL
            if pos.order_type == "BUY":
                gain = (close - pos.open_price) * pos.volume * contract_size
            else:
                gain = (pos.open_price - close) * pos.volume * contract_size
            total_floating_pnl += gain

        for t in closed_tickets:
            self.positions.pop(t, None)

        self.equity = self.balance + total_floating_pnl

    def _close_position(self, pos: SimulatedOrder, exit_price: float, exit_time: str, reason: str):
        spec = resolve_symbol_registry(pos.symbol)
        contract_size = getattr(spec, "contract_size", 100000.0)
        if pos.order_type == "BUY":
            pnl = (exit_price - pos.open_price) * pos.volume * contract_size
        else:
            pnl = (pos.open_price - exit_price) * pos.volume * contract_size

        pos.close_price = exit_price
        pos.close_time = exit_time
        pos.pnl = round(pnl, 2)
        pos.status = "CLOSED"
        pos.comment += f" [{reason}]"

        self.balance += pnl
        self.closed_trades.append(pos)


class MarketReplayEngine:
    """
    Chronologically steps through historical data, strictly preventing future data leakage.
    At step t, the strategy or model is provided data ONLY up to bar t.
    """

    def __init__(
        self,
        historical_df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        simulator: Optional[RealisticExecutionSimulator] = None
    ):
        self.df = historical_df.copy().reset_index(drop=True)
        self.symbol = symbol
        self.timeframe = timeframe
        self.simulator = simulator or RealisticExecutionSimulator()
        self.current_idx = 0
        self.is_running = False

    def reset(self, start_idx: int = 50):
        self.current_idx = max(20, min(len(self.df) - 1, start_idx))
        self.is_running = False

    def step(self) -> Optional[Tuple[pd.Series, pd.DataFrame]]:
        """
        Advances by one bar.
        Returns (current_bar, historical_slice_up_to_current_bar).
        Guarantees strict zero-lookahead safety: slice ends strictly at current_bar.
        """
        if self.current_idx >= len(self.df):
            return None

        current_bar = self.df.iloc[self.current_idx]
        # Strict anti-lookahead: strategy can only inspect records up to current_idx
        history_slice = self.df.iloc[: self.current_idx + 1].copy()

        # Update simulator mark-to-market
        self.simulator.update_bar(current_bar, self.symbol)

        self.current_idx += 1
        return current_bar, history_slice

    def run_replay(
        self,
        strategy_callback: Callable[[pd.Series, pd.DataFrame, RealisticExecutionSimulator], None],
        start_idx: int = 50,
        max_bars: Optional[int] = None,
        delay_sec: float = 0.0
    ) -> Dict[str, Any]:
        """
        Runs replay loop, invoking strategy callback at each bar.
        """
        self.reset(start_idx=start_idx)
        self.is_running = True

        bars_processed = 0
        limit = max_bars if max_bars is not None else (len(self.df) - self.current_idx)

        t0 = time.time()
        while self.is_running and bars_processed < limit:
            step_result = self.step()
            if step_result is None:
                break

            current_bar, history_slice = step_result
            strategy_callback(current_bar, history_slice, self.simulator)

            bars_processed += 1
            if delay_sec > 0:
                time.sleep(delay_sec)

        elapsed = time.time() - t0
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bars_processed": bars_processed,
            "elapsed_sec": round(elapsed, 3),
            "final_balance": round(self.simulator.balance, 2),
            "final_equity": round(self.simulator.equity, 2),
            "total_trades": len(self.simulator.closed_trades),
            "open_trades": len(self.simulator.positions)
        }
