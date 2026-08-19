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
    MICRO_VOLUME_THRESHOLD = 0.03
    STAGE1_ATR_TRIGGER = 1.0
    STAGE1_BE_BUFFER = 0.15
    STAGE2_ATR_TRIGGER = 1.6
    STAGE2_PROFIT_LOCK = 0.6
    STAGE3_ATR_TRIGGER = 2.0
    STAGE3_PROFIT_LOCK_PCT = 0.60
    STD_ATR_TRIGGER = 1.5
    STD_BE_BUFFER = 0.2
    SR_ATR_BUFFER = 0.2
    SPREAD_ALERT_THRESHOLD = 4.0

    def __init__(self, mt5_client: MT5Client):
        self.mt5_client = mt5_client

    def manage_position(self, position: PositionSnapshot, context: MarketContext) -> Dict[str, Any]:
        """Dynamically manages trailing stop loss and profit protection for an open position."""
        c_price = context.current_price
        atr = context.volatility.atr if context.volatility.atr > 0 else (c_price * 0.005)
        st = context.structure
        vol = context.volatility
        is_micro_pos = (position.volume <= self.MICRO_VOLUME_THRESHOLD)

        # ATR-adaptive trailing step
        atr_multiplier = 1.3 if vol.state in ["EXPANSION", "EXTREME"] else 1.0

        modified = False
        new_sl = position.sl
        new_tp = position.tp

        if position.type == "BUY":
            profit_pips = (c_price - position.open_price)
            
            # Momentum-loss exit
            if getattr(context, "strategy", "") == "TREND_FOLLOWING" and profit_pips > 0:
                trend_score = getattr(context, "trend_score", 0)
                if trend_score < 0:
                    lock_80_sl = position.open_price + (profit_pips * 0.80)
                    if lock_80_sl > new_sl:
                        new_sl = lock_80_sl
                        modified = True
                        logger.info(f"⚡ Momentum Loss Exit! Position #{position.ticket} BUY: 80% Profit Lock at {new_sl:.2f}")

            # Micro Account 3-Stage Breakeven & Profit Lock Protocol
            if is_micro_pos:
                # Stage 3: Lock in 60% of Floating Profit at >= 2.0 ATR / +15 pts
                if profit_pips >= (atr * self.STAGE3_ATR_TRIGGER * atr_multiplier):
                    lock_60_sl = position.open_price + (profit_pips * self.STAGE3_PROFIT_LOCK_PCT)
                    if lock_60_sl > new_sl:
                        new_sl = lock_60_sl
                        modified = True
                        logger.info(f"⚡ [MICRO] Position #{position.ticket} BUY: Stage 3 (60% Profit Lock) at {new_sl:.2f}")

                # Stage 2: Lock in +0.75R profit at +1.6 ATR
                elif profit_pips >= (atr * self.STAGE2_ATR_TRIGGER * atr_multiplier) and position.sl < position.open_price + (atr * self.STAGE2_PROFIT_LOCK):
                    new_sl = position.open_price + (atr * self.STAGE2_PROFIT_LOCK)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} BUY: Stage 2 Profit Lock at {new_sl:.2f}")

                # Stage 1: Move SL to Break-Even + Buffer at +1.0 ATR
                elif profit_pips >= (atr * self.STAGE1_ATR_TRIGGER * atr_multiplier) and position.sl < position.open_price:
                    new_sl = position.open_price + (atr * self.STAGE1_BE_BUFFER)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} BUY: Stage 1 Breakeven Lock at {new_sl:.2f}")

            # Standard Institutional Trailing (>= $100 Accounts - UNTOUCHED)
            else:
                if profit_pips >= (atr * self.STD_ATR_TRIGGER * atr_multiplier) and position.sl < position.open_price:
                    new_sl = position.open_price + (atr * self.STD_BE_BUFFER)
                    modified = True
                    logger.info(f"Position #{position.ticket} BUY: Moving SL to Break-Even ({new_sl:.4f}).")

            # Structural Trailing: Ratchet SL behind newly formed Higher-Low Support Floor
            if st.higher_lows and st.demand_zone[0] > 0:
                struct_sl = st.demand_zone[0] - (atr * self.SR_ATR_BUFFER)
                if struct_sl > new_sl and struct_sl < c_price:
                    new_sl = struct_sl
                    modified = True
                    logger.info(f"🏛️ Position #{position.ticket} BUY: Ratcheted SL behind Support Floor at {new_sl:.2f}")

        elif position.type == "SELL":
            profit_pips = (position.open_price - c_price)
            
            # Momentum-loss exit
            if getattr(context, "strategy", "") == "TREND_FOLLOWING" and profit_pips > 0:
                trend_score = getattr(context, "trend_score", 0)
                if trend_score > 0:
                    lock_80_sl = position.open_price - (profit_pips * 0.80)
                    if lock_80_sl < new_sl or new_sl == 0:
                        new_sl = lock_80_sl
                        modified = True
                        logger.info(f"⚡ Momentum Loss Exit! Position #{position.ticket} SELL: 80% Profit Lock at {new_sl:.2f}")

            # Micro Account 3-Stage Breakeven & Profit Lock Protocol
            if is_micro_pos:
                # Stage 3: Lock in 60% of Floating Profit at >= 2.0 ATR / +15 pts
                if profit_pips >= (atr * self.STAGE3_ATR_TRIGGER * atr_multiplier):
                    lock_60_sl = position.open_price - (profit_pips * self.STAGE3_PROFIT_LOCK_PCT)
                    if lock_60_sl < new_sl or new_sl == 0:
                        new_sl = lock_60_sl
                        modified = True
                        logger.info(f"⚡ [MICRO] Position #{position.ticket} SELL: Stage 3 (60% Profit Lock) at {new_sl:.2f}")

                # Stage 2: Lock in +0.75R profit at +1.6 ATR
                elif profit_pips >= (atr * self.STAGE2_ATR_TRIGGER * atr_multiplier) and (position.sl > position.open_price - (atr * self.STAGE2_PROFIT_LOCK) or position.sl == 0):
                    new_sl = position.open_price - (atr * self.STAGE2_PROFIT_LOCK)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} SELL: Stage 2 Profit Lock at {new_sl:.2f}")

                # Stage 1: Move SL to Break-Even - Buffer at +1.0 ATR
                elif profit_pips >= (atr * self.STAGE1_ATR_TRIGGER * atr_multiplier) and (position.sl > position.open_price or position.sl == 0):
                    new_sl = position.open_price - (atr * self.STAGE1_BE_BUFFER)
                    modified = True
                    logger.info(f"⚡ [MICRO] Position #{position.ticket} SELL: Stage 1 Breakeven Lock at {new_sl:.2f}")

            # Standard Institutional Trailing (>= $100 Accounts - UNTOUCHED)
            else:
                if profit_pips >= (atr * self.STD_ATR_TRIGGER * atr_multiplier) and (position.sl > position.open_price or position.sl == 0):
                    new_sl = position.open_price - (atr * self.STD_BE_BUFFER)
                    modified = True
                    logger.info(f"Position #{position.ticket} SELL: Moving SL to Break-Even ({new_sl:.4f}).")

            # Structural Trailing: Ratchet SL behind newly formed Lower-High Resistance Ceiling
            if st.lower_highs and st.supply_zone[1] > 0:
                struct_sl = st.supply_zone[1] + (atr * self.SR_ATR_BUFFER)
                if (struct_sl < new_sl or new_sl == 0) and struct_sl > c_price:
                    new_sl = struct_sl
                    modified = True
                    logger.info(f"🏛️ Position #{position.ticket} SELL: Ratcheted SL behind Resistance Ceiling at {new_sl:.2f}")

        # Spread blowout alert
        if vol.current_spread_pips > self.SPREAD_ALERT_THRESHOLD:
            logger.warning(f"⚠️ High Spread Detected on #{position.ticket} ({vol.current_spread_pips:.1f} pips).")

        return {
            "ticket": position.ticket,
            "modified": modified,
            "new_sl": round(new_sl, 4),
            "new_tp": round(new_tp, 4)
        }
