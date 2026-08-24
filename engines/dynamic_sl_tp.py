from typing import Dict, Any, List, Optional
from engines.ml_optimizer_engine import MachineLearningOptimizerEngine

class DynamicSLTPEngine:
    def __init__(self, logger: Any = None):
        self.logger = logger
        self.ml_optimizer = MachineLearningOptimizerEngine(logger=logger)

    def calculate_sl_tp(
        self,
        symbol: str,
        action: str,
        current_price: float,
        structure: Dict[str, Any],
        volatility: Dict[str, Any],
        profile: Dict[str, Any],
        regime: str = "STRONG_TREND_BULLISH"
    ) -> Dict[str, Any]:
        atr = volatility.get("atr", 0.0)
        if atr <= 0.0:
            atr = current_price * 0.005  # 0.5% default fallback

        sl_atr_mult = profile.get("sl_atr_multiplier", 1.5)
        digits = profile.get("digits", 5)

        # Dynamic High-Profit TP Multiplier based on Regime (Min R:R 1:2.0)
        if "STRONG_TREND" in regime:
            tp1_rr_mult = 2.2
            tp2_rr_mult = 4.0
        elif "RANGE" in regime:
            tp1_rr_mult = 2.0
            tp2_rr_mult = 3.0
        else:
            tp1_rr_mult = 2.0
            tp2_rr_mult = 3.5

        swing_high = structure.get("recent_swing_high", current_price + atr * 2)
        swing_low = structure.get("recent_swing_low", current_price - atr * 2)

        sl_price = current_price
        tp1_price = current_price
        tp2_price = current_price

        spread_pips = volatility.get("current_spread_pips", 1.5)
        pip_size = profile.get("pip_size", 0.0001 if digits == 5 else 0.1)
        spread_dist = spread_pips * pip_size

        max_sl_dist = atr * sl_atr_mult  # Dynamic ATR SL Cap from symbol profile

        if action == "BUY":
            struct_sl = swing_low - (atr * 0.25)
            atr_sl = current_price - max_sl_dist
            sl_price = max(struct_sl, atr_sl)  # Take structural or ATR SL
            
            risk_pips = current_price - sl_price
            if risk_pips <= 0 or risk_pips > max_sl_dist:
                risk_pips = max_sl_dist
                sl_price = current_price - risk_pips

            tp1_price = current_price + (risk_pips * tp1_rr_mult)
            tp2_price = current_price + (risk_pips * tp2_rr_mult)

        elif action == "SELL":
            # For SELL, SL must be above swing_high + spread so Ask doesn't trigger SL prematurely
            struct_sl = swing_high + (atr * 0.25) + spread_dist
            atr_sl = current_price + max_sl_dist + spread_dist
            # For SELL, valid SL must be the LARGER price distance (further away from entry) to remain outside structure
            sl_price = max(struct_sl, atr_sl)

            risk_pips = sl_price - current_price
            if risk_pips <= 0 or risk_pips > (max_sl_dist + spread_dist):
                risk_pips = max_sl_dist + spread_dist
                sl_price = current_price + risk_pips

            tp1_price = current_price - (risk_pips * tp1_rr_mult)
            tp2_price = current_price - (risk_pips * tp2_rr_mult)

        # ML MFE/MAE Take-Profit Optimization
        ml_res = self.ml_optimizer.optimize_sl_tp_levels(symbol, regime, current_price, sl_price, tp1_price, tp2_price, atr)
        opt_tp2 = ml_res.get("ml_tp2_price", tp2_price)

        rr_ratio = abs(tp1_price - current_price) / (abs(current_price - sl_price) + 1e-9)

        return {
            "sl_price": round(sl_price, digits),
            "tp1_price": round(tp1_price, digits),
            "tp2_price": round(opt_tp2, digits),
            "risk_pips": round(abs(current_price - sl_price), digits),
            "rr_ratio": round(rr_ratio, 2),
            "ml_mfe_tp_multiplier": ml_res.get("ml_mfe_tp_multiplier"),
            "ml_optimized_rr": ml_res.get("optimized_rr_ratio")
        }

