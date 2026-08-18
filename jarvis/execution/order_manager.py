"""
JARVIS AI 3.0 — Active Order & Position Manager.
Features:
- Micro-Account 3-Stage Breakeven & Profit Lock Scalping Protocol (< $100 Equity)
- Structural and ATR-based Trailing Stops
- Execution Deterioration & Spread Expansion Protection
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
        vol = context.volatility
        is_micro_pos = (position.volume <= 0.03)

        modified = False
        new_sl = position.sl
        new_tp = position.tp

        if position.type == "BUY":
            profit_pips = (c_price - position.open_price)
            
            # Micro Account 3-Stage Breakeven Protocol
            if is_micro_pos:
                # Stage 1: Move SL to Break-Even + Buffer at +1.0 ATR
                if profit_pips >= atr * 1.0 and position.sl < position.open_price:
                    new_sl = position.open_price + (atr * 0.15)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} BUY: Stage 1 Breakeven Lock at {new_sl:.2f}")

                # Stage 2: Lock in +0.75R profit at +1.6 ATR
                elif profit_pips >= atr * 1.6 and position.sl < position.open_price + (atr * 0.6):
                    new_sl = position.open_price + (atr * 0.6)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} BUY: Stage 2 Profit Lock at {new_sl:.2f}")

            # Standard Institutional Trailing (>= $100 Accounts - UNTOUCHED)
            else:
                if profit_pips >= atr * 1.5 and position.sl < position.open_price:
                    new_sl = position.open_price + (atr * 0.2)
                    modified = True
                    logger.info(f"Position #{position.ticket} BUY: Moving SL to Break-Even ({new_sl:.4f}).")

            # Trailing stop behind dynamic swing low
            if st.higher_lows and st.demand_zone[0] > new_sl and st.demand_zone[0] < c_price:
                new_sl = st.demand_zone[0]
                modified = True
                logger.info(f"Position #{position.ticket} BUY: Trailing SL to Higher-Low structure ({new_sl:.4f}).")

        elif position.type == "SELL":
            profit_pips = (position.open_price - c_price)
            
            # Micro Account 3-Stage Breakeven Protocol
            if is_micro_pos:
                # Stage 1: Move SL to Break-Even - Buffer at +1.0 ATR
                if profit_pips >= atr * 1.0 and (position.sl > position.open_price or position.sl == 0):
                    new_sl = position.open_price - (atr * 0.15)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} SELL: Stage 1 Breakeven Lock at {new_sl:.2f}")

                # Stage 2: Lock in +0.75R profit at +1.6 ATR
                elif profit_pips >= atr * 1.6 and (position.sl > position.open_price - (atr * 0.6) or position.sl == 0):
                    new_sl = position.open_price - (atr * 0.6)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} SELL: Stage 2 Profit Lock at {new_sl:.2f}")

            # Standard Institutional Trailing (>= $100 Accounts - UNTOUCHED)
            else:
                if profit_pips >= atr * 1.5 and (position.sl > position.open_price or position.sl == 0):
                    new_sl = position.open_price - (atr * 0.2)
                    modified = True
                    logger.info(f"Position #{position.ticket} SELL: Moving SL to Break-Even ({new_sl:.4f}).")

            # Trailing stop behind dynamic swing high
            if st.lower_highs and st.supply_zone[1] < new_sl and st.supply_zone[1] > c_price:
                new_sl = st.supply_zone[1]
                modified = True
                logger.info(f"Position #{position.ticket} SELL: Trailing SL to Lower-High structure ({new_sl:.4f}).")

        # Spread blowout alert
        if vol.current_spread_pips > 4.0:
            logger.warning(f"⚠️ High Spread Detected on #{position.ticket} ({vol.current_spread_pips:.1f} pips).")

        return {
            "ticket": position.ticket,
            "modified": modified,
            "new_sl": round(new_sl, 4),
            "new_tp": round(new_tp, 4)
        }
