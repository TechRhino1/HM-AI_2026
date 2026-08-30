import os
import sys
import time

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from jarvis.india.india_service import INDIA_SERVICE
from jarvis.india.options_engine import INDIA_OPTIONS
from jarvis.india.india_engine import INDIA_ENGINE
from jarvis.india.universe import INDIA_UNIVERSE

def test_india_market_engine_performance():
    print("Testing Indices Snapshot...")
    t0 = time.time()
    indices = INDIA_SERVICE.get_indices_snapshot()
    t1 = time.time()
    print(f"Indices count: {len(indices)}, Cold Time: {t1-t0:.4f}s")
    assert len(indices) == 7
    for idx in indices:
        assert idx["price"] > 0
        print(f"  {idx['symbol']}: price={idx['price']}, change={idx['change_pct']}%")

    print("\nTesting Warm Indices Snapshot...")
    t0 = time.time()
    indices_warm = INDIA_SERVICE.get_indices_snapshot()
    t1 = time.time()
    warm_ms = (t1 - t0) * 1000.0
    print(f"Indices Warm Time: {warm_ms:.2f}ms")
    assert warm_ms < 50.0

    print("\nTesting Scanner Data (Cold)...")
    t0 = time.time()
    scanner = INDIA_SERVICE.get_scanner_data()
    t1 = time.time()
    print(f"Scanner count: {scanner['count']}, Cold Time: {t1-t0:.4f}s")
    assert scanner["count"] >= 30
    assert len(scanner["ai_recommended_buys"]) == 4

    print("\nTesting Scanner Data (Warm Cache)...")
    t0 = time.time()
    scanner_warm = INDIA_SERVICE.get_scanner_data()
    t1 = time.time()
    scanner_warm_ms = (t1 - t0) * 1000.0
    print(f"Scanner Warm Time: {scanner_warm_ms:.2f}ms")
    assert scanner_warm_ms < 10.0

    print("\nTesting NIFTY Option Chain...")
    t0 = time.time()
    chain_nifty = INDIA_OPTIONS.generate_option_chain("NIFTY")
    t1 = time.time()
    print(f"NIFTY Spot: {chain_nifty['spot_price']}, ATM: {chain_nifty['atm_strike']}, Max Pain: {chain_nifty['max_pain_strike']}, Time: {t1-t0:.4f}s")
    assert chain_nifty["spot_price"] == 24175.65
    assert chain_nifty["atm_strike"] in (24150.0, 24200.0)
    assert len(chain_nifty["chain"]) == 25

    print("\nTesting BANKNIFTY Option Chain...")
    t0 = time.time()
    chain_bank = INDIA_OPTIONS.generate_option_chain("BANKNIFTY")
    t1 = time.time()
    print(f"BANKNIFTY Spot: {chain_bank['spot_price']}, ATM: {chain_bank['atm_strike']}, Max Pain: {chain_bank['max_pain_strike']}, Time: {t1-t0:.4f}s")
    assert chain_bank["spot_price"] == 57496.30
    assert chain_bank["atm_strike"] == 57500.0
    assert chain_bank["lot_size"] == 15

    print("\nTesting AI Options Strategies...")
    t0 = time.time()
    strat = INDIA_OPTIONS.generate_ai_options_strategy("NIFTY", bias="BULL_CALL_SPREAD")
    t1 = time.time()
    print(f"Strategy: {strat['strategy_name']}, Spot: {strat['spot_price']}, Max Profit: INR {strat['max_profit_inr']}, Time: {t1-t0:.4f}s")
    assert "BULL CALL" in strat["strategy_name"]
    assert strat["spot_price"] == 24175.65

    print("\nALL PERFORMANCE AND VALUATION TESTS PASSED!")

if __name__ == "__main__":
    test_india_market_engine_performance()
