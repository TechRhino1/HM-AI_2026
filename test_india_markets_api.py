"""
Comprehensive Automated Test Suite for India Markets (NSE/BSE & F&O Intelligence Terminal)
Validates all endpoints, Option Chains, Greeks, Max Pain, PCR, AI Spreads, CPR Levels,
SEBI Margins, Lot Sizes, and ensures complete backward compatibility.
"""
import urllib.request
import urllib.error
import json
import sys


BASE_URL = "http://127.0.0.1:8501"


def test_endpoint(name: str, url_path: str, validator=None):
    url = f"{BASE_URL}{url_path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisIndiaTestRunner/1.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            status = res.status
            content_type = res.headers.get("Content-Type", "")
            raw_data = res.read()

            if status != 200:
                print(f"[FAIL] {name:<45} -> HTTP {status}")
                return False

            if "application/json" in content_type:
                data = json.loads(raw_data.decode("utf-8"))
                if validator:
                    val_res, val_msg = validator(data)
                    if not val_res:
                        print(f"[FAIL] {name:<45} -> JSON Validation Failed: {val_msg}")
                        return False
                print(f"[PASS] {name:<45} -> HTTP 200 OK | JSON Validated")
                return True
            elif "text/html" in content_type:
                html_str = raw_data.decode("utf-8")
                if "India Markets" in html_str and "NSE" in html_str:
                    print(f"[PASS] {name:<45} -> HTTP 200 OK | HTML Rendered ({len(raw_data)} bytes)")
                    return True
                else:
                    print(f"[FAIL] {name:<45} -> HTML missing key elements")
                    return False
            elif "text/csv" in content_type:
                csv_str = raw_data.decode("utf-8")
                if "Symbol" in csv_str and "CPR" in csv_str:
                    print(f"[PASS] {name:<45} -> HTTP 200 OK | CSV Stream Validated ({len(raw_data)} bytes)")
                    return True
                else:
                    print(f"[FAIL] {name:<45} -> CSV missing header columns")
                    return False
            else:
                print(f"[PASS] {name:<45} -> HTTP 200 OK | Content-Type: {content_type}")
                return True

    except Exception as e:
        print(f"[FAIL] {name:<45} -> Exception: {e}")
        return False


def run_all_india_tests():
    print("=" * 70)
    print("RUNNING INSTITUTIONAL INDIA MARKETS (NSE/BSE & F&O) TEST SUITE")
    print("=" * 70)

    tests = [
        # UI Pages
        ("India Terminal UI /india", "/india", None),

        # Indices & FII/DII Telemetry
        ("Indices Snapshot Telemetry", "/api/india/indices", lambda d: (
            len(d.get("indices", [])) >= 5 and any(x["symbol"] == "NIFTY" for x in d["indices"]),
            "Missing NIFTY in indices snapshot"
        )),
        ("FII / DII Institutional Flows", "/api/india/fii_dii", lambda d: (
            "fii_cash_net_cr" in d and "fii_index_options_pcr" in d,
            "Missing FII cash or PCR metrics"
        )),

        # Market Scanner & Filters
        ("NSE/BSE Default Market Scanner", "/api/india/scanner", lambda d: (
            d.get("count", 0) >= 15 and len(d.get("ai_recommended_buys", [])) > 0,
            "Scanner count too low or missing AI buy now setups"
        )),
        ("Scanner Sector Filter (Banking)", "/api/india/scanner?sector=Financial+Services", lambda d: (
            all(x["sector"] == "Financial Services" for x in d.get("stocks", [])),
            "Non-banking stocks present in filtered response"
        )),
        ("Scanner CPR Filter (Narrow Breakout)", "/api/india/scanner?cpr=narrow", lambda d: (
            all(x["cpr"]["width_classification"] == "NARROW_CPR" for x in d.get("stocks", [])),
            "Non-narrow CPR stocks in narrow filter"
        )),

        # Stock & Index Dossier
        ("Stock Dossier (RELIANCE)", "/api/india/details?symbol=RELIANCE", lambda d: (
            d.get("symbol") == "RELIANCE" and "cpr" in d and "camarilla" in d and "vwap_structure" in d,
            "Missing CPR or Camarilla structure in RELIANCE dossier"
        )),
        ("Index Dossier (NIFTY 50)", "/api/india/details?symbol=NIFTY", lambda d: (
            d.get("symbol") == "NIFTY" and len(d.get("candles", [])) > 50,
            "Missing candles or symbol mismatch in NIFTY dossier"
        )),
        ("Stock Dossier (HDFCBANK)", "/api/india/details?symbol=HDFCBANK", lambda d: (
            d.get("symbol") == "HDFCBANK" and "monte_carlo" in d,
            "Missing Monte Carlo in HDFCBANK dossier"
        )),

        # Option Chain Analytics (CE/PE, Greeks, Max Pain, PCR)
        ("NIFTY Option Chain & Max Pain", "/api/india/option_chain?symbol=NIFTY", lambda d: (
            len(d.get("chain", [])) >= 15 and d.get("max_pain_strike", 0) > 0 and "pcr" in d,
            "Option chain too short or missing Max Pain / PCR"
        )),
        ("BANKNIFTY Option Chain", "/api/india/option_chain?symbol=BANKNIFTY", lambda d: (
            len(d.get("chain", [])) >= 15 and d.get("lot_size") == 15,
            "BANKNIFTY lot size mismatch or short chain"
        )),
        ("Equity Stock Option Chain (RELIANCE)", "/api/india/option_chain?symbol=RELIANCE", lambda d: (
            len(d.get("chain", [])) >= 10 and d.get("lot_size") == 250,
            "RELIANCE lot size mismatch in option chain"
        )),

        # AI Defined-Risk Strategy Builder
        ("AI Bull Call Spread (NIFTY)", "/api/india/options_ai?symbol=NIFTY&bias=BULLISH", lambda d: (
            d.get("strategy_name") == "BULL CALL VERTICAL SPREAD" and len(d.get("legs", [])) == 2 and d.get("max_profit_inr", 0) > 0,
            "Invalid Bull Call Spread payload"
        )),
        ("AI Bear Put Spread (BANKNIFTY)", "/api/india/options_ai?symbol=BANKNIFTY&bias=BEARISH", lambda d: (
            d.get("strategy_name") == "BEAR PUT VERTICAL SPREAD" and len(d.get("legs", [])) == 2,
            "Invalid Bear Put Spread payload"
        )),
        ("AI Iron Condor (NIFTY)", "/api/india/options_ai?symbol=NIFTY&bias=NEUTRAL", lambda d: (
            d.get("strategy_name") == "DEFINED-RISK IRON CONDOR" and len(d.get("legs", [])) == 4,
            "Invalid Iron Condor 4-leg payload"
        )),

        # Sector Heatmap, Rules & Position Sizing
        ("Sector Capital Rotation Heatmap", "/api/india/heatmap", lambda d: (
            len(d.get("sectors", [])) >= 5 and "rotation_status" in d["sectors"][0],
            "Missing sectors or rotation status"
        )),
        ("NSE Dynamic Contract Rules (NIFTY)", "/api/india/rules?symbol=NIFTY", lambda d: (
            d.get("lot_size") == 25 and d.get("freeze_limit") == 1800 and d.get("strike_step") == 50.0,
            "NSE rules mismatch for NIFTY"
        )),
        ("SEBI Lot Position Sizer (RELIANCE)", "/api/india/calc_position?symbol=RELIANCE&entry=2980&sl=2920&tp=3100&equity=500000&risk_pct=1.0", lambda d: (
            d.get("lots", 0) >= 1 and "broker_order_ticket" in d,
            "Position sizing calculation failed"
        )),

        # Search, Candles & CSV Export
        ("Search 'RELIANCE'", "/api/india/search?q=reliance", lambda d: (
            len(d.get("results", [])) > 0 and d["results"][0]["symbol"] == "RELIANCE",
            "Search for Reliance failed"
        )),
        ("Search 'ZOMATO'", "/api/india/search?q=zomato", lambda d: (
            len(d.get("results", [])) > 0 and d["results"][0]["symbol"] == "ZOMATO",
            "Search for Zomato failed"
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

    print("=" * 70)
    print(f"TEST RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = run_all_india_tests()
    sys.exit(0 if success else 1)
