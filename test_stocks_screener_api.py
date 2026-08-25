"""
Automated Test Suite for AI Breakout Stock Screener & Stock Intelligence Module.
Verifies all REST API endpoints, filtering, search, multi-timeframe analytics, and trade setups.
"""
import urllib.request
import json
import time

def run_tests():
    base_url = "http://127.0.0.1:8501"
    
    tests = [
        # 1. UI Page
        {"name": "UI Page /stocks", "url": f"{base_url}/stocks", "is_json": False},
        
        # 2. Screener API Default & AI Recommended Buys
        {"name": "Screener Default & AI Recommended Buys", "url": f"{base_url}/api/stocks/screener", "is_json": True, "check": lambda d: d.get("count", 0) > 20 and len(d.get("ai_recommended_buys", [])) > 0},
        {"name": "Recommended Buys Endpoint", "url": f"{base_url}/api/stocks/recommended_buys", "is_json": True, "check": lambda d: len(d.get("recommended_buys", [])) > 0 and "entry_zone" in d["recommended_buys"][0]},
        
        # 3. Screener Filtered by Sector & Min Prob
        {"name": "Screener Tech Filter (>70% prob)", "url": f"{base_url}/api/stocks/screener?sector=Technology&min_prob=70", "is_json": True, "check": lambda d: len(d.get("stocks", [])) > 0},
        
        # 4. Screener Filtered by Horizon (Upcoming vs In Week)
        {"name": "Screener Upcoming Breakouts Filter", "url": f"{base_url}/api/stocks/screener?type=upcoming", "is_json": True, "check": lambda d: len(d.get("stocks", [])) > 0 and "timing_horizon" in d["stocks"][0]},
        {"name": "Screener Breakouts In Week (Weekly TF)", "url": f"{base_url}/api/stocks/screener?type=weekly&tf=1W", "is_json": True, "check": lambda d: len(d.get("stocks", [])) > 0},
        {"name": "Screener Squeeze Filter", "url": f"{base_url}/api/stocks/screener?type=squeeze", "is_json": True, "check": lambda d: isinstance(d.get("stocks"), list)},
        
        # 5. Search Autocomplete
        {"name": "Search 'NVDA'", "url": f"{base_url}/api/stocks/search?q=NVDA", "is_json": True, "check": lambda d: any(r.get("symbol") == "NVDA" for r in d.get("results", []))},
        {"name": "Search 'Apple'", "url": f"{base_url}/api/stocks/search?q=apple", "is_json": True, "check": lambda d: any(r.get("symbol") == "AAPL" for r in d.get("results", []))},
        {"name": "Search 'nio' (lowercase)", "url": f"{base_url}/api/stocks/search?q=nio", "is_json": True, "check": lambda d: any(r.get("symbol") == "NIO" for r in d.get("results", []))},
        {"name": "Search 'NIO' (uppercase)", "url": f"{base_url}/api/stocks/search?q=NIO", "is_json": True, "check": lambda d: any(r.get("symbol") == "NIO" for r in d.get("results", []))},
        
        # 6. Stock Details Dossier
        {"name": "Details NVDA (Order Flow & Monte Carlo)", "url": f"{base_url}/api/stocks/details?symbol=NVDA&tf=1D", "is_json": True, "check": lambda d: d.get("breakout_probability", 0) > 0 and "order_flow" in d and "monte_carlo" in d and "setup_grade" in d},
        {"name": "Details NIO (Order Flow & Monte Carlo)", "url": f"{base_url}/api/stocks/details?symbol=NIO&tf=1D", "is_json": True, "check": lambda d: d.get("symbol") == "NIO" and "order_flow" in d and "monte_carlo" in d},
        {"name": "Details TSLA", "url": f"{base_url}/api/stocks/details?symbol=TSLA&tf=1H", "is_json": True, "check": lambda d: "support_resistance" in d and "news" in d},
        
        # 7. Stock News Sentiment
        {"name": "News NVDA", "url": f"{base_url}/api/stocks/news?symbol=NVDA", "is_json": True, "check": lambda d: len(d.get("news", [])) > 0 and "sentiment" in d["news"][0]},
        {"name": "News NIO", "url": f"{base_url}/api/stocks/news?symbol=NIO", "is_json": True, "check": lambda d: len(d.get("news", [])) > 0 and any(n.get("symbol") == "NIO" for n in d["news"])},
        
        # 8. Breakout Alerts
        {"name": "Breakout Alerts", "url": f"{base_url}/api/stocks/alerts", "is_json": True, "check": lambda d: d.get("count", 0) > 0},
        
        # 9. Stock Candles
        {"name": "Candles NVDA 1D", "url": f"{base_url}/api/stocks/candles?symbol=NVDA&tf=1D", "is_json": True, "check": lambda d: len(d.get("candles", [])) == 120},
        
        # 10. Sector Heatmap
        {"name": "Sector Capital Rotation Heatmap", "url": f"{base_url}/api/stocks/heatmap", "is_json": True, "check": lambda d: len(d.get("sectors", [])) > 0 and "rotation_status" in d["sectors"][0]},
        
        # 11. Position Size & Risk Calculator
        {"name": "Position Sizing Calculator", "url": f"{base_url}/api/stocks/calc_position?equity=10000&risk_pct=1.0&entry=128.80&sl=124.50&tp=139.80", "is_json": True, "check": lambda d: d.get("shares", 0) > 0 and "broker_order_text" in d},
        
        # 12. Head-to-Head 2-Stock Comparison
        {"name": "Head-to-Head Compare NVDA vs AMD", "url": f"{base_url}/api/stocks/compare?sym1=NVDA&sym2=AMD", "is_json": True, "check": lambda d: "ai_winner" in d and "stock_a" in d and "stock_b" in d},
        
        # 13. Export CSV Endpoint
        {"name": "Export Screener CSV", "url": f"{base_url}/api/stocks/export_csv", "is_json": False, "check": lambda c: "Symbol,Company,Sector" in c},

        # 14. Existing Forex/Crypto Endpoints (Zero Regression Check)
        {"name": "Existing /api/telemetry_state", "url": f"{base_url}/api/telemetry_state", "is_json": True, "check": lambda d: "execution_mode" in d and "account" in d},
        {"name": "Existing /api/candles", "url": f"{base_url}/api/candles?symbol=XAUUSD&tf=H1", "is_json": True, "check": lambda d: len(d.get("candles", [])) > 0},
    ]

    print("=" * 70)
    print("RUNNING AI BREAKOUT STOCK SCREENER & INTELLIGENCE TEST SUITE")
    print("=" * 70)
    
    passed = 0
    failed = 0

    for t in tests:
        try:
            req = urllib.request.Request(t["url"], headers={"User-Agent": "JarvisStockTestRunner"})
            with urllib.request.urlopen(req, timeout=5.0) as res:
                status = res.status
                if status != 200:
                    print(f"[FAIL] {t['name']:<40} -> HTTP Status {status}")
                    failed += 1
                    continue
                
                content = res.read().decode("utf-8")
                if t.get("is_json", True):
                    data = json.loads(content)
                    if "check" in t:
                        if t["check"](data):
                            print(f"[PASS] {t['name']:<40} -> HTTP 200 OK | Validation Succeeded")
                            passed += 1
                        else:
                            print(f"[FAIL] {t['name']:<40} -> HTTP 200 OK | Validation Check FAILED on data: {list(data.keys()) if isinstance(data, dict) else len(data)}")
                            failed += 1
                    else:
                        print(f"[PASS] {t['name']:<40} -> HTTP 200 OK | JSON Valid")
                        passed += 1
                else:
                    if "check" in t:
                        if t["check"](content):
                            print(f"[PASS] {t['name']:<40} -> HTTP 200 OK | Text/CSV Content Validated ({len(content)} bytes)")
                            passed += 1
                        else:
                            print(f"[FAIL] {t['name']:<40} -> Validation Check Failed on Content")
                            failed += 1
                    elif "<html" in content.lower():
                        print(f"[PASS] {t['name']:<40} -> HTTP 200 OK | HTML Rendered ({len(content)} bytes)")
                        passed += 1
                    else:
                        print(f"[FAIL] {t['name']:<40} -> Unexpected Response Content")
                        failed += 1
        except Exception as ex:
            print(f"[FAIL] {t['name']:<40} -> Exception: {ex}")
            failed += 1

    print("=" * 70)
    print(f"TEST RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 70)
    return failed == 0

if __name__ == "__main__":
    run_tests()
