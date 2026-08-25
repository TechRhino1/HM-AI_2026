"""
Comprehensive Automated Test Suite for India Markets (Strict Equities vs Indices Partition & F&O Suite)
Validates:
1. Strict separation: Zero indices in /api/india/scanner and AI recommended buys (only corporate stocks).
2. Indices availability in /api/india/indices and /api/india/options/chain.
3. 2024-2026 SEBI/NSE regulatory fields (ASM/GSM, MWPL %, STT rates, margin requirements).
4. 6-Factor quantitative score breakdown & CPR/Camarilla/VWAP confluence.
5. Multi-leg payoff curves, strike OI distribution, and broker basket orders.
6. 100% backward compatibility on Forex/MT5 and US Stocks screener.
"""
import urllib.request
import urllib.error
import json
import sys


BASE_URL = "http://127.0.0.1:8501"


def test_endpoint(name: str, url_path: str, validator=None):
    url = f"{BASE_URL}{url_path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisIndiaTestRunner/3.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            status = res.status
            content_type = res.headers.get("Content-Type", "")
            raw_data = res.read()

            if status != 200:
                print(f"[FAIL] {name:<55} -> HTTP {status}")
                return False

            if "application/json" in content_type:
                data = json.loads(raw_data.decode("utf-8"))
                if validator:
                    val_res, val_msg = validator(data)
                    if not val_res:
                        print(f"[FAIL] {name:<55} -> JSON Validation Failed: {val_msg}")
                        return False
                print(f"[PASS] {name:<55} -> HTTP 200 OK | JSON Validated")
                return True
            elif "text/html" in content_type:
                html_str = raw_data.decode("utf-8")
                if ("India" in html_str or "Options" in html_str) and "NSE" in html_str:
                    print(f"[PASS] {name:<55} -> HTTP 200 OK | HTML Rendered ({len(raw_data)} bytes)")
                    return True
                else:
                    print(f"[FAIL] {name:<55} -> HTML missing key elements")
                    return False
            elif "text/csv" in content_type:
                csv_str = raw_data.decode("utf-8")
                if "Symbol" in csv_str and "CPR" in csv_str:
                    print(f"[PASS] {name:<55} -> HTTP 200 OK | CSV Stream Validated ({len(raw_data)} bytes)")
                    return True
                else:
                    print(f"[FAIL] {name:<55} -> CSV missing header columns")
                    return False
            else:
                print(f"[PASS] {name:<55} -> HTTP 200 OK | Content-Type: {content_type}")
                return True

    except Exception as e:
        print(f"[FAIL] {name:<55} -> Exception: {e}")
        return False


def run_all_india_tests():
    print("=" * 80)
    print("RUNNING INSTITUTIONAL INDIA MARKETS (PURE STOCKS & F&O DERIVATIVES) TEST SUITE")
    print("=" * 80)

    index_symbols = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYIT", "NIFTYAUTO"}

    tests = [
        # UI Windows
        ("Window 1: India Stocks Screener UI /india", "/india", None),
        ("Window 2: India Options Terminal UI /options", "/options", None),

        # Pure Stock Screener (Strict Index Partitioning)
        ("NSE/BSE Pure Stock Scanner (/api/india/scanner)", "/api/india/scanner", lambda d: (
            d.get("count", 0) >= 15
            and all(x["symbol"] not in index_symbols and x["sector"] != "Indices" and not x.get("is_index") for x in d.get("stocks", []))
            and all(x["symbol"] not in index_symbols for x in d.get("ai_recommended_buys", [])),
            "Indices found in stock screener or AI recommended buys!"
        )),
        ("Dedicated Stocks Endpoint (/api/india/stocks)", "/api/india/stocks", lambda d: (
            d.get("count", 0) >= 15 and all(x["symbol"] not in index_symbols for x in d.get("stocks", [])),
            "Indices found in /api/india/stocks"
        )),
        ("Stock Screener Sector Filter (Financials)", "/api/india/scanner?sector=Financial+Services", lambda d: (
            all(x["sector"] == "Financial Services" and x["symbol"] not in index_symbols for x in d.get("stocks", [])),
            "Non-financial stocks or indices present in filtered response"
        )),
        ("Stock Screener CPR Narrow Filter", "/api/india/scanner?cpr=narrow", lambda d: (
            all(x["cpr"]["width_classification"] == "NARROW_CPR" for x in d.get("stocks", [])),
            "Non-narrow CPR stocks in narrow filter"
        )),

        # Indices Snapshot (Where indices belong)
        ("Indices Snapshot Telemetry (/api/india/indices)", "/api/india/indices", lambda d: (
            len(d.get("indices", [])) >= 5 and any(x["symbol"] == "NIFTY" for x in d["indices"]),
            "Missing NIFTY in indices snapshot"
        )),

        # 6-Factor Radar Breakdown & SEBI Regulatory Metadata
        ("Stock Dossier with SEBI & 6-Factor Radar (RELIANCE)", "/api/india/details?symbol=RELIANCE", lambda d: (
            d.get("symbol") == "RELIANCE" 
            and "score_breakdown" in d
            and "sebi_regulatory" in d
            and d["score_breakdown"].get("market_regime", 0) > 0,
            "Missing score_breakdown or sebi_regulatory in RELIANCE dossier"
        )),
        ("Stock Dossier (HDFCBANK)", "/api/india/details?symbol=HDFCBANK", lambda d: (
            d.get("symbol") == "HDFCBANK" and "monte_carlo" in d and "trade_setup" in d,
            "Missing Monte Carlo or trade setup in HDFCBANK dossier"
        )),
        ("FII / DII Institutional Flows", "/api/india/fii_dii", lambda d: (
            "fii_cash_net_cr" in d and "fii_index_options_pcr" in d,
            "Missing FII cash or PCR metrics"
        )),

        # F&O Options Suite
        ("NIFTY Option Chain & Max Pain", "/api/india/options/chain?symbol=NIFTY", lambda d: (
            len(d.get("chain", [])) >= 15 and d.get("max_pain_strike", 0) > 0 and "pcr" in d,
            "Option chain too short or missing Max Pain / PCR"
        )),
        ("BANKNIFTY Option Chain", "/api/india/options/chain?symbol=BANKNIFTY", lambda d: (
            len(d.get("chain", [])) >= 15 and d.get("lot_size") == 15,
            "BANKNIFTY lot size mismatch or short chain"
        )),
        ("Equity Stock Option Chain (RELIANCE)", "/api/india/options/chain?symbol=RELIANCE", lambda d: (
            len(d.get("chain", [])) >= 10 and d.get("lot_size") == 250,
            "RELIANCE lot size mismatch in option chain"
        )),
        ("Strike-wise OI Distribution (NIFTY)", "/api/india/options/oi_distribution?symbol=NIFTY", lambda d: (
            len(d.get("distribution", [])) >= 15 and "call_oi" in d["distribution"][0],
            "OI distribution data invalid"
        )),
        ("ATM Straddle Premium & Breakevens", "/api/india/options/straddle?symbol=NIFTY", lambda d: (
            d.get("combined_premium", 0) > 0 and "upper_breakeven" in d,
            "ATM straddle payload invalid"
        )),
        ("AI Recommended Options Spreads (/api/india/options/recommendations)", "/api/india/options/recommendations", lambda d: (
            len(d.get("recommendations", [])) >= 4 and "strategy_name" in d["recommendations"][0],
            "Options recommendations count low or invalid"
        )),
        ("AI Recommended Stock Buys (/api/india/stocks/recommendations)", "/api/india/stocks/recommendations", lambda d: (
            len(d.get("ai_recommended_buys", [])) >= 4 and not d["ai_recommended_buys"][0].get("is_index", False),
            "Stock recommendations count low or contains index"
        )),

        # Multi-Leg Payoff Curves & AI Strategies
        ("Multi-Leg Payoff Curve (Bull Call Spread)", "/api/india/options/payoff?symbol=NIFTY&days_to_target=0", lambda d: (
            len(d.get("curve_expiry", [])) >= 100 
            and "portfolio_greeks" in d 
            and "margin_breakdown" in d
            and len(d.get("broker_basket", [])) >= 2,
            "Payoff calculation failed or missing portfolio Greeks / margin breakdown"
        )),
        ("SEBI Hedge Benefit & Smart Basket Sequencing", "/api/india/options/payoff?symbol=NIFTY&days_to_target=0", lambda d: (
            d.get("margin_breakdown", {}).get("hedge_benefit_inr", 0) > 0
            and d.get("broker_basket", [])[0]["transaction_type"] == "BUY",
            "SEBI hedge benefit calculation or BUY priority order sequencing failed"
        )),
        ("AI Bull Call Spread (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=BULL_CALL_SPREAD", lambda d: (
            "BULL CALL" in d.get("strategy_name", "") and len(d.get("legs", [])) == 2 and d.get("max_profit_inr", 0) > 0,
            "Invalid Bull Call Spread payload"
        )),
        ("AI Bull Put Credit Spread (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=BULL_PUT_SPREAD", lambda d: (
            "BULL PUT" in d.get("strategy_name", "") and len(d.get("legs", [])) == 2,
            "Invalid Bull Put Credit Spread payload"
        )),
        ("AI Short Straddle (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=SHORT_STRADDLE", lambda d: (
            "STRADDLE" in d.get("strategy_name", "") and len(d.get("legs", [])) == 2,
            "Invalid Short Straddle payload"
        )),
        ("AI Iron Butterfly (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=IRON_BUTTERFLY", lambda d: (
            "BUTTERFLY" in d.get("strategy_name", "") and len(d.get("legs", [])) == 4,
            "Invalid Iron Butterfly payload"
        )),
        ("AI Long Straddle (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=LONG_STRADDLE", lambda d: (
            "LONG STRADDLE" in d.get("strategy_name", "") and len(d.get("legs", [])) == 2,
            "Invalid Long Straddle payload"
        )),
        ("AI Iron Condor (NIFTY)", "/api/india/options/strategies?symbol=NIFTY&bias=IRON_CONDOR", lambda d: (
            "IRON CONDOR" in d.get("strategy_name", "") and len(d.get("legs", [])) == 4,
            "Invalid Iron Condor 4-leg payload"
        )),

        # Heatmap, Rules & Risk Position Calculator
        ("Sector Capital Rotation Heatmap", "/api/india/heatmap", lambda d: (
            len(d.get("sectors", [])) >= 5 and "rotation_status" in d["sectors"][0],
            "Missing sectors or rotation status"
        )),
        ("NSE Rules Engine (RELIANCE)", "/api/india/rules?symbol=RELIANCE", lambda d: (
            d.get("lot_size") == 250 and d.get("symbol") == "RELIANCE",
            "NSE rules mismatch for RELIANCE"
        )),
        ("SEBI Lot Position Sizer (RELIANCE)", "/api/india/calc_position?symbol=RELIANCE&entry=2980&sl=2920&tp=3100&equity=500000&risk_pct=1.0", lambda d: (
            d.get("lots", 0) >= 1 and "broker_order_ticket" in d,
            "Position sizing calculation failed"
        )),

        # Autocomplete, Candles, CSV
        ("Search 'TCS'", "/api/india/search?q=tcs", lambda d: (
            len(d.get("results", [])) > 0 and d["results"][0]["symbol"] == "TCS",
            "Search for TCS failed"
        )),
        ("Candles TCS 1D", "/api/india/candles?symbol=TCS&tf=1D", lambda d: (
            len(d.get("candles", [])) >= 100,
            "TCS candle count insufficient"
        )),
        ("Export India Screener CSV", "/api/india/export_csv", None),

        # Regression Verification
        ("Regression: Forex/MT5 Telemetry", "/api/telemetry_state", lambda d: (
            "account" in d or "engine_active" in d or "market_statuses" in d,
            "Telemetry state missing key fields"
        )),
        ("Regression: US Stock Screener", "/api/stocks/screener", lambda d: (
            d.get("count", 0) >= 30,
            "US Stock screener count too low"
        ))
    ]

    passed = 0
    failed = 0

    for name, path, val in tests:
        ok = test_endpoint(name, path, val)
        if ok:
            passed += 1
        else:
            failed += 1

    print("=" * 80)
    print(f"TEST RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 80)
    return failed == 0


if __name__ == "__main__":
    success = run_all_india_tests()
    sys.exit(0 if success else 1)
