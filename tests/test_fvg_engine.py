import pytest
import pandas as pd
import numpy as np
from jarvis.market.fair_value_gap import FairValueGapEngine

def test_fvg_engine_empty_short_df():
    engine = FairValueGapEngine()
    
    # Test None
    res = engine.analyze(None)
    assert not res['bullish_fvgs']
    
    # Test short DF (<10 rows)
    df = pd.DataFrame({'open': [1], 'high': [2], 'low': [0.5], 'close': [1.5]})
    res = engine.analyze(df)
    assert not res['bullish_fvgs']

def test_fvg_bullish_detection():
    engine = FairValueGapEngine()
    
    # Create 20 candles where later candles stay above 27 so FVG is unmitigated
    data = [{'open': 10, 'high': 15, 'low': 5, 'close': 12} for _ in range(10)]
    data.append({'open': 10, 'high': 15, 'low': 5, 'close': 12})   # idx 10
    data.append({'open': 12, 'high': 25, 'low': 10, 'close': 23})  # idx 11
    data.append({'open': 23, 'high': 30, 'low': 27, 'close': 28})  # idx 12
    for _ in range(7):
        data.append({'open': 28, 'high': 35, 'low': 28, 'close': 30})  # idx 13-19 (low >= 28, above top 27)
    
    df = pd.DataFrame(data)
    res = engine.analyze(df)
    
    assert len(res['bullish_fvgs']) > 0
    fvg = res['bullish_fvgs'][0]
    assert fvg['top'] == 27.0
    assert fvg['bottom'] == 15.0
    assert not fvg['mitigated']

def test_fvg_bearish_detection():
    engine = FairValueGapEngine()
    
    data = [{'open': 30, 'high': 35, 'low': 25, 'close': 28} for _ in range(10)]
    data.append({'open': 30, 'high': 35, 'low': 25, 'close': 26})  # idx 10
    data.append({'open': 26, 'high': 28, 'low': 10, 'close': 12})  # idx 11
    data.append({'open': 12, 'high': 15, 'low': 5, 'close': 8})    # idx 12
    for _ in range(7):
        data.append({'open': 8, 'high': 14, 'low': 4, 'close': 6})     # idx 13-19 (high <= 14, below bottom 15)
    
    df = pd.DataFrame(data)
    res = engine.analyze(df)
    
    assert len(res['bearish_fvgs']) > 0
    fvg = res['bearish_fvgs'][0]
    assert fvg['top'] == 25.0
    assert fvg['bottom'] == 15.0
    assert not fvg['mitigated']

def test_ob_detection():
    engine = FairValueGapEngine()
    
    # Need > 15 rows for ATR calc, need displacement
    data = [{'open': 10.0, 'high': 12.0, 'low': 8.0, 'close': 11.0} for _ in range(20)]
    
    # Bullish OB: prev bearish, curr bullish with displacement
    # ATR will be approx 4 (12-8). Displacement needs body > 1.5 * 4 = 6.
    data[15] = {'open': 12.0, 'high': 12.0, 'low': 8.0, 'close': 8.5} # Bearish
    data[16] = {'open': 9.0, 'high': 20.0, 'low': 8.0, 'close': 19.0} # Bullish, body=10 (displacement)
    
    df = pd.DataFrame(data)
    res = engine.analyze(df)
    
    assert len(res['bullish_obs']) > 0
    ob = res['bullish_obs'][-1]
    assert ob['top'] == 12.0
    assert ob['bottom'] == 8.0

def test_ote_zone_calculation():
    engine = FairValueGapEngine()
    
    # Create 30 bars with distinct swing high and swing low
    data = [{'open': 50, 'high': 55, 'low': 45, 'close': 50} for _ in range(30)]
    
    # Distinct Swing high at 10
    data[10] = {'open': 80, 'high': 100, 'low': 70, 'close': 85}
    # Distinct Swing low at 20
    data[20] = {'open': 15, 'high': 25, 'low': 5, 'close': 15}
    # Current bar close at 25 (below equilibrium (100+5)/2 = 52.5 -> BULLISH OTE)
    data[-1] = {'open': 20, 'high': 30, 'low': 15, 'close': 25}
    
    df = pd.DataFrame(data)
    res = engine.analyze(df)
    
    assert 'ote_705' in res.get('ote_zone', {})
    assert res['ote_zone']['direction'] == 'BULLISH'
