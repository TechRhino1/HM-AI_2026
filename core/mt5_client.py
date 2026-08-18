import time
import threading
from typing import Dict, Any, List, Optional
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except Exception:
    mt5 = None
    MT5_AVAILABLE = False

class MT5ExecutionEngine:
    def __init__(self, magic_number: int = 888999, mode: str = "dry_run", logger: Any = None):
        self.magic_number = magic_number
        self.mode = mode.lower()
        self.logger = logger
        self.is_connected = False
        self.symbol_alias_cache: Dict[str, str] = {}
        self._lock = threading.Lock()
        self.init_connection()

    def init_connection(self) -> bool:
        if self.mode == "dry_run":
            if self.logger:
                self.logger.info("MT5 Engine operating in DRY_RUN / SIMULATION mode.")
            self.is_connected = True
            return True

        if not MT5_AVAILABLE or mt5 is None or not mt5.initialize():
            error_code = mt5.last_error() if mt5 else "MT5_MODULE_NOT_FOUND"
            if self.logger:
                self.logger.error(f"MT5 initialization failed with error: {error_code}")
            self.is_connected = False
            return False
        
        self.is_connected = True
        account = mt5.account_info()
        if account and self.logger:
            self.logger.info(f"Connected to MT5 Server: {account.server} | Account: {account.login} | Balance: ${account.balance:.2f}")
        return True

    def resolve_symbol_name(self, symbol: str) -> str:
        """Automatically resolves broker-specific symbol suffixes ensuring trade-enabled symbols are selected."""
        if symbol in self.symbol_alias_cache:
            return self.symbol_alias_cache[symbol]

        if self.mode == "dry_run" or not self.is_connected or not MT5_AVAILABLE:
            return symbol

        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return symbol

        base_u = symbol.upper()
        candidates = []
        for s in all_symbols:
            s_name_u = s.name.upper()
            if base_u in ["XAUUSD", "GOLD"]:
                if any(k in s_name_u for k in ["GOLD.I#", "GOLD#", "GOLD.M", "XAUUSD.I#", "XAUUSD#", "GOLD", "XAUUSD"]):
                    candidates.append(s)
            elif base_u in ["OIL", "CRUDE", "USOIL"]:
                if any(k in s_name_u for k in ["OILCASH#", "USOIL", "OIL#", "CRUDE"]):
                    candidates.append(s)
            elif base_u == "US30":
                if any(k in s_name_u for k in ["US30CASH#", "US30#", "US30"]):
                    candidates.append(s)
            elif base_u == "NAS100":
                if any(k in s_name_u for k in ["NAS100CASH#", "USTECH#", "NAS100#", "NAS100"]):
                    candidates.append(s)
            elif base_u in s_name_u:
                candidates.append(s)

        if candidates:
            # Sort: FULL trade_mode first, then visible, then shortest name or with '#' suffix
            candidates.sort(key=lambda s: (
                0 if s.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL else 1,
                0 if "#" in s.name else 1,
                0 if s.visible else 1,
                len(s.name)
            ))
            best = candidates[0]
            resolved = best.name
            mt5.symbol_select(resolved, True)
            self.symbol_alias_cache[symbol] = resolved
            return resolved

        return symbol

    def get_account_info(self) -> Dict[str, Any]:
        if self.mode == "dry_run" or not self.is_connected:
            return {
                "login": 345841337,
                "server": "XMGlobal-MT5 10",
                "balance": 996.07,
                "equity": 996.07,
                "margin": 0.0,
                "free_margin": 996.07,
                "leverage": 100,
                "currency": "USD",
                "trade_allowed": True
            }

        with self._lock:
            acc = mt5.account_info()
            if acc is None:
                return {
                    "login": 345841337,
                    "server": "XMGlobal-MT5 10",
                    "balance": 996.07,
                    "equity": 996.07,
                    "margin": 0.0,
                    "free_margin": 996.07,
                    "leverage": 100,
                    "currency": "USD",
                    "trade_allowed": True
                }
            return acc._asdict()

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        resolved_symbol = self.resolve_symbol_name(symbol)

        if self.mode == "dry_run" or not self.is_connected:
            return {
                "symbol": resolved_symbol,
                "digits": 2 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol or "BTC" in resolved_symbol) else 5,
                "point": 0.01 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol or "BTC" in resolved_symbol) else 0.00001,
                "bid": 62800.0 if "BTC" in resolved_symbol else (2000.0 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol) else 1.0850),
                "ask": 62815.0 if "BTC" in resolved_symbol else (2000.2 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol) else 1.0852),
                "spread_pips": 1500.0 if "BTC" in resolved_symbol else (20.0 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol) else 2.0),
                "trade_contract_size": 1 if "BTC" in resolved_symbol else (100 if ("XAU" in resolved_symbol or "GOLD" in resolved_symbol) else 100000),
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
                "trade_tick_size": 0.01,
                "trade_tick_value": 1.0
            }

        sym_info = mt5.symbol_info(resolved_symbol)
        if sym_info is None:
            if not mt5.symbol_select(resolved_symbol, True):
                if self.logger:
                    self.logger.error(f"Symbol {resolved_symbol} not found or cannot be selected.")
                return None
            sym_info = mt5.symbol_info(resolved_symbol)

        point = sym_info.point
        digits = sym_info.digits
        spread_pips = (sym_info.ask - sym_info.bid) / (10 ** -digits * 10 if digits in [3, 5] else (10 ** -digits if 10 ** -digits > 0 else 1.0))

        return {
            "symbol": sym_info.name,
            "digits": digits,
            "point": point,
            "bid": sym_info.bid,
            "ask": sym_info.ask,
            "spread_pips": round(spread_pips, 2),
            "trade_contract_size": sym_info.trade_contract_size,
            "volume_min": sym_info.volume_min,
            "volume_max": sym_info.volume_max,
            "volume_step": sym_info.volume_step,
            "trade_tick_size": sym_info.trade_tick_size,
            "trade_tick_value": sym_info.trade_tick_value
        }

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mode == "dry_run" or not self.is_connected:
            return []

        resolved_symbol = self.resolve_symbol_name(symbol) if symbol else None
        if resolved_symbol:
            positions = mt5.positions_get(symbol=resolved_symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        res = []
        for pos in positions:
            res.append(pos._asdict())
        return res

    def send_market_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "AI_Trade"
    ) -> Dict[str, Any]:
        resolved_symbol = self.resolve_symbol_name(symbol)
        if self.mode == "dry_run":
            sym = self.get_symbol_info(resolved_symbol)
            price = sym["ask"] if order_type == "BUY" else sym["bid"]
            if self.logger:
                self.logger.info(f"DRY RUN ORDER SUCCESS: {order_type} {volume} {resolved_symbol} @ {price} SL: {sl_price} TP: {tp_price}")
            return {
                "status": "SUCCESS",
                "ticket": 999999,
                "volume": volume,
                "price": price,
                "comment": f"[DRY_RUN] {comment}"
            }

        sym_info = self.get_symbol_info(resolved_symbol)
        if not sym_info:
            return {"status": "FAILED", "reason": f"Symbol {resolved_symbol} unavailable"}

        digits = sym_info["digits"]
        point = sym_info["point"]
        tick = mt5.symbol_info_tick(resolved_symbol)
        if not tick:
            return {"status": "FAILED", "reason": f"Tick info unavailable for {resolved_symbol}"}

        price = tick.ask if order_type == "BUY" else tick.bid
        type_op = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL

        # Fetch MT5 Symbol Stops Level
        mt5_sym = mt5.symbol_info(resolved_symbol)
        stops_level_pts = mt5_sym.trade_stops_level if mt5_sym else 10
        min_dist = max(stops_level_pts * point, point * 100)

        # Validate SL & TP against current live price
        final_sl = sl_price
        final_tp = tp_price

        # Check if passed SL/TP are completely out-of-range or inverted for current live price
        if order_type == "BUY":
            if final_sl <= 0 or final_sl >= price or abs(price - final_sl) > (price * 0.15):
                final_sl = price - (price * 0.015)  # 1.5% SL
            if final_tp <= price or abs(final_tp - price) > (price * 0.30):
                final_tp = price + (price * 0.030)  # 3.0% TP
            
            # Enforce minimum stops level distance
            if final_sl >= price - min_dist:
                final_sl = price - min_dist
            if final_tp <= price + min_dist:
                final_tp = price + min_dist

        elif order_type == "SELL":
            if final_sl <= 0 or final_sl <= price or abs(final_sl - price) > (price * 0.15):
                final_sl = price + (price * 0.015)  # 1.5% SL
            if final_tp >= price or abs(price - final_tp) > (price * 0.30):
                final_tp = price - (price * 0.030)  # 3.0% TP

            # Enforce minimum stops level distance
            if final_sl <= price + min_dist:
                final_sl = price + min_dist
            if final_tp >= price - min_dist:
                final_tp = price - min_dist

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": resolved_symbol,
            "volume": round(volume, 2),
            "type": type_op,
            "price": round(price, digits),
            "sl": round(final_sl, digits),
            "tp": round(final_tp, digits),
            "deviation": 50,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        # Pre-validate order parameters & margin using official MT5 order_check()
        check_result = mt5.order_check(request)
        if check_result is None or check_result.retcode != 0:
            err_reason = check_result.comment if check_result else str(mt5.last_error())
            if self.logger:
                self.logger.error(f"MT5 Order Check FAILED for {resolved_symbol}: {err_reason}")
            # If order_check warns about filling, fallback to FOK
            if check_result and "filling" in check_result.comment.lower():
                request["type_filling"] = mt5.ORDER_FILLING_FOK

        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            if self.logger:
                self.logger.error(f"Order send failed for {resolved_symbol}, last_error: {err}")
            return {"status": "FAILED", "reason": str(err)}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            if self.logger:
                self.logger.error(f"Order execution rejected for {resolved_symbol}. Retcode: {result.retcode} ({result.comment})")
            return {"status": "FAILED", "reason": result.comment, "retcode": result.retcode}

        if self.logger:
            self.logger.info(f"ORDER EXECUTED: Ticket={result.order} {order_type} {volume} {resolved_symbol} @ {result.price}")
        return {
            "status": "SUCCESS",
            "ticket": result.order,
            "volume": result.volume,
            "price": result.price,
            "comment": result.comment
        }

    def modify_position(self, ticket: int, symbol: str, new_sl: float, new_tp: float) -> bool:
        resolved_symbol = self.resolve_symbol_name(symbol)
        if self.mode == "dry_run":
            if self.logger:
                self.logger.info(f"DRY RUN MODIFY POSITION #{ticket}: SL={new_sl} TP={new_tp}")
            return True

        sym_info = self.get_symbol_info(resolved_symbol)
        digits = sym_info["digits"] if sym_info else 5

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": resolved_symbol,
            "sl": round(new_sl, digits),
            "tp": round(new_tp, digits)
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            if self.logger:
                self.logger.info(f"POSITION #{ticket} MODIFIED: New SL={new_sl} New TP={new_tp}")
            return True

        if self.logger:
            self.logger.error(f"Failed to modify position #{ticket}: {result.comment if result else 'Unknown'}")
        return False

    def close_position(self, ticket: int, symbol: str, volume: float = 0.0) -> bool:
        resolved_symbol = self.resolve_symbol_name(symbol)
        if self.mode == "dry_run":
            if self.logger:
                self.logger.info(f"DRY RUN CLOSE POSITION #{ticket} ({resolved_symbol}) Volume={volume}")
            return True

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(resolved_symbol)
        if not tick:
            return False

        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        
        sym_info = self.get_symbol_info(resolved_symbol)
        min_vol = sym_info.get("volume_min", 0.01) if sym_info else 0.01
        step_vol = sym_info.get("volume_step", 0.01) if sym_info else 0.01

        close_vol = volume if volume > 0.0 else pos.volume
        close_vol = round(close_vol / step_vol) * step_vol
        close_vol = max(min_vol, min(pos.volume, round(close_vol, 2)))

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": resolved_symbol,
            "volume": close_vol,
            "type": close_type,
            "price": price,
            "deviation": 50,
            "magic": self.magic_number,
            "comment": f"AI_Close_{close_vol}L",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            if self.logger:
                self.logger.info(f"POSITION #{ticket} PARTIALLY/FULLY CLOSED: Volume={close_vol} Lots @ {price}")
            return True
        return False

    def partial_close_position(self, ticket: int, symbol: str, pct: float = 0.50) -> bool:
        if self.mode == "dry_run":
            if self.logger:
                self.logger.info(f"DRY RUN PARTIAL CLOSE #{ticket} ({symbol}) Pct={pct*100}%")
            return True
        positions = self.get_open_positions(symbol=symbol)
        target_pos = None
        for p in positions:
            if p.get("ticket") == ticket:
                target_pos = p
                break

        if not target_pos:
            return False

        total_vol = target_pos.get("volume", 0.0)
        close_vol = total_vol * pct
        return self.close_position(ticket, symbol, volume=close_vol)

    def close_position_partial(self, ticket: int, symbol: str, volume: float) -> bool:
        return self.close_position(ticket, symbol, volume=volume)

    def move_to_breakeven(self, ticket: int, symbol: str) -> bool:
        positions = self.get_open_positions(symbol=symbol)
        target_pos = None
        for p in positions:
            if p.get("ticket") == ticket:
                target_pos = p
                break

        if not target_pos:
            return False

        open_price = target_pos.get("price_open", 0.0)
        current_tp = target_pos.get("tp", 0.0)
        order_type = target_pos.get("type", 0)

        sym_info = self.get_symbol_info(symbol)
        point = sym_info.get("point", 0.01) if sym_info else 0.01
        offset = point * 10.0

        new_sl = open_price + offset if order_type == 0 else open_price - offset
        return self.modify_position(ticket, symbol, new_sl, current_tp)

    def shutdown(self):
        if self.is_connected and self.mode != "dry_run":
            mt5.shutdown()
            self.is_connected = False
