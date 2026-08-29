import pytest
import pandas as pd
import numpy as np
from jarvis.intelligence.mean_reversion import MeanReversionEngine

def test_mean_reversion_empty_df():
    engine = MeanReversionEngine()
    res = engine.evaluate(None, 100.0, 20.0, 50.0)
    assert res['signal'] == 'NONE'
    assert res['reason'] == 'Insufficient data'

def test_mean_reversion_range_detection():
    engine = MeanReversionEngine()
    
    # Create 25 rows of data so rolling(20) works
    # Bollinger Bands 20, StdDev=2.0
    # Mean of 100, no std dev
    data = [{'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000} for _ in range(25)]
    
    # We want a BUY signal:
    # long_cond_1 = is_valid_range (adx < 22) -> True
    # long_cond_2 = c_low < c_lower and c_close > c_lower -> True
    # long_cond_3 = rsi < 35 -> True
    # long_cond_4 = bullish_rejection (c_close > c_open) -> True
    
    # Make the 25th row satisfy cond 2 and 4.
    # To have a lower band, we need some variance in previous rows.
    for i in range(24):
        data[i] = {'open': 100, 'high': 102, 'low': 98, 'close': 100 + (i % 2 - 0.5)*2, 'volume': 1000}
        
    df = pd.DataFrame(data)
    
    # Recalculate to get an actual lower band.
    mid_band = df['close'].rolling(window=20).mean().iloc[-1]
    std_dev = df['close'].rolling(window=20).std().iloc[-1]
    lower_band = mid_band - 2.0 * std_dev
    
    # Make the last row break lower band but close above
    data[24] = {
        'open': lower_band - 1,
        'high': lower_band + 2,
        'low': lower_band - 5,
        'close': lower_band + 1,
        'volume': 1000
    }
    df = pd.DataFrame(data)
    
    res = engine.evaluate(df, current_price=data[24]['close'], adx=20.0, rsi=30.0)
    
    assert res['is_valid_range'] == True
    assert res['signal'] == 'BUY'
    
    # Test ADX > 22 (no signal)
    res_no = engine.evaluate(df, current_price=data[24]['close'], adx=25.0, rsi=30.0)
    assert res_no['signal'] == 'NONE'

def test_mean_reversion_outputs():
    engine = MeanReversionEngine()
    
    # Test short signal
    data = [{'open': 100, 'high': 102, 'low': 98, 'close': 100 + (i % 2 - 0.5)*2, 'volume': 1000} for i in range(24)]
    df = pd.DataFrame(data)
    
    mid_band = df['close'].rolling(window=20).mean().iloc[-1]
    std_dev = df['close'].rolling(window=20).std().iloc[-1]
    upper_band = mid_band + 2.0 * std_dev
    
    # Break upper band but close below it (Bearish rejection)
    data.append({
        'open': upper_band + 1,
        'high': upper_band + 5,
        'low': upper_band - 2,
        'close': upper_band - 1,
        'volume': 1000
    })
    
    df = pd.DataFrame(data)
    expected_mid = df['close'].rolling(window=20).mean().iloc[-1]
    res = engine.evaluate(df, current_price=data[-1]['close'], adx=15.0, rsi=75.0)
    
    assert res['signal'] == 'SELL'
    assert res['tp_price'] == round(expected_mid, 5)
    assert res['sl_price'] > upper_band  # Stop loss beyond wick
    assert res['confluence_score'] > 0
