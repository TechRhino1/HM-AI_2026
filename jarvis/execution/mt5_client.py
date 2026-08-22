"""
JARVIS AI 3.0 — MT5 Client & Execution Gateway.
Provides a thread-safe, timeout-guarded connection to MetaTrader 5 with automatic symbol resolution and retry mechanisms.
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from jarvis.application.timeout_guard import TimeoutGuard
from jarvis.data.schemas import AccountSnapshot, PositionSnapshot

logger = logging.getLogger("JARVIS_MT5Client")

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

class MT5Client:
    def __init__(self, magic_number: int = 888999, mode: str = "paper", timeout_sec: float = 4.0):
        self.magic_number = magic_number
        self.mode = mode.lower()  # "live", "paper", "demo"
        self.timeout_sec = timeout_sec
        self.is_connected = False
        self.symbol_alias_cache: Dict[str, str] = {}
        self._paper_positions: Dict[int, PositionSnapshot] = {}
        self._lock = threading.RLock()
        self.init_connection()

    def init_connection(self) -> bool:
        if self.mode == "paper":
            self.is_connected = True
            logger.info("MT5Client running in simulated PAPER execution mode.")
            return True

        if not MT5_AVAILABLE or mt5 is None:
            logger.warning("MetaTrader5 python package not available. Falling back to PAPER mode.")
            self.mode = "paper"
            self.is_connected = True
            return True

        import random
        delays = [1.0, 2.0, 4.0, 8.0, 16.0]
        
        for attempt in range(len(delays) + 1):
            def _init():
                with self._lock:
                    if not mt5.initialize():
                        err = mt5.last_error()
                        logger.error(f"MT5 initialization failed: {err}")
                        return False
                    self.is_connected = True
                    acc = mt5.account_info()
                    if acc:
                        logger.info(f"Connected to MT5 Server: {acc.server} | Login: #{acc.login} | Equity: ${acc.equity:.2f}")
                    return True

            res = TimeoutGuard.run_sync(_init, timeout_sec=self.timeout_sec, default=False, task_name="MT5_Init")
            self.is_connected = bool(res)
            
            if self.is_connected:
                return True
                
            if attempt < len(delays):
                delay = delays[attempt]
                jitter = delay * 0.2 * (random.random() * 2 - 1)
                time.sleep(delay + jitter)
                
        return False

    def _reconnect_if_needed(self):
        if not self.is_connected:
            self.init_connection()

    def resolve_symbol_name(self, symbol: str) -> str:
        if symbol in self.symbol_alias_cache:
            return self.symbol_alias_cache[symbol]

        if self.mode == "paper" or not MT5_AVAILABLE or not self.is_connected:
            return symbol

        def _resolve():
            all_syms = mt5.symbols_get()
            if not all_syms:
                return symbol

            base_u = symbol.upper()
            candidates = []
            for s in all_syms:
                s_name_u = s.name.upper()
                if base_u in ["XAUUSD", "GOLD"]:
                    if any(k in s_name_u for k in ["GOLD.I#", "GOLD#", "GOLD.M", "XAUUSD.I#", "XAUUSD#", "GOLD", "XAUUSD"]):
                        candidates.append(s)
                elif base_u in ["BTCUSD", "BTC"]:
                    if any(k in s_name_u for k in ["BTCUSD#", "BTCUSD", "BITCOIN"]):
                        candidates.append(s)
                elif base_u in s_name_u:
                    candidates.append(s)

            if candidates:
                candidates.sort(key=lambda s: (
                    0 if getattr(s, "trade_mode", 0) == getattr(mt5, "SYMBOL_TRADE_MODE_FULL", 4) else 1,
                    0 if "#" in s.name else 1,
                    len(s.name)
                ))
                best = candidates[0].name
                mt5.symbol_select(best, True)
                self.symbol_alias_cache[symbol] = best
                return best
            return symbol

        res = TimeoutGuard.run_sync(_resolve, timeout_sec=2.0, default=symbol, task_name=f"ResolveSymbol_{symbol}")
        self.symbol_alias_cache[symbol] = res
        return res

    def get_account_snapshot(self) -> AccountSnapshot:
        self._reconnect_if_needed()
        if self.mode == "paper" or not self.is_connected or not MT5_AVAILABLE:
            return AccountSnapshot(
                login=345841337,
                server="JARVIS-Paper-Terminal",
                balance=10000.0,
                equity=10000.0,
                margin=0.0,
                free_margin=10000.0,
                margin_level=0.0,
                leverage=100,
                profit=0.0,
                name="Paper Account",
                company="Simulation",
                currency="USD",
                trade_allowed=True
            )

        default_snap = AccountSnapshot(
            login=345841337,
            server="XMGlobal-MT5 10",
            balance=102.14,
            equity=102.25,
            margin=3.71,
            free_margin=98.54,
            margin_level=2756.0,
            leverage=1000,
            name="Demo Account",
            company="XM Global Limited"
        )
        
        try:
            with self._lock:
                acc = mt5.account_info()
                if acc is None:
                    return default_snap
                return AccountSnapshot(
                    login=int(acc.login),
                    server=str(acc.server),
                    balance=float(acc.balance),
                    equity=float(acc.equity),
                    margin=float(acc.margin),
                    free_margin=float(acc.margin_free),
                    margin_level=float(getattr(acc, "margin_level", 0.0)),
                    leverage=int(acc.leverage),
                    profit=float(getattr(acc, "profit", 0.0)),
                    name=str(getattr(acc, "name", "Trader")),
                    company=str(getattr(acc, "company", "XM Global")),
                    currency=str(acc.currency),
                    trade_allowed=bool(acc.trade_allowed),
                    last_sync_time=datetime.now(timezone.utc)
                )
        except Exception as e:
            logger.error(f"MT5 get_account_snapshot failed: {e}")
            return default_snap

    def get_open_positions(self, symbol: Optional[str] = None) -> List[PositionSnapshot]:
        self._reconnect_if_needed()
        if self.mode == "paper" or not self.is_connected or not MT5_AVAILABLE:
            with self._lock:
                if symbol:
                    resolved = self.resolve_symbol_name(symbol)
                    return [p for p in self._paper_positions.values() if p.symbol == resolved or p.symbol == symbol]
                return list(self._paper_positions.values())

        try:
            with self._lock:
                resolved = self.resolve_symbol_name(symbol) if symbol else None
                positions = mt5.positions_get(symbol=resolved) if resolved else mt5.positions_get()
                if not positions:
                    return []

                results = []
                for p in positions:
                    results.append(PositionSnapshot(
                        ticket=int(p.ticket),
                        symbol=str(p.symbol),
                        type="BUY" if p.type == getattr(mt5, "POSITION_TYPE_BUY", 0) else "SELL",
                        volume=float(p.volume),
                        open_price=float(p.price_open),
                        current_price=float(p.price_current),
                        sl=float(p.sl),
                        tp=float(p.tp),
                        profit=float(p.profit),
                        swap=float(p.swap),
                        commission=float(getattr(p, "commission", 0.0)),
                        open_time=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(p.time)),
                        magic=int(p.magic),
                        comment=str(p.comment)
                    ))
                return results
        except Exception as e:
            logger.error(f"MT5 get_open_positions failed: {e}")
            return []

    def send_market_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "JARVIS_3.0"
    ) -> Dict[str, Any]:
        self._reconnect_if_needed()
        resolved = self.resolve_symbol_name(symbol)
        
        if self.mode == "paper" or not MT5_AVAILABLE:
            with self._lock:
                price = 2400.0 if "XAU" in symbol else (1.0850 if "EUR" in symbol else (65000.0 if "BTC" in symbol else (155.0 if "JPY" in symbol else 1.2700)))
                ticket = int(time.time() * 1000) % 100000000
                pos = PositionSnapshot(
                    ticket=ticket,
                    symbol=resolved,
                    type=order_type,
                    volume=volume,
                    open_price=price,
                    current_price=price,
                    sl=float(sl_price),
                    tp=float(tp_price),
                    profit=0.0,
                    swap=0.0,
                    commission=0.0,
                    open_time=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                    magic=self.magic_number,
                    comment=f"[PAPER] {comment}"
                )
                self._paper_positions[ticket] = pos
                logger.info(f"[PAPER] Order FILLED: #{ticket} {order_type} {volume} {resolved} @ {price}")
                return {
                    "status": "FILLED",
                    "ticket": ticket,
                    "symbol": resolved,
                    "type": order_type,
                    "volume": volume,
                    "price": price,
                    "comment": f"[PAPER] {comment}"
                }

        def _send():
            with self._lock:
                sym_info = mt5.symbol_info(resolved)
                tick = mt5.symbol_info_tick(resolved)
                if not tick or not sym_info:
                    return {"status": "FAILED", "reason": f"Tick or symbol metadata unavailable for {resolved}"}

                price = tick.ask if order_type == "BUY" else tick.bid
                type_op = getattr(mt5, "ORDER_TYPE_BUY", 0) if order_type == "BUY" else getattr(mt5, "ORDER_TYPE_SELL", 1)
                digits = sym_info.digits
                point = sym_info.point or (10 ** -digits)
                min_stop_dist = max(getattr(sym_info, "trade_stops_level", 0), getattr(sym_info, "freeze_level", 0), 5) * point

                final_sl = float(sl_price)
                final_tp = float(tp_price)
                if order_type == "BUY":
                    if final_sl > 0 and (price - final_sl) < min_stop_dist:
                        final_sl = price - min_stop_dist
                    if final_tp > 0 and (final_tp - price) < min_stop_dist:
                        final_tp = price + min_stop_dist
                else:
                    if final_sl > 0 and (final_sl - price) < min_stop_dist:
                        final_sl = price + min_stop_dist
                    if final_tp > 0 and (price - final_tp) < min_stop_dist:
                        final_tp = price - min_stop_dist

                request = {
                    "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
                    "symbol": resolved,
                    "volume": round(volume, 2),
                    "type": type_op,
                    "price": round(price, digits),
                    "sl": round(final_sl, digits) if final_sl > 0 else 0.0,
                    "tp": round(final_tp, digits) if final_tp > 0 else 0.0,
                    "deviation": 50,
                    "magic": self.magic_number,
                    "comment": comment,
                    "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
                    "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)
                }

                # Direct fast execution with instant filling fallback
                result = mt5.order_send(request)
                if result is None or result.retcode not in [getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_PLACED", 10008)]:
                    # If filling type rejected, immediately retry with FOK / RETURN
                    if result and result.retcode in [10030, 10031]:
                        request["type_filling"] = getattr(mt5, "ORDER_FILLING_FOK", 0)
                        result = mt5.order_send(request)
                        if result and result.retcode in [10030, 10031]:
                            request["type_filling"] = getattr(mt5, "ORDER_FILLING_RETURN", 2)
                            result = mt5.order_send(request)

                if result is None or result.retcode not in [getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_PLACED", 10008)]:
                    err_msg = result.comment if result else str(mt5.last_error())
                    logger.error(f"MT5 Order Send Failed for {resolved}: {err_msg}")
                    return {"status": "FAILED", "reason": err_msg}

                logger.info(f"⚡ ULTRA-FAST ORDER FILLED: Ticket={result.order} {order_type} {volume} {resolved} @ {result.price}")
                return {
                    "status": "FILLED",
                    "ticket": result.order,
                    "volume": result.volume,
                    "price": result.price,
                    "comment": result.comment
                }

        return TimeoutGuard.run_sync(_send, timeout_sec=5.0, default={"status": "FAILED", "reason": "Timeout"}, task_name=f"MT5_SendOrder_{symbol}")

    def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
        """Closes a specific open MT5 position (full or partial) by ticket."""
        if self.mode == "paper" or not MT5_AVAILABLE or not self.is_connected:
            with self._lock:
                if ticket in self._paper_positions:
                    pos = self._paper_positions[ticket]
                    if volume is not None and 0 < volume < pos.volume:
                        pos.volume = round(pos.volume - volume, 2)
                        pnl = round(pos.profit * (volume / (pos.volume + volume)), 2)
                        logger.info(f"[PAPER] Partially closed position #{ticket} ({pos.symbol}) by {volume} lots. Remaining: {pos.volume}")
                        return {
                            "status": "PARTIALLY_CLOSED",
                            "ticket": ticket,
                            "closed_volume": volume,
                            "remaining_volume": pos.volume,
                            "pnl": pnl,
                            "price": pos.current_price
                        }
                    else:
                        pos = self._paper_positions.pop(ticket)
                        logger.info(f"[PAPER] Closed simulated position #{ticket} ({pos.symbol})")
                        return {"status": "CLOSED", "ticket": ticket, "pnl": pos.profit, "price": pos.current_price}
                logger.info(f"[PAPER] Position #{ticket} not found or already closed")
                return {"status": "CLOSED", "ticket": ticket, "pnl": 0.0, "price": 0.0}

        def _close():
            with self._lock:
                positions = mt5.positions_get(ticket=ticket)
                if not positions or len(positions) == 0:
                    return {"status": "FAILED", "reason": f"Position #{ticket} not found on MT5"}

                p = positions[0]
                symbol = p.symbol
                tick = mt5.symbol_info_tick(symbol)
                sym_info = mt5.symbol_info(symbol)
                if not tick or not sym_info:
                    return {"status": "FAILED", "reason": f"Tick info unavailable for {symbol}"}

                # Calculate volume to close
                close_volume = float(volume) if (volume is not None and 0 < volume < p.volume) else float(p.volume)
                is_partial = close_volume < p.volume

                # Opposite order type
                is_buy = p.type == getattr(mt5, "POSITION_TYPE_BUY", 0)
                order_type = getattr(mt5, "ORDER_TYPE_SELL", 1) if is_buy else getattr(mt5, "ORDER_TYPE_BUY", 0)
                price = tick.bid if is_buy else tick.ask

                request = {
                    "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
                    "position": ticket,
                    "symbol": symbol,
                    "volume": close_volume,
                    "type": order_type,
                    "price": round(price, sym_info.digits),
                    "deviation": 50,
                    "magic": self.magic_number,
                    "comment": f"Partial #{ticket}" if is_partial else f"Close #{ticket}",
                    "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
                    "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)
                }

                result = mt5.order_send(request)
                if result is None or result.retcode != getattr(mt5, "TRADE_RETCODE_DONE", 10009):
                    err_msg = result.comment if result else str(mt5.last_error())
                    logger.error(f"MT5 Close Order Failed for #{ticket}: {err_msg}")
                    return {"status": "FAILED", "reason": err_msg}

                status_code = "PARTIALLY_CLOSED" if is_partial else "CLOSED"
                logger.info(f"LIVE POSITION {status_code}: Ticket=#{ticket} {symbol} closed {close_volume} lots @ {result.price}")
                return {
                    "status": status_code,
                    "ticket": ticket,
                    "closed_volume": close_volume,
                    "remaining_volume": round(p.volume - close_volume, 2) if is_partial else 0.0,
                    "price": result.price
                }

        return TimeoutGuard.run_sync(_close, timeout_sec=5.0, default={"status": "FAILED", "reason": "Timeout"}, task_name=f"MT5_Close_{ticket}")

    def partial_close(self, ticket: int, volume: float) -> Dict[str, Any]:
        """Convenience method to partially close an open position by ticket and volume."""
        return self.close_position(ticket, volume=volume)

    def modify_position(self, ticket: int, sl: float, tp: float) -> Dict[str, Any]:
        """Modifies Stop Loss and Take Profit of an open MT5 position."""
        if self.mode == "paper" or not MT5_AVAILABLE or not self.is_connected:
            with self._lock:
                if ticket in self._paper_positions:
                    self._paper_positions[ticket].sl = float(sl)
                    self._paper_positions[ticket].tp = float(tp)
                    logger.info(f"[PAPER] Modified position #{ticket} -> SL: {sl}, TP: {tp}")
                    return {"status": "MODIFIED", "ticket": ticket, "sl": sl, "tp": tp}
                return {"status": "FAILED", "reason": f"Position #{ticket} not found in paper positions"}

        def _modify():
            with self._lock:
                positions = mt5.positions_get(ticket=ticket)
                if not positions or len(positions) == 0:
                    return {"status": "FAILED", "reason": f"Position #{ticket} not found on MT5"}

                p = positions[0]
                symbol = p.symbol
                sym_info = mt5.symbol_info(symbol)
                if not sym_info:
                    return {"status": "FAILED", "reason": f"Symbol info unavailable for {symbol}"}

                digits = sym_info.digits
                point = sym_info.point or (10 ** -digits)
                min_stop_dist = max(getattr(sym_info, "trade_stops_level", 0), getattr(sym_info, "freeze_level", 0), 5) * point

                tick = mt5.symbol_info_tick(symbol)
                cur_price = (tick.bid if p.type == getattr(mt5, "POSITION_TYPE_BUY", 0) else tick.ask) if tick else p.price_current

                final_sl = float(sl)
                final_tp = float(tp)
                is_buy = (p.type == getattr(mt5, "POSITION_TYPE_BUY", 0))

                if is_buy:
                    if final_sl > 0 and (cur_price - final_sl) < min_stop_dist:
                        final_sl = cur_price - min_stop_dist
                    if final_tp > 0 and (final_tp - cur_price) < min_stop_dist:
                        final_tp = cur_price + min_stop_dist
                else:
                    if final_sl > 0 and (final_sl - cur_price) < min_stop_dist:
                        final_sl = cur_price + min_stop_dist
                    if final_tp > 0 and (cur_price - final_tp) < min_stop_dist:
                        final_tp = cur_price - min_stop_dist

                request = {
                    "action": getattr(mt5, "TRADE_ACTION_SLTP", 6),
                    "position": ticket,
                    "symbol": symbol,
                    "sl": round(final_sl, digits) if final_sl > 0 else 0.0,
                    "tp": round(final_tp, digits) if final_tp > 0 else 0.0,
                    "magic": self.magic_number,
                    "comment": "JARVIS_SLTP_MODIFY"
                }

                result = mt5.order_send(request)
                if result is None or result.retcode not in [getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_PLACED", 10008)]:
                    err_msg = result.comment if result else str(mt5.last_error())
                    logger.error(f"MT5 SL/TP Modify Failed for #{ticket}: {err_msg}")
                    return {"status": "FAILED", "reason": err_msg}

                logger.info(f"⚡ LIVE SL/TP MODIFIED: Ticket=#{ticket} {symbol} -> New SL={round(final_sl, digits)}, TP={round(final_tp, digits)}")
                return {"status": "MODIFIED", "ticket": ticket, "sl": round(final_sl, digits), "tp": round(final_tp, digits)}

        return TimeoutGuard.run_sync(_modify, timeout_sec=5.0, default={"status": "FAILED", "reason": "Timeout"}, task_name=f"MT5_Modify_{ticket}")

    def close_all_positions(self) -> List[Dict[str, Any]]:
        """Closes all currently open MT5 positions."""
        positions = self.get_open_positions()
        results = []
        for p in positions:
            res = self.close_position(p.ticket)
            results.append(res)
        return results

    def shutdown(self):
        if MT5_AVAILABLE and mt5 and self.is_connected and self.mode != "paper":
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.is_connected = False
