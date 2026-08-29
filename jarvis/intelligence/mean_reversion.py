import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MeanReversionEngine:
    """Bollinger Band Mean Reversion Engine for ranging market regimes.
    Activated when ADX < 22 and regime is RANGE/LOW_VOLATILITY.
    Research shows 71-78% win rate on ranging Forex pairs targeting the 20 SMA mean."""

    def evaluate(self, df: pd.DataFrame, current_price: float, adx: float, rsi: float) -> dict:
        """Evaluate mean reversion setup quality.
        
        Returns dict with:
        - 'signal': 'BUY', 'SELL', or 'NONE'
        - 'is_valid_range': bool — ADX < 22 confirmed
        - 'bb_upper': float — upper Bollinger Band
        - 'bb_lower': float — lower Bollinger Band  
        - 'bb_mid': float — 20 SMA (mean target)
        - 'entry_price': float — suggested entry
        - 'sl_price': float — stop loss beyond the wick extreme + 1.0*ATR buffer
        - 'tp_price': float — take profit at 20 SMA (middle band)
        - 'confluence_score': float 0-100 — quality of the mean reversion setup
        - 'reason': str — human-readable explanation
        - 'max_bars_to_hold': int — default 12
        """
        
        empty_result = {
            'signal': 'NONE',
            'is_valid_range': False,
            'bb_upper': 0.0,
            'bb_lower': 0.0,
            'bb_mid': 0.0,
            'entry_price': 0.0,
            'sl_price': 0.0,
            'tp_price': 0.0,
            'confluence_score': 0.0,
            'reason': 'Insufficient data',
            'max_bars_to_hold': 12
        }

        if df is None or len(df) < 20:
            logger.info("MeanReversionEngine: Dataframe too short (<20 bars).")
            return empty_result
            
        try:
            # 1. Calculate Bollinger Bands (Period=20, StdDev=2.0)
            mid_band = df['close'].rolling(window=20).mean()
            std_dev = df['close'].rolling(window=20).std()
            upper_band = mid_band + (2.0 * std_dev)
            lower_band = mid_band - (2.0 * std_dev)
            
            # 2. Calculate ATR for Stop Loss (Period=14)
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift(1))
            low_close = np.abs(df['low'] - df['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            
            # BB Width calculation for percentiles
            bb_width = (upper_band - lower_band) / mid_band
            bb_width_percentile = bb_width.rank(pct=True).iloc[-1]
            
            # Volume average
            vol_avg = df['volume'].rolling(window=20).mean()
            
            # Current bar data
            current_bar = df.iloc[-1]
            c_open = current_bar['open']
            c_high = current_bar['high']
            c_low = current_bar['low']
            c_close = current_bar['close']
            c_vol = current_bar.get('volume', 0.0)
            
            c_upper = upper_band.iloc[-1]
            c_lower = lower_band.iloc[-1]
            c_mid = mid_band.iloc[-1]
            c_atr = atr.iloc[-1]
            c_vol_avg = vol_avg.iloc[-1]
            
            is_valid_range = adx < 22
            
            # Determine candle structure
            body = abs(c_close - c_open)
            upper_wick = c_high - max(c_open, c_close)
            lower_wick = min(c_open, c_close) - c_low
            
            is_bullish_candle = c_close > c_open
            is_bearish_candle = c_close < c_open
            
            bullish_rejection = is_bullish_candle or (lower_wick > 2 * body)
            bearish_rejection = is_bearish_candle or (upper_wick > 2 * body)
            
            # Initialize response fields
            signal = 'NONE'
            reason = 'No clear setup'
            entry_price = current_price
            sl_price = 0.0
            tp_price = c_mid
            confluence_score = 0.0
            
            # Evaluate LONG condition
            long_cond_1 = is_valid_range
            long_cond_2 = (c_low < c_lower) and (c_close > c_lower)  # Breaks below lower BB but closes inside
            long_cond_3 = rsi < 35
            long_cond_4 = bullish_rejection
            
            # Evaluate SHORT condition
            short_cond_1 = is_valid_range
            short_cond_2 = (c_high > c_upper) and (c_close < c_upper) # Breaks above upper BB but closes inside
            short_cond_3 = rsi > 65
            short_cond_4 = bearish_rejection
            
            if long_cond_1 and long_cond_2 and long_cond_3 and long_cond_4:
                signal = 'BUY'
                sl_price = c_low - (1.0 * c_atr)
                reason = 'Bollinger Band Lower Rejection in Range'
            elif short_cond_1 and short_cond_2 and short_cond_3 and short_cond_4:
                signal = 'SELL'
                sl_price = c_high + (1.0 * c_atr)
                reason = 'Bollinger Band Upper Rejection in Range'
                
            # If a signal was generated, calculate the confluence score
            if signal != 'NONE':
                # +25 if ADX < 18 (strong range)
                if adx < 18:
                    confluence_score += 25.0
                    
                # +25 if RSI is in oversold/overbought zone (e.g., <30 or >70)
                if (signal == 'BUY' and rsi < 30) or (signal == 'SELL' and rsi > 70):
                    confluence_score += 25.0
                elif (signal == 'BUY' and rsi < 35) or (signal == 'SELL' and rsi > 65):
                    # Already meets entry, but might just get partial or same score. We'll give 25 if strictly <30/>70 as per typical extreme, or just give 25 for meeting the rule. Let's give 25 for <30/>70.
                    # Wait, prompt says: "+25 if RSI is in oversold/overbought zone". We can just give it if <30 or >70.
                    pass
                
                # +20 if rejection candle pattern present (which is a requirement, so always adds 20)
                confluence_score += 20.0
                
                # +15 if BB width is between 20th-80th percentile (normal volatility, not squeezed)
                if 0.20 <= bb_width_percentile <= 0.80:
                    confluence_score += 15.0
                    
                # +15 if volume is above average (institutional interest)
                if c_vol > c_vol_avg:
                    confluence_score += 15.0
                    
            return {
                'signal': signal,
                'is_valid_range': is_valid_range,
                'bb_upper': round(c_upper, 5),
                'bb_lower': round(c_lower, 5),
                'bb_mid': round(c_mid, 5),
                'entry_price': round(entry_price, 5),
                'sl_price': round(sl_price, 5),
                'tp_price': round(tp_price, 5),
                'confluence_score': confluence_score,
                'reason': reason,
                'max_bars_to_hold': 12
            }
            
        except Exception as e:
            logger.error(f"MeanReversionEngine calculation error: {str(e)}")
            empty_result['reason'] = f'Error: {str(e)}'
            return empty_result
