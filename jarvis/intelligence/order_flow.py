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
            return {'signal': 'NEUTRAL', 'strength': 0.0, 'institutional_activity': False}

        close = df['close']
        open_price = df['open']
        high = df['high']
        low = df['low']
        vol = df['volume']

        vol_ma = vol.rolling(window=self.volume_ma_period).mean()
        current_vol = vol.iloc[-1]
        is_institutional_vol = current_vol > (vol_ma.iloc[-1] * self.extreme_vol_multiplier)

        spread = high - low
        body = abs(close - open_price)
        current_body = body.iloc[-1]
        avg_body = body.rolling(window=self.volume_ma_period).mean().iloc[-1]
        is_bullish = close.iloc[-1] > open_price.iloc[-1]

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
            if current_vol < (vol_ma.iloc[-1] * 0.5):
                strength = 0.3
                signal = 'NEUTRAL'

        return {'signal': signal, 'strength': round(strength, 2), 'institutional_activity': bool(is_institutional_vol), 'current_vol_ratio': round(current_vol / (vol_ma.iloc[-1] + 1e-9), 2)}
