"""
Unit and Integration Tests for JARVIS Dynamic Market Data Hydration Architecture.
Verifies real-time field resolution, thread-safe caching (<0.1ms), arbitrary ticker resolution,
batch hydration, and US/Indian universe integration.
"""
import concurrent.futures
import time
import unittest
from typing import Dict, Any, List

from jarvis.data.dynamic_hydrator import (
    DynamicMarketDataHydrator,
    DYNAMIC_HYDRATOR,
    format_market_cap,
    format_avg_volume,
)
from jarvis.stocks.universe import get_stock_profile, STOCK_UNIVERSE
from jarvis.india.universe import get_india_profile, INDIA_UNIVERSE


class TestDynamicMarketDataHydrator(unittest.TestCase):
    """Test suite for DynamicMarketDataHydrator."""

    def setUp(self):
        self.hydrator = DynamicMarketDataHydrator(cache_ttl_sec=60.0)

    def test_format_market_cap_us(self):
        """Validates US market capitalization dollar formatting."""
        self.assertIn(format_market_cap(4_665_000_000_000, market="US"), ["$4.66T", "$4.67T"])
        self.assertIn("$", format_market_cap(4_665_000_000_000, market="US"))
        self.assertEqual(format_market_cap(216_500_000_000, market="US"), "$216.5B")
        self.assertEqual(format_market_cap(50_000_000, market="US"), "$50.0M")
        self.assertEqual(format_market_cap("$3.45T", market="US"), "$3.45T")

    def test_format_market_cap_india(self):
        """Validates Indian market capitalization rupee/Lakh Cr formatting."""
        # 1.738e13 INR = 17.38 Lakh Cr
        cap_lakh_cr = format_market_cap(17_381_193_502_259, market="IN")
        self.assertIn("Lakh Cr", cap_lakh_cr)
        self.assertIn("₹", cap_lakh_cr)

        # 7.739e11 INR = 77,399 Cr
        cap_cr = format_market_cap(773_991_881_981, market="IN")
        self.assertIn("Cr", cap_cr)
        self.assertIn("₹", cap_cr)

    def test_format_avg_volume(self):
        """Validates volume formatting."""
        self.assertEqual(format_avg_volume(48_500_000), "48.5M")
        self.assertEqual(format_avg_volume(1_200_000_000), "1.2B")
        self.assertEqual(format_avg_volume(500_000), "500.0K")
        self.assertEqual(format_avg_volume("46.2M"), "46.2M")

    def test_us_equities_hydration(self):
        """Tests live dynamic field resolution for key US equities (AAPL, NVDA, PLTR)."""
        symbols = ["AAPL", "NVDA", "PLTR"]
        for sym in symbols:
            profile = self.hydrator.get_profile(sym, market="US")
            self.assertIsInstance(profile, dict)
            self.assertEqual(profile["symbol"], sym)
            self.assertIn("name", profile)
            self.assertIn("sector", profile)
            self.assertIn("industry", profile)
            self.assertIn("market", profile)
            self.assertIn("description", profile)
            
            # Dynamic fields verification
            self.assertGreater(profile["price"], 0.0)
            self.assertIn("change_val", profile)
            self.assertIn("change_pct", profile)
            self.assertIn("market_cap", profile)
            self.assertIn("pe_ratio", profile)
            self.assertGreater(profile["week52_high"], 0.0)
            self.assertGreater(profile["week52_low"], 0.0)
            self.assertGreaterEqual(profile["week52_high"], profile["week52_low"])
            self.assertGreater(profile["beta"], 0.0)
            self.assertIn("avg_volume", profile)
            self.assertIn("rsi", profile)
            self.assertIn("macd", profile)
            self.assertIn("recommendation", profile)

    def test_indian_equities_and_indices_hydration(self):
        """Tests live dynamic field resolution for Indian stocks and indices (NIFTY, TATAMOTORS, RELIANCE, TCS)."""
        symbols = ["NIFTY", "TATAMOTORS", "RELIANCE", "TCS"]
        for sym in symbols:
            profile = self.hydrator.get_profile(sym, market="IN")
            self.assertIsInstance(profile, dict)
            expected_sym = "TMPV" if sym in ("TATAMOTORS", "TATA_MOTORS") else sym
            self.assertEqual(profile["symbol"], expected_sym)
            self.assertIn("name", profile)
            self.assertIn("sector", profile)
            self.assertIn("industry", profile)
            self.assertIn("market", profile)
            
            # Price & 52-week range checks
            self.assertGreater(profile["price"], 0.0)
            self.assertGreater(profile["week52_high"], 0.0)
            self.assertGreater(profile["week52_low"], 0.0)
            self.assertGreaterEqual(profile["week52_high"], profile["week52_low"])
            
            # Market cap & valuation checks
            self.assertIn("market_cap", profile)
            self.assertIn("pe_ratio", profile)
            self.assertIn("beta", profile)
            self.assertIn("avg_volume", profile)
            self.assertIn("rsi", profile)
            self.assertIn("macd", profile)
            self.assertIn("recommendation", profile)
            
            # India specific field checks
            self.assertIn("lot_size", profile)
            self.assertIn("is_index", profile)
            self.assertIn("circuit_limit_pct", profile)

        # Index verification
        nifty = self.hydrator.get_profile("NIFTY", market="IN")
        self.assertTrue(nifty["is_index"])
        self.assertGreater(nifty["price"], 10000.0)

        # Equity verification
        reliance = self.hydrator.get_profile("RELIANCE", market="IN")
        self.assertFalse(reliance["is_index"])
        self.assertIn("₹", reliance["market_cap"])

    def test_arbitrary_ticker_support_on_the_fly(self):
        """Tests dynamic profile construction for newly listed or arbitrary tickers."""
        # Indian newly listed / emerging tickers
        for sym in ["SWIGGY", "HYUNDAI", "SMCI", "MSTR"]:
            mkt = "IN" if sym in ("SWIGGY", "HYUNDAI") else "US"
            prof = self.hydrator.get_profile(sym, market=mkt)
            self.assertIsNotNone(prof)
            self.assertEqual(prof["symbol"], sym)
            self.assertGreater(prof["price"], 0.0)
            self.assertGreater(prof["beta"], 0.0)
            self.assertIn("market_cap", prof)
            self.assertIn("avg_volume", prof)

        # Completely custom unknown ticker
        unknown_prof = self.hydrator.get_profile("UNLISTED_AI_TECH", market="US")
        self.assertIsNotNone(unknown_prof)
        self.assertEqual(unknown_prof["symbol"], "UNLISTED_AI_TECH")
        self.assertGreater(unknown_prof["price"], 0.0)
        self.assertGreater(unknown_prof["week52_high"], unknown_prof["week52_low"])

    def test_cache_hit_latency(self):
        """Validates that cached profile lookups execute in < 0.1ms."""
        # Prime cache
        self.hydrator.get_profile("AAPL", market="US")

        t0 = time.perf_counter()
        n_iters = 5000
        for _ in range(n_iters):
            p = self.hydrator.get_profile("AAPL", market="US")
        elapsed_total = time.perf_counter() - t0
        avg_ms = (elapsed_total / n_iters) * 1000.0

        # Must return in < 0.1ms
        self.assertLess(avg_ms, 0.1, f"Cached lookup took {avg_ms:.4f}ms, expected < 0.1ms")

    def test_thread_safety_concurrent_access(self):
        """Tests thread safety under high-concurrency access."""
        symbols = ["AAPL", "NVDA", "MSFT", "RELIANCE", "TCS", "NIFTY"]
        for s in symbols:
            mkt = "IN" if s in ("RELIANCE", "TCS", "NIFTY") else "US"
            self.hydrator.get_profile(s, market=mkt)
        
        def _fetch(sym: str) -> Dict[str, Any]:
            mkt = "IN" if sym in ("RELIANCE", "TCS", "NIFTY") else "US"
            return self.hydrator.get_profile(sym, market=mkt)

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            tasks = [executor.submit(_fetch, s) for _ in range(10) for s in symbols]
            results = [t.result() for t in concurrent.futures.as_completed(tasks)]

        self.assertEqual(len(results), 60)
        for r in results:
            self.assertGreater(r["price"], 0.0)

    def test_hydrate_batch(self):
        """Tests multi-symbol batch hydration."""
        us_batch = ["AAPL", "NVDA", "TSLA", "AMZN"]
        res = self.hydrator.hydrate_batch(us_batch, market="US")
        self.assertEqual(len(res), 4)
        for sym in us_batch:
            self.assertIn(sym, res)
            self.assertEqual(res[sym]["symbol"], sym)
            self.assertGreater(res[sym]["price"], 0.0)

    def test_wire_into_us_stock_universe(self):
        """Verifies get_stock_profile queries dynamic hydrator with baseline fallback."""
        profile = get_stock_profile("AAPL")
        self.assertEqual(profile["symbol"], "AAPL")
        self.assertEqual(profile["base_price"], 319.75)  # Baseline preserved
        self.assertGreater(profile["price"], 0.0)
        self.assertIn("market_cap", profile)
        self.assertIn("pe_ratio", profile)
        self.assertIn("rsi", profile)
        self.assertIn("macd", profile)

    def test_wire_into_india_universe(self):
        """Verifies get_india_profile queries dynamic hydrator with baseline fallback."""
        profile = get_india_profile("RELIANCE")
        self.assertEqual(profile["symbol"], "RELIANCE")
        self.assertEqual(profile["base_price"], 1287.0)  # Baseline preserved
        self.assertGreater(profile["price"], 0.0)
        self.assertIn("₹", profile["market_cap"])
        self.assertIn("lot_size", profile)

        # Alias conversion
        tmpv_profile = get_india_profile("TATAMOTORS")
        self.assertEqual(tmpv_profile["symbol"], "TMPV")
        self.assertIn("Tata", tmpv_profile["name"])


if __name__ == "__main__":
    unittest.main()
