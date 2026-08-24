import pandas as pd
import numpy as np
import logging

logger = logging.getLogger('JARVIS_OrderFlow')

class InstitutionalVolumeOrderFlowEngine:
    def __init__(self, volume_ma_period=20, extreme_vol_multiplier=2.5):
        self.volume_ma_period = volume_ma_period
        self.extreme_vol_multiplier = extreme_vol_multiplier

    def analyze_order_flow(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < self.volume_ma_period:
            return {
                'signal': 'NEUTRAL',
                'strength': 0.0,
                'institutional_activity': False,
                'current_vol_ratio': 1.0,
                'delta_ratio': 0.0,
                'absorption_trap': None,
                'delta_score': 0.0
            }

        # Fast numpy slice extraction
        vol_arr = df['volume'].values[-self.volume_ma_period:].astype(float)
        close_arr = df['close'].values[-self.volume_ma_period:].astype(float)
        open_arr = df['open'].values[-self.volume_ma_period:].astype(float)
        high_arr = df['high'].values[-self.volume_ma_period:].astype(float) if 'high' in df else close_arr
        low_arr = df['low'].values[-self.volume_ma_period:].astype(float) if 'low' in df else open_arr

        vol_ma = float(np.mean(vol_arr))
        current_vol = float(vol_arr[-1])
        is_institutional_vol = current_vol > (vol_ma * self.extreme_vol_multiplier)

        body_arr = np.abs(close_arr - open_arr)
        current_body = float(body_arr[-1])
        avg_body = float(np.mean(body_arr))
        is_bullish = close_arr[-1] > open_arr[-1]

        # ── Footprint Volume Delta Calculation ──
        ranges = np.maximum(high_arr - low_arr, 1e-9)
        buy_vols = vol_arr * ((close_arr - low_arr) / ranges)
        sell_vols = vol_arr * ((high_arr - close_arr) / ranges)
        deltas = buy_vols - sell_vols

        latest_delta = float(deltas[-1])
        recent_cum_delta = float(np.sum(deltas[-3:]))
        delta_ratio = float(latest_delta / (vol_ma + 1e-9))
        delta_score = float(np.clip((recent_cum_delta / (vol_ma * 3.0 + 1e-9)) * 100.0, -100.0, 100.0))

        # ── Absorption Trap Detection ──
        # Seller Absorption: Bullish candle body but strong negative delta -> institutional selling absorption
        # Buyer Absorption: Bearish candle body but strong positive delta -> institutional buying absorption
        absorption_trap = None
        if is_bullish and latest_delta < (-0.20 * current_vol) and is_institutional_vol:
            absorption_trap = "SELLER_ABSORPTION_TRAP"
            logger.warning(f"⚠️ Order Flow: SELLER_ABSORPTION_TRAP detected! Bullish candle with negative delta ({latest_delta:.1f}).")
        elif (not is_bullish) and latest_delta > (0.20 * current_vol) and is_institutional_vol:
            absorption_trap = "BUYER_ABSORPTION_TRAP"
            logger.warning(f"⚠️ Order Flow: BUYER_ABSORPTION_TRAP detected! Bearish candle with positive delta (+{latest_delta:.1f}).")

        signal = 'NEUTRAL'
        strength = 0.0

        if is_institutional_vol:
            if current_body > (avg_body * 1.5):
                if absorption_trap == "SELLER_ABSORPTION_TRAP" and is_bullish:
                    signal = 'NEUTRAL'  # Trap cancels signal
                    strength = 0.0
                elif absorption_trap == "BUYER_ABSORPTION_TRAP" and (not is_bullish):
                    signal = 'NEUTRAL'
                    strength = 0.0
                else:
                    signal = 'BUY' if (is_bullish or latest_delta > 0) else 'SELL'
                    strength = 1.0
            elif current_body < (avg_body * 0.5):
                signal = 'SELL' if is_bullish else 'BUY'
                strength = 0.8
        else:
            if delta_score > 35.0:
                signal = 'BUY'
                strength = 0.6
            elif delta_score < -35.0:
                signal = 'SELL'
                strength = 0.6

        return {
            'signal': signal,
            'strength': round(strength, 2),
            'institutional_activity': bool(is_institutional_vol),
            'current_vol_ratio': round(current_vol / (vol_ma + 1e-9), 2),
            'delta_ratio': round(delta_ratio, 2),
            'absorption_trap': absorption_trap,
            'delta_score': round(delta_score, 1)
        }

