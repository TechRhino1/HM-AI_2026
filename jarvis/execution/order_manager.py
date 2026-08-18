"""
JARVIS AI 3.0 — Active Order & Position Manager.
Manages trailing stop adjustments (structure and ATR-based), break-even stops, and partial profit locks.
"""
import logging
from typing import Dict, List, Any
from jarvis.data.schemas import PositionSnapshot, MarketContext
from jarvis.execution.mt5_client import MT5Client

logger = logging.getLogger("JARVIS_OrderManager")

class OrderManager:
    def __init__(self, mt5_client: MT5Client):
        self.mt5_client = mt5_client

    def manage_position(self, position: PositionSnapshot, context: MarketContext) -> Dict[str, Any]:
        """Dynamically manages trailing stop loss and profit protection for an open position."""
        c_price = context.current_price
        atr = context.volatility.atr if context.volatility.atr > 0 else (c_price * 0.005)
        st = context.structure

        modified = False
        new_sl = position.sl
        new_tp = position.tp

        if position.type == "BUY":
            profit_pips = (c_price - position.open_price)
            # Break-even trigger: If in profit by 1.5 ATR, move SL to open_price + 0.2 ATR
            if profit_pips >= atr * 1.5 and position.sl < position.open_price:
                new_sl = position.open_price + (atr * 0.2)
                modified = True
                logger.info(f"Position #{position.ticket} BUY: Moving SL to Break-Even + Buffer ({new_sl:.4f}).")

            # Trailing stop behind swing low
            elif st.higher_lows and st.demand_zone[0] > position.sl and st.demand_zone[0] < c_price:
                new_sl = st.demand_zone[0]
                modified = True
                logger.info(f"Position #{position.ticket} BUY: Trailing SL to new Higher-Low structure ({new_sl:.4f}).")

        elif position.type == "SELL":
            profit_pips = (position.open_price - c_price)
            # Break-even trigger
            if profit_pips >= atr * 1.5 and (position.sl > position.open_price or position.sl == 0):
                new_sl = position.open_price - (atr * 0.2)
                modified = True
                logger.info(f"Position #{position.ticket} SELL: Moving SL to Break-Even - Buffer ({new_sl:.4f}).")

            # Trailing stop behind swing high
            elif st.lower_highs and st.supply_zone[1] < position.sl and st.supply_zone[1] > c_price:
                new_sl = st.supply_zone[1]
                modified = True
                logger.info(f"Position #{position.ticket} SELL: Trailing SL to new Lower-High structure ({new_sl:.4f}).")

        return {
            "ticket": position.ticket,
            "modified": modified,
            "new_sl": round(new_sl, 4),
            "new_tp": round(new_tp, 4)
        }
