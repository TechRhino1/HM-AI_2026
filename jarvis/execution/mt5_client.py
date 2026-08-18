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
        return self.is_connected

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

        def _fetch_acc():
            with self._lock:
                acc = mt5.account_info()
                if acc is None:
                    return None
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
        res = TimeoutGuard.run_sync(_fetch_acc, timeout_sec=self.timeout_sec, default=default_snap, task_name="MT5_GetAccount")
        return res or default_snap

    def get_open_positions(self, symbol: Optional[str] = None) -> List[PositionSnapshot]:
        if self.mode == "paper" or not self.is_connected or not MT5_AVAILABLE:
            return []

        def _fetch_pos():
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

        return TimeoutGuard.run_sync(_fetch_pos, timeout_sec=self.timeout_sec, default=[], task_name="MT5_GetPositions")

    def send_market_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "JARVIS_3.0"
    ) -> Dict[str, Any]:
        resolved = self.resolve_symbol_name(symbol)
        
        if self.mode == "paper" or not MT5_AVAILABLE:
            price = 2400.0 if "XAU" in symbol else 1.0850
            return {
                "status": "FILLED",
                "ticket": int(time.time() * 1000) % 100000000,
                "symbol": resolved,
                "type": order_type,
                "volume": volume,
                "price": price,
                "comment": f"[PAPER] {comment}"
            }

        def _send():
            with self._lock:
                tick = mt5.symbol_info_tick(resolved)
                sym_info = mt5.symbol_info(resolved)
                if not tick or not sym_info:
                    return {"status": "FAILED", "reason": f"Tick or symbol metadata unavailable for {resolved}"}

                price = tick.ask if order_type == "BUY" else tick.bid
                type_op = getattr(mt5, "ORDER_TYPE_BUY", 0) if order_type == "BUY" else getattr(mt5, "ORDER_TYPE_SELL", 1)
                digits = sym_info.digits

                request = {
                    "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
                    "symbol": resolved,
                    "volume": round(volume, 2),
                    "type": type_op,
                    "price": round(price, digits),
                    "sl": round(sl_price, digits),
                    "tp": round(tp_price, digits),
                    "deviation": 50,
                    "magic": self.magic_number,
                    "comment": comment,
                    "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
                    "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)
                }

                # Pre-flight check
                check_res = mt5.order_check(request)
                if check_res and "filling" in str(check_res.comment).lower():
                    request["type_filling"] = getattr(mt5, "ORDER_FILLING_FOK", 0)

                result = mt5.order_send(request)
                if result is None or result.retcode != getattr(mt5, "TRADE_RETCODE_DONE", 10009):
                    err_msg = result.comment if result else str(mt5.last_error())
                    logger.error(f"MT5 Order Send Failed for {resolved}: {err_msg}")
                    return {"status": "FAILED", "reason": err_msg}

                logger.info(f"LIVE ORDER FILLED: Ticket={result.order} {order_type} {volume} {resolved} @ {result.price}")
                return {
                    "status": "FILLED",
                    "ticket": result.order,
                    "volume": result.volume,
                    "price": result.price,
                    "comment": result.comment
                }

        return TimeoutGuard.run_sync(_send, timeout_sec=5.0, default={"status": "FAILED", "reason": "Timeout"}, task_name=f"MT5_SendOrder_{symbol}")

    def shutdown(self):
        if MT5_AVAILABLE and mt5 and self.is_connected and self.mode != "paper":
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.is_connected = False
