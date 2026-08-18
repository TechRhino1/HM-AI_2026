from typing import Dict, Any, List

class TradeManagerEngine:
    """
    Omniscient Active Position Guardian Engine.
    Continuously monitors all active trades for:
    1. Macro Economic News Proximity & Risk Shifts.
    2. Institutional Order Flow & Cumulative Volume Delta (CVD) Reversals.
    3. Market Structure Transitions (BOS, CHoCH, Swing Lows/Highs).
    4. 4-Stage Adaptive Trailing Stop & Fast Breakeven Protection.
    5. Partial Profit Scaling at TP1 (50% scale-out with risk-free runner).
    """
    def __init__(self, mt5_client: Any, logger: Any = None):
        self.mt5_client = mt5_client
        self.logger = logger

    def manage_active_positions(
        self,
        symbol: str,
        regime_info: Dict[str, Any],
        structure_info: Dict[str, Any],
        volatility_info: Dict[str, Any],
        news_info: Dict[str, Any] = None,
        orderflow_info: Dict[str, Any] = None
    ):
        positions = self.mt5_client.get_open_positions(symbol=symbol)
        if not positions:
            return

        atr = volatility_info.get("atr", 0.0)
        sym_info = self.mt5_client.get_symbol_info(symbol) or {}
        current_bid = sym_info.get("bid", 0.0)
        current_ask = sym_info.get("ask", 0.0)
        regime_bias = regime_info.get("bias", "NEUTRAL")
        regime_type = regime_info.get("regime", "NEUTRAL")
        news_status = news_info.get("news_status", "NEWS_RISK_LOW") if isinstance(news_info, dict) else "NEWS_RISK_LOW"
        delta_imbalance = orderflow_info.get("delta_imbalance", "NEUTRAL") if isinstance(orderflow_info, dict) else "NEUTRAL"
        cvd_trend = orderflow_info.get("cvd_trend", "FLAT") if isinstance(orderflow_info, dict) else "FLAT"

        for pos in positions:
            ticket = pos.get("ticket", 0)
            order_type = "BUY" if pos.get("type") == 0 else "SELL"
            open_price = float(pos.get("price_open", 0.0))
            current_sl = float(pos.get("sl", 0.0))
            current_tp = float(pos.get("tp", 0.0))
            volume = float(pos.get("volume", 0.0))
            digits = int(sym_info.get("digits", 2 if ("XAU" in symbol or "GOLD" in symbol or "BTC" in symbol) else 5))

            effective_atr = atr if atr > 0 else (open_price * 0.003)
            spread_buffer = effective_atr * 0.15

            # =========================================================================
            # 1. EMERGENCY EXIT & MACRO SHIELD: Opposing Regime or High-Impact News
            # =========================================================================
            if (order_type == "BUY" and regime_bias == "BEARISH" and "STRONG_TREND" in regime_type) or \
               (order_type == "SELL" and regime_bias == "BULLISH" and "STRONG_TREND" in regime_type):
                if self.logger:
                    self.logger.warning(f"EMERGENCY EXIT [Ticket #{ticket}]: Strong Regime Shift against {symbol} {order_type}. Closing position.")
                self.mt5_client.close_position(ticket, symbol)
                continue

            # =========================================================================
            # 2. LONG (BUY) POSITION MONITORING & ADAPTIVE MANAGEMENT
            # =========================================================================
            if order_type == "BUY":
                profit_dist = current_bid - open_price
                current_r = profit_dist / (effective_atr + 1e-9)

                # A. News Shield: If High-Impact News is imminent and position is in profit, lock Breakeven
                if news_status == "NEWS_RISK_HIGH" and profit_dist >= (effective_atr * 0.5):
                    news_sl = round(open_price + spread_buffer, digits)
                    if news_sl > current_sl:
                        self.mt5_client.modify_position(ticket, symbol, news_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"NEWS SHIELD ACTIVE [Ticket #{ticket}]: Locked Breakeven prior to High-Impact News @ ${news_sl:.2f}")

                # B. Volume Delta Reversal Guard: Heavy institutional selling volume detected
                if delta_imbalance == "BEARISH_ORDER_FLOW" and cvd_trend == "BEARISH" and profit_dist >= (effective_atr * 0.8):
                    vol_sl = round(current_bid - (effective_atr * 0.5), digits)
                    if vol_sl > current_sl and vol_sl < current_bid:
                        self.mt5_client.modify_position(ticket, symbol, vol_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"VOLUME DELTA GUARD [Ticket #{ticket}]: Bearish Delta shift. Tightened SL to lock profit @ ${vol_sl:.2f}")

                # C. Partial Profit Scale-Out (50% close at TP1 >= 1.8 ATR)
                tp1_target_dist = effective_atr * 1.8
                if profit_dist >= tp1_target_dist and volume >= 0.02 and not pos.get("partially_closed", False):
                    close_vol = round(volume * 0.5, 2)
                    self.mt5_client.close_position(ticket, symbol, volume=close_vol)
                    if self.logger:
                        self.logger.info(f"PARTIAL PROFIT SCALED OUT [Ticket #{ticket}]: Closed {close_vol} Lots @ TP1 Target (${current_bid:.2f})")
                    new_sl = round(open_price + spread_buffer, digits)
                    self.mt5_client.modify_position(ticket, symbol, new_sl, current_tp)

                # D. Master Breakeven: Trigger at >= 1.0 ATR profit
                if profit_dist >= (effective_atr * 1.0) and current_sl < (open_price + spread_buffer):
                    new_sl = round(open_price + spread_buffer, digits)
                    self.mt5_client.modify_position(ticket, symbol, new_sl, current_tp)
                    if self.logger:
                        self.logger.info(f"AI BREAKEVEN PROTECTION [Ticket #{ticket}]: Moved SL to Entry+Buffer @ ${new_sl:.2f} (Profit: +{current_r:.1f}R)")

                # E. Master Trailing Stop (Follows Swing Low or ATR trail at >= 1.5 ATR profit)
                if profit_dist >= (effective_atr * 1.5):
                    step_trailing_sl = round(current_bid - (effective_atr * 1.0), digits)
                    recent_sl = structure_info.get("recent_swing_low", 0.0)
                    struct_sl = round(recent_sl - spread_buffer, digits) if recent_sl > 0 else 0.0

                    candidate_sl = max(step_trailing_sl, struct_sl)
                    if candidate_sl > current_sl and candidate_sl < current_bid:
                        self.mt5_client.modify_position(ticket, symbol, candidate_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"AI PROFIT LOCK TRAIL [Ticket #{ticket}]: Raised SL to lock profit @ ${candidate_sl:.2f}")

                # F. Dynamic Take Profit Expansion in Strong Trends
                if "STRONG_TREND" in regime_type:
                    extended_tp = round(open_price + (abs(open_price - current_sl) * 3.5), digits)
                    if extended_tp > current_tp and current_tp > 0:
                        self.mt5_client.modify_position(ticket, symbol, current_sl, extended_tp)

            # =========================================================================
            # 3. SHORT (SELL) POSITION MONITORING & ADAPTIVE MANAGEMENT
            # =========================================================================
            elif order_type == "SELL":
                profit_dist = open_price - current_ask
                current_r = profit_dist / (effective_atr + 1e-9)

                # A. News Shield: If High-Impact News is imminent and position is in profit, lock Breakeven
                if news_status == "NEWS_RISK_HIGH" and profit_dist >= (effective_atr * 0.5):
                    news_sl = round(open_price - spread_buffer, digits)
                    if current_sl == 0 or news_sl < current_sl:
                        self.mt5_client.modify_position(ticket, symbol, news_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"NEWS SHIELD ACTIVE [Ticket #{ticket}]: Locked Breakeven prior to High-Impact News @ ${news_sl:.2f}")

                # B. Volume Delta Reversal Guard: Heavy institutional buying volume detected
                if delta_imbalance == "BULLISH_ORDER_FLOW" and cvd_trend == "BULLISH" and profit_dist >= (effective_atr * 0.8):
                    vol_sl = round(current_ask + (effective_atr * 0.5), digits)
                    if (current_sl == 0 or vol_sl < current_sl) and vol_sl > current_ask:
                        self.mt5_client.modify_position(ticket, symbol, vol_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"VOLUME DELTA GUARD [Ticket #{ticket}]: Bullish Delta shift. Tightened SL to lock profit @ ${vol_sl:.2f}")

                # C. Partial Profit Scale-Out (50% close at TP1 >= 1.8 ATR)
                tp1_target_dist = effective_atr * 1.8
                if profit_dist >= tp1_target_dist and volume >= 0.02 and not pos.get("partially_closed", False):
                    close_vol = round(volume * 0.5, 2)
                    self.mt5_client.close_position(ticket, symbol, volume=close_vol)
                    if self.logger:
                        self.logger.info(f"PARTIAL PROFIT SCALED OUT [Ticket #{ticket}]: Closed {close_vol} Lots @ TP1 Target (${current_ask:.2f})")
                    new_sl = round(open_price - spread_buffer, digits)
                    self.mt5_client.modify_position(ticket, symbol, new_sl, current_tp)

                # D. Master Breakeven: Trigger at >= 1.0 ATR profit
                if profit_dist >= (effective_atr * 1.0) and (current_sl > (open_price - spread_buffer) or current_sl == 0):
                    new_sl = round(open_price - spread_buffer, digits)
                    self.mt5_client.modify_position(ticket, symbol, new_sl, current_tp)
                    if self.logger:
                        self.logger.info(f"AI BREAKEVEN PROTECTION [Ticket #{ticket}]: Moved SL to Entry+Buffer @ ${new_sl:.2f} (Profit: +{current_r:.1f}R)")

                # E. Master Trailing Stop (Follows Swing High or ATR trail at >= 1.5 ATR profit)
                if profit_dist >= (effective_atr * 1.5):
                    step_trailing_sl = round(current_ask + (effective_atr * 1.0), digits)
                    recent_sh = structure_info.get("recent_swing_high", 0.0)
                    struct_sl = round(recent_sh + spread_buffer, digits) if recent_sh > 0 else 999999.0

                    candidate_sl = min(step_trailing_sl, struct_sl)
                    if (current_sl == 0 or candidate_sl < current_sl) and candidate_sl > current_ask:
                        self.mt5_client.modify_position(ticket, symbol, candidate_sl, current_tp)
                        if self.logger:
                            self.logger.info(f"AI PROFIT LOCK TRAIL [Ticket #{ticket}]: Lowered SL to lock profit @ ${candidate_sl:.2f}")

                # F. Dynamic Take Profit Expansion in Strong Trends
                if "STRONG_TREND" in regime_type:
                    extended_tp = round(open_price - (abs(current_sl - open_price) * 3.5), digits)
                    if extended_tp < current_tp and current_tp > 0:
                        self.mt5_client.modify_position(ticket, symbol, current_sl, extended_tp)
