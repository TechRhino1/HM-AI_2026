import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any

logger = logging.getLogger('JARVIS_FVG')

class FairValueGapEngine:
    """ICT Fair Value Gap (FVG) & Order Block (OB) Detection Engine.
    Detects institutional price imbalance zones for high-probability entries."""

    def analyze(self, df: pd.DataFrame) -> dict:
        """Analyze dataframe for FVGs, Order Blocks, and OTE zones."""
        result = {
            'bullish_fvgs': [],
            'bearish_fvgs': [],
            'bullish_obs': [],
            'bearish_obs': [],
            'active_bullish_fvg': None,
            'active_bearish_fvg': None,
            'active_bullish_ob': None,
            'active_bearish_ob': None,
            'price_in_fvg': False,
            'price_in_ob': False,
            'ote_zone': {},
            'fvg_ob_confluence': False
        }
        
        required_cols = ['open', 'high', 'low', 'close']
        if df is None or len(df) < 10 or not all(col in df.columns for col in required_cols):
            return result
            
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        n_bars = len(df)
        current_price = float(closes[-1])
        
        # 14 period ATR
        if n_bars >= 15:
            tr1 = highs[-14:] - lows[-14:]
            tr2 = np.abs(highs[-14:] - closes[-15:-1])
            tr3 = np.abs(lows[-14:] - closes[-15:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            atr_14 = float(np.mean(tr))
        else:
            atr_14 = float(highs.max() - lows.min()) / max(1, n_bars)
            
        atr_14 = max(atr_14, 1e-5)

        # 1. FVG Detection & Mitigation (Last 50 candles)
        fvg_lookback = min(50, n_bars)
        fvg_start = n_bars - fvg_lookback
        bullish_fvgs = []
        bearish_fvgs = []
        
        for i in range(fvg_start + 2, n_bars):
            c1_high = float(highs[i - 2])
            c1_low = float(lows[i - 2])
            c3_high = float(highs[i])
            c3_low = float(lows[i])
            
            # Bullish FVG: c1_high < c3_low
            if c1_high < c3_low:
                top = c3_low
                bottom = c1_high
                mitigated = bool(np.any(lows[i + 1:] <= top)) if i + 1 < n_bars else False
                bullish_fvgs.append({
                    'top': top,
                    'bottom': bottom,
                    'bar_idx': i - 2,
                    'mitigated': mitigated
                })
                
            # Bearish FVG: c1_low > c3_high
            elif c1_low > c3_high:
                top = c1_low
                bottom = c3_high
                mitigated = bool(np.any(highs[i + 1:] >= bottom)) if i + 1 < n_bars else False
                bearish_fvgs.append({
                    'top': top,
                    'bottom': bottom,
                    'bar_idx': i - 2,
                    'mitigated': mitigated
                })

        result['bullish_fvgs'] = bullish_fvgs
        result['bearish_fvgs'] = bearish_fvgs
        
        # 2. OB Detection (Last 30 candles)
        ob_lookback = min(30, n_bars)
        ob_start = n_bars - ob_lookback
        bullish_obs = []
        bearish_obs = []
        
        for i in range(ob_start + 1, n_bars):
            prev_o, prev_c = float(opens[i - 1]), float(closes[i - 1])
            prev_h, prev_l = float(highs[i - 1]), float(lows[i - 1])
            curr_o, curr_c = float(opens[i]), float(closes[i])
            
            body_size = abs(curr_c - curr_o)
            if body_size > (1.5 * atr_14):
                if curr_c > curr_o and prev_c < prev_o:
                    # Bullish OB
                    top, bottom = prev_h, prev_l
                    mitigated = bool(np.any(lows[i + 1:] <= top)) if i + 1 < n_bars else False
                    bullish_obs.append({'top': top, 'bottom': bottom, 'bar_idx': i - 1, 'mitigated': mitigated})
                    
                elif curr_c < curr_o and prev_c > prev_o:
                    # Bearish OB
                    top, bottom = prev_h, prev_l
                    mitigated = bool(np.any(highs[i + 1:] >= bottom)) if i + 1 < n_bars else False
                    bearish_obs.append({'top': top, 'bottom': bottom, 'bar_idx': i - 1, 'mitigated': mitigated})

        result['bullish_obs'] = bullish_obs
        result['bearish_obs'] = bearish_obs
        
        # Active unmitigated FVGs and OBs
        unmitigated_bullish_fvgs = [f for f in bullish_fvgs if not f['mitigated']]
        unmitigated_bearish_fvgs = [f for f in bearish_fvgs if not f['mitigated']]
        
        if unmitigated_bullish_fvgs:
            result['active_bullish_fvg'] = unmitigated_bullish_fvgs[-1]
            if result['active_bullish_fvg']['bottom'] <= current_price <= result['active_bullish_fvg']['top']:
                result['price_in_fvg'] = True
                
        if unmitigated_bearish_fvgs:
            result['active_bearish_fvg'] = unmitigated_bearish_fvgs[-1]
            if result['active_bearish_fvg']['bottom'] <= current_price <= result['active_bearish_fvg']['top']:
                result['price_in_fvg'] = True

        unmitigated_bullish_obs = [ob for ob in bullish_obs if not ob['mitigated']]
        unmitigated_bearish_obs = [ob for ob in bearish_obs if not ob['mitigated']]
        
        if unmitigated_bullish_obs:
            result['active_bullish_ob'] = unmitigated_bullish_obs[-1]
            if result['active_bullish_ob']['bottom'] <= current_price <= result['active_bullish_ob']['top']:
                result['price_in_ob'] = True
                
        if unmitigated_bearish_obs:
            result['active_bearish_ob'] = unmitigated_bearish_obs[-1]
            if result['active_bearish_ob']['bottom'] <= current_price <= result['active_bearish_ob']['top']:
                result['price_in_ob'] = True

        # 3. Confluence Detection (Active FVG overlaps with Active OB)
        active_fvgs = []
        if result['active_bullish_fvg']: active_fvgs.append(result['active_bullish_fvg'])
        if result['active_bearish_fvg']: active_fvgs.append(result['active_bearish_fvg'])
        
        active_obs = []
        if result['active_bullish_ob']: active_obs.append(result['active_bullish_ob'])
        if result['active_bearish_ob']: active_obs.append(result['active_bearish_ob'])
        
        for fvg in active_fvgs:
            for ob in active_obs:
                if fvg['bottom'] <= ob['top'] and fvg['top'] >= ob['bottom']:
                    result['fvg_ob_confluence'] = True
                    break

        # 4. OTE Zone Calculation (Recent 60 bars)
        pivot_window = 5
        ote_start = max(0, n_bars - 60)
        h_slice = highs[ote_start:]
        l_slice = lows[ote_start:]
        n_slice = len(h_slice)
        
        if n_slice > pivot_window * 2:
            swing_highs = []
            swing_lows = []
            
            for i in range(pivot_window, n_slice - pivot_window):
                if h_slice[i] == np.max(h_slice[i - pivot_window : i + pivot_window + 1]):
                    swing_highs.append(float(h_slice[i]))
                if l_slice[i] == np.min(l_slice[i - pivot_window : i + pivot_window + 1]):
                    swing_lows.append(float(l_slice[i]))
                    
            if swing_highs and swing_lows:
                recent_sh = swing_highs[-1]
                recent_sl = swing_lows[-1]
                swing_range = recent_sh - recent_sl
                equilibrium = (recent_sh + recent_sl) / 2.0
                
                if current_price > equilibrium:
                    result['ote_zone'] = {
                        'ote_62': recent_sh - 0.62 * swing_range,
                        'ote_705': recent_sh - 0.705 * swing_range,
                        'ote_79': recent_sh - 0.79 * swing_range,
                        'direction': 'BEARISH'
                    }
                else:
                    result['ote_zone'] = {
                        'ote_62': recent_sl + 0.62 * swing_range,
                        'ote_705': recent_sl + 0.705 * swing_range,
                        'ote_79': recent_sl + 0.79 * swing_range,
                        'direction': 'BULLISH'
                    }
                    
        return result
