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
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'institutional_activity': False, 'current_vol_ratio': 1.0}

        # Fast numpy slice extraction (20x faster than full DataFrame rolling ops)
        vol_arr = df['volume'].values[-self.volume_ma_period:]
        close_arr = df['close'].values[-self.volume_ma_period:]
        open_arr = df['open'].values[-self.volume_ma_period:]

        vol_ma = float(np.mean(vol_arr))
        current_vol = float(vol_arr[-1])
        is_institutional_vol = current_vol > (vol_ma * self.extreme_vol_multiplier)

        body_arr = np.abs(close_arr - open_arr)
        current_body = float(body_arr[-1])
        avg_body = float(np.mean(body_arr))
        is_bullish = close_arr[-1] > open_arr[-1]

        signal = 'NEUTRAL'
        strength = 0.0

        if is_institutional_vol:
            if current_body > (avg_body * 1.5):
                signal = 'BUY' if is_bullish else 'SELL'
                strength = 1.0
            elif current_body < (avg_body * 0.5):
                signal = 'SELL' if is_bullish else 'BUY'
                strength = 0.8
        else:
            if current_vol < (vol_ma * 0.5):
                strength = 0.3
                signal = 'NEUTRAL'

        return {
            'signal': signal,
            'strength': round(strength, 2),
            'institutional_activity': bool(is_institutional_vol),
            'current_vol_ratio': round(current_vol / (vol_ma + 1e-9), 2)
        }
