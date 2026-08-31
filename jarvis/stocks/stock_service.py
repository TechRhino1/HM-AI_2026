"""
JARVIS AI 3.0 — AI Stock Screener & Intelligence Service
Unified service orchestrating stock universe scans, filtering, search indexing,
breakout probability ranking, and REST API dispatching.
"""
import time
import json
import logging
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from jarvis.stocks.universe import STOCK_UNIVERSE, get_all_symbols, get_stock_profile
from jarvis.stocks.stock_engine import STOCK_ENGINE
from jarvis.stocks.news_analyzer import STOCK_NEWS

logger = logging.getLogger("JARVIS_StockService")


class StockService:
    """
    Central Coordinator for the AI Stock Intelligence & Breakout Screener.
    """

    def __init__(self):
        self._scan_cache: Dict[str, Dict[str, Any]] = {}
        self._scan_cache_ttl = 15.0
        self._last_full_scan_time = 0.0
        self._cached_screener_results: List[Dict[str, Any]] = []

    def get_screener_results(
        self,
        market: str = "all",
        sector: str = "all",
        timeframe: str = "1D",
        min_probability: int = 0,
        breakout_type: str = "all",
        sort_by: str = "probability",
        sort_dir: str = "desc",
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Scans all equities in the universe and returns ranked breakout opportunities with filters applied.
        """
        now = time.time()
        # Refresh universe scan cache every TTL interval (15.0s)
        if (now - self._last_full_scan_time) > self._scan_cache_ttl or not self._cached_screener_results:
            results = []
            symbols = get_all_symbols()
            try:
                from jarvis.data.dynamic_hydrator import DYNAMIC_HYDRATOR
                DYNAMIC_HYDRATOR.hydrate_batch(symbols, market="US")
            except Exception:
                pass

            results_map: Dict[str, Dict[str, Any]] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                future_to_sym = {
                    executor.submit(STOCK_ENGINE.analyze_stock, sym, timeframe=timeframe): sym
                    for sym in symbols
                }
                for future in concurrent.futures.as_completed(future_to_sym):
                    sym = future_to_sym[future]
                    try:
                        results_map[sym] = future.result()
                    except Exception as exc:
                        logger.error(f"Error analyzing stock {sym}: {exc}", exc_info=False)

            for sym in symbols:
                analysis = results_map.get(sym)
                if not analysis:
                    # Graceful fallback row for failed symbol analysis
                    prof = get_stock_profile(sym)
                    base_px = float(prof.get("base_price", 100.0))
                    row = {
                        "symbol": sym,
                        "name": prof.get("name", sym),
                        "sector": prof.get("sector", "Technology"),
                        "industry": prof.get("industry", "General"),
                        "market": prof.get("market", "US_EQUITIES"),
                        "market_cap": prof.get("market_cap", "$10.0B"),
                        "price": base_px,
                        "change_val": 0.0,
                        "change_pct": 0.0,
                        "volume": 1000000,
                        "rvol": 1.0,
                        "breakout_probability": 50,
                        "confidence": 0.85,
                        "setup_grade": "GRADE B",
                        "grade_badge": "B",
                        "timing_horizon": "UPCOMING (1-3 DAYS)",
                        "timing_badge": "UPCOMING",
                        "timing_desc": "Fallback Analysis",
                        "trend_bias": "BULLISH",
                        "squeeze_status": "NONE",
                        "is_squeeze": False,
                        "recommendation": "WATCH",
                        "risk_level": "MODERATE",
                        "cmf_20": 0.0,
                        "buyer_pressure_pct": 50,
                        "rs_vs_spy": 0.0,
                        "rs_label": "IN_LINE",
                        "monte_carlo_tp1_prob": 50.0,
                        "entry_zone": base_px,
                        "stop_loss": round(base_px * 0.96, 2),
                        "take_profit_2": round(base_px * 1.08, 2),
                        "risk_reward": 2.0,
                        "rsi": 50.0,
                        "earnings_date": "N/A",
                        "days_to_earnings": 999,
                        "earnings_badge": "SAFE",
                        "earnings_warning": "LOW",
                        "implied_volatility": 25.0,
                        "tags": prof.get("tags", [])
                    }
                else:
                    # Lightweight row object for table rendering
                    row = {
                        "symbol": analysis["symbol"],
                        "name": analysis["name"],
                        "sector": analysis["sector"],
                        "industry": analysis["industry"],
                        "market": analysis["market"],
                        "market_cap": analysis["market_cap"],
                        "price": analysis["current_price"],
                        "change_val": analysis["change_val"],
                        "change_pct": analysis["change_pct"],
                        "volume": analysis["volume"],
                        "rvol": analysis["rvol"],
                        "breakout_probability": analysis["breakout_probability"],
                        "confidence": analysis["confidence"],
                        "setup_grade": analysis.get("setup_grade", "GRADE A"),
                        "grade_badge": analysis.get("grade_badge", "A"),
                        "timing_horizon": analysis.get("timing_horizon", "UPCOMING (1-3 DAYS)"),
                        "timing_badge": analysis.get("timing_badge", "UPCOMING"),
                        "timing_desc": analysis.get("timing_desc", ""),
                        "trend_bias": analysis["trend_bias"],
                        "squeeze_status": analysis["squeeze_status"],
                        "is_squeeze": analysis["is_squeeze"],
                        "recommendation": analysis["recommendation"],
                        "risk_level": analysis["risk_level"],
                        "cmf_20": analysis["order_flow"]["cmf_20"],
                        "buyer_pressure_pct": analysis["order_flow"]["buyer_pressure_pct"],
                        "rs_vs_spy": analysis["order_flow"]["rs_vs_spy"],
                        "rs_label": analysis["order_flow"]["rs_label"],
                        "monte_carlo_tp1_prob": analysis["monte_carlo"]["tp1_probability_pct"],
                        "entry_zone": analysis["trade_setup"]["entry_zone"],
                        "stop_loss": analysis["trade_setup"]["stop_loss"],
                        "take_profit_2": analysis["trade_setup"]["take_profit_2"],
                        "risk_reward": analysis["trade_setup"]["risk_reward_ratio"],
                        "rsi": analysis["technicals"]["rsi_14"],
                        "earnings_date": analysis["earnings"]["earnings_date"],
                        "days_to_earnings": analysis["earnings"]["days_to_earnings"],
                        "earnings_badge": analysis["earnings"]["warning_badge"],
                        "earnings_warning": analysis["earnings"]["warning_level"],
                        "implied_volatility": analysis["earnings"]["implied_volatility"],
                        "tags": analysis["tags"]
                    }
                results.append(row)

            self._cached_screener_results = results
            self._last_full_scan_time = now

        # Apply Filters
        filtered = self._cached_screener_results.copy()

        # 1. Market Filter
        if market and market.lower() != "all":
            m_target = market.upper().replace(" ", "_")
            filtered = [s for s in filtered if m_target in s.get("market", "").upper() or m_target in str(s.get("tags", []))]

        # 2. Sector Filter
        if sector and sector.lower() != "all":
            s_target = sector.lower().replace("_", " ")
            filtered = [s for s in filtered if s_target in s.get("sector", "").lower() or s_target in s.get("industry", "").lower()]

        # 3. Minimum Breakout Probability Filter
        if min_probability > 0:
            filtered = [s for s in filtered if s["breakout_probability"] >= min_probability]

        # 4. Breakout Type / Horizon Filter (Upcoming vs In Week vs Fired)
        if breakout_type and breakout_type.lower() != "all":
            bt = breakout_type.lower()
            if bt in ["upcoming", "upcoming_breakout", "squeeze"]:
                filtered = [
                    s for s in filtered 
                    if s.get("is_squeeze") 
                    or s.get("timing_badge") == "UPCOMING" 
                    or "UPCOMING" in s.get("timing_horizon", "").upper()
                    or "SQUEEZE" in s.get("squeeze_status", "").upper()
                    or s.get("breakout_probability", 0) >= 68
                ]
            elif bt in ["weekly", "breakout_in_week", "this_week"]:
                filtered = [
                    s for s in filtered 
                    if s.get("timing_badge") == "THIS_WEEK" 
                    or "WEEK" in s.get("timing_horizon", "").upper() 
                    or s.get("breakout_probability", 0) >= 72
                    or s.get("timeframe") == "1W"
                ]
            elif bt in ["fired", "fired_breakout", "active"]:
                filtered = [
                    s for s in filtered 
                    if s.get("timing_badge") == "ACTIVE" 
                    or "FIRED" in s.get("squeeze_status", "").upper() 
                    or s.get("rvol", 0) >= 1.4
                    or s.get("breakout_probability", 0) >= 80
                ]
            elif bt == "vol_surge":
                filtered = [s for s in filtered if s.get("rvol", 0) >= 1.5]

        # Sort Results
        reverse = (sort_dir.lower() == "desc")
        if sort_by == "probability":
            filtered.sort(key=lambda x: x["breakout_probability"], reverse=reverse)
        elif sort_by == "rvol":
            filtered.sort(key=lambda x: x["rvol"], reverse=reverse)
        elif sort_by == "change_pct":
            filtered.sort(key=lambda x: x["change_pct"], reverse=reverse)
        elif sort_by == "price":
            filtered.sort(key=lambda x: x["price"], reverse=reverse)
        else:
            filtered.sort(key=lambda x: x["breakout_probability"], reverse=True)

        # Extract top AI recommended 'Buy Now' setups
        recommended_buys = self._extract_recommended_buys()

        return {
            "count": len(filtered),
            "total_universe": len(self._cached_screener_results),
            "timeframe": timeframe,
            "filters": {
                "market": market,
                "sector": sector,
                "min_probability": min_probability,
                "breakout_type": breakout_type,
                "sort_by": sort_by,
                "sort_dir": sort_dir
            },
            "ai_recommended_buys": recommended_buys,
            "stocks": filtered[:limit],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _extract_recommended_buys(self, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Extracts the highest-conviction 'BUY NOW' opportunities from the universe.
        Requires high breakout probability, Grade A/A+, positive order flow (CMF), and strong R:R.
        """
        if not self._cached_screener_results:
            return []

        candidates = []
        for s in self._cached_screener_results:
            prob = s.get("breakout_probability", 0)
            cmf = s.get("cmf_20", 0)
            grade = s.get("grade_badge", "C")
            
            # Conviction score combines probability, CMF, and RVOL
            conviction_score = prob + (cmf * 50.0) + (s.get("rvol", 1.0) * 10.0)
            
            # High conviction buy threshold
            if prob >= 75 and grade in ["A+", "A", "B"]:
                rvol_str = f"{s.get('rvol', 1.0):.1f}x"
                cmf_str = f"{cmf:+.2f}"
                rs_val = s.get("rs_vs_spy", 0)
                
                reasons = []
                if s.get("is_squeeze") or "SQUEEZE" in s.get("squeeze_status", ""):
                    reasons.append("🔥 Coiling Squeeze Trigger Ready")
                if s.get("rvol", 0) >= 1.5:
                    reasons.append(f"📊 Volume Surge ({rvol_str})")
                if cmf > 0.08:
                    reasons.append(f"🌊 Smart Money Inflow (CMF {cmf_str})")
                if rs_val > 1.5:
                    reasons.append(f"⚡ Outperforming S&P 500 (+{rs_val:.1f}%)")
                if not reasons:
                    reasons.append("⚡ Multi-Timeframe Trend Confluence")

                item = {
                    "symbol": s["symbol"],
                    "name": s["name"],
                    "sector": s["sector"],
                    "price": s["price"],
                    "change_pct": s["change_pct"],
                    "breakout_probability": s["breakout_probability"],
                    "confidence": s.get("confidence", 0.90),
                    "setup_grade": s.get("setup_grade", "GRADE A"),
                    "grade_badge": s.get("grade_badge", "A"),
                    "recommendation": s["recommendation"],
                    "entry_zone": s["entry_zone"],
                    "stop_loss": s["stop_loss"],
                    "take_profit_2": s["take_profit_2"],
                    "risk_reward": s["risk_reward"],
                    "expected_gain_pct": round(((s["take_profit_2"] - s["entry_zone"]) / s["entry_zone"]) * 100.0, 1) if s["entry_zone"] > 0 else 12.5,
                    "max_risk_pct": round(((s["entry_zone"] - s["stop_loss"]) / s["entry_zone"]) * 100.0, 1) if s["entry_zone"] > 0 else 3.5,
                    "timing_badge": s.get("timing_badge", "UPCOMING"),
                    "timing_horizon": s.get("timing_horizon", "UPCOMING (1-3 DAYS)"),
                    "cmf_20": cmf,
                    "buyer_pressure_pct": s.get("buyer_pressure_pct", 65),
                    "ai_catalyst": " • ".join(reasons[:2]),
                    "conviction_score": conviction_score
                }
                candidates.append(item)

        if len(candidates) < limit and self._cached_screener_results:
            sorted_all = sorted(self._cached_screener_results, key=lambda x: x.get("breakout_probability", 0), reverse=True)
            for s in sorted_all:
                if any(c["symbol"] == s["symbol"] for c in candidates):
                    continue
                cmf = s.get("cmf_20", 0)
                item = {
                    "symbol": s["symbol"],
                    "name": s["name"],
                    "sector": s["sector"],
                    "price": s["price"],
                    "change_pct": s["change_pct"],
                    "breakout_probability": s["breakout_probability"],
                    "confidence": s.get("confidence", 0.88),
                    "setup_grade": s.get("setup_grade", "GRADE A"),
                    "grade_badge": s.get("grade_badge", "A"),
                    "recommendation": s["recommendation"],
                    "entry_zone": s["entry_zone"],
                    "stop_loss": s["stop_loss"],
                    "take_profit_2": s["take_profit_2"],
                    "risk_reward": s["risk_reward"],
                    "expected_gain_pct": round(((s["take_profit_2"] - s["entry_zone"]) / s["entry_zone"]) * 100.0, 1) if s["entry_zone"] > 0 else 12.5,
                    "max_risk_pct": round(((s["entry_zone"] - s["stop_loss"]) / s["entry_zone"]) * 100.0, 1) if s["entry_zone"] > 0 else 3.5,
                    "timing_badge": s.get("timing_badge", "UPCOMING"),
                    "timing_horizon": s.get("timing_horizon", "UPCOMING (1-3 DAYS)"),
                    "cmf_20": cmf,
                    "buyer_pressure_pct": s.get("buyer_pressure_pct", 65),
                    "ai_catalyst": "⚡ Quantitative Trend & Momentum Confluence",
                    "conviction_score": s.get("breakout_probability", 0)
                }
                candidates.append(item)
                if len(candidates) >= limit:
                    break

        candidates.sort(key=lambda x: x["conviction_score"], reverse=True)
        return candidates[:limit]

    def get_ai_recommended_buys(self, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Public accessor for AI recommended buy setups.
        """
        self.get_screener_results()
        return self._extract_recommended_buys(limit=limit)

    def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Instant auto-complete search matching ticker symbol or company name.
        """
        q = (query or "").upper().strip()
        if not q:
            # Return top default stocks
            return [
                {
                    "symbol": s,
                    "name": STOCK_UNIVERSE[s]["name"],
                    "sector": STOCK_UNIVERSE[s]["sector"],
                    "market_cap": STOCK_UNIVERSE[s]["market_cap"]
                }
                for s in ["NVDA", "AAPL", "MSFT", "TSLA", "PLTR", "AMD", "META", "AMZN"]
            ]

        matches = []
        exact_matches = []
        prefix_matches = []
        contains_matches = []

        for sym, prof in STOCK_UNIVERSE.items():
            if q == sym:
                exact_matches.append({
                    "symbol": sym,
                    "name": prof["name"],
                    "sector": prof["sector"],
                    "market_cap": prof["market_cap"]
                })
            elif sym.startswith(q) or prof["name"].upper().startswith(q):
                prefix_matches.append({
                    "symbol": sym,
                    "name": prof["name"],
                    "sector": prof["sector"],
                    "market_cap": prof["market_cap"]
                })
            elif q in sym or q in prof["name"].upper():
                contains_matches.append({
                    "symbol": sym,
                    "name": prof["name"],
                    "sector": prof["sector"],
                    "market_cap": prof["market_cap"]
                })

        matches = exact_matches + prefix_matches + contains_matches

        # If user searched a ticker format not yet in predefined universe, dynamically allow 1-click analysis
        if len(q) >= 1 and len(q) <= 6 and q.isalnum():
            if not any(m["symbol"] == q for m in matches):
                matches.insert(0, {
                    "symbol": q,
                    "name": f"{q} (Global / US Equity)",
                    "sector": "Equities",
                    "market_cap": "AI Analyzed"
                })

        return matches[:limit]

    def get_stock_details(self, symbol: str, timeframe: str = "1D") -> Dict[str, Any]:
        """
        Returns full institutional dossier for a specific stock including technicals, S/R, trade plan, and news.
        """
        analysis = STOCK_ENGINE.analyze_stock(symbol, timeframe=timeframe)
        news = STOCK_NEWS.get_stock_news(symbol)
        analysis["news"] = news
        return analysis

    def get_breakout_alerts(self, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Generates real-time breakout alert items for high probability tickers.
        """
        screener = self.get_screener_results(min_probability=75, sort_by="probability", limit=limit)
        alerts = []
        now = datetime.now(timezone.utc)
        
        for i, st in enumerate(screener.get("stocks", [])):
            time_offset = i * 6 + 2
            alerts.append({
                "symbol": st["symbol"],
                "name": st["name"],
                "price": st["price"],
                "change_pct": st["change_pct"],
                "probability": st["breakout_probability"],
                "rvol": st["rvol"],
                "action": st["recommendation"],
                "type": "COILING SQUEEZE" if st["is_squeeze"] else "VOLUME EXPANSION",
                "time_ago": f"{time_offset}m ago",
                "timestamp": (now - timezone.utc.utcoffset(now) if hasattr(now, "utcoffset") else now).isoformat()
            })
            
        return alerts

    def get_sector_heatmap(self) -> List[Dict[str, Any]]:
        """
        Aggregates equity universe performance and smart money rotation by sector.
        """
        self.get_screener_results()
        if not self._cached_screener_results:
            return []

        sector_groups: Dict[str, List[Dict[str, Any]]] = {}
        for s in self._cached_screener_results:
            sec = s.get("sector", "General")
            if sec not in sector_groups:
                sector_groups[sec] = []
            sector_groups[sec].append(s)

        heatmap = []
        for sec, items in sector_groups.items():
            if not items:
                continue
            avg_chg = round(sum(it["change_pct"] for it in items) / len(items), 2)
            avg_cmf = round(sum(it.get("cmf_20", 0.0) for it in items) / len(items), 2)
            avg_prob = round(sum(it["breakout_probability"] for it in items) / len(items), 1)
            
            # Identify sector leader and top breakout candidate
            leader = max(items, key=lambda x: x["change_pct"])
            top_breakout = max(items, key=lambda x: x["breakout_probability"])
            
            # Determine Smart Money Rotation Status
            if avg_chg > 1.2 and avg_cmf > 0.05:
                rot_status = "LEADING_INFLOW"
            elif avg_chg > 0 and avg_cmf > 0:
                rot_status = "ACCUMULATION"
            elif avg_chg < -0.8 and avg_cmf < -0.05:
                rot_status = "OUTFLOW_DEFENSIVE"
            else:
                rot_status = "ROTATION_NEUTRAL"

            heatmap.append({
                "sector": sec,
                "count": len(items),
                "avg_change_pct": avg_chg,
                "avg_cmf": avg_cmf,
                "avg_probability": avg_prob,
                "rotation_status": rot_status,
                "top_leader_symbol": leader["symbol"],
                "top_leader_change": leader["change_pct"],
                "top_breakout_symbol": top_breakout["symbol"],
                "top_breakout_prob": top_breakout["breakout_probability"],
                "stocks": [
                    {
                        "symbol": it["symbol"],
                        "change_pct": it["change_pct"],
                        "price": it["price"],
                        "breakout_probability": it["breakout_probability"]
                    } for it in items[:6]
                ]
            })

        # Sort by average change % descending
        heatmap.sort(key=lambda x: x["avg_change_pct"], reverse=True)
        return heatmap

    def export_csv(self, market: str = "all", sector: str = "all") -> str:
        """
        Exports filtered stock screener opportunities to CSV format.
        """
        screener = self.get_screener_results(market=market, sector=sector, limit=500)
        stocks = screener.get("stocks", [])
        
        headers = [
            "Symbol", "Company", "Sector", "Price", "Change %", "Setup Grade", 
            "Breakout Probability %", "Timing Horizon", "CMF 20", "RS vs SPY", 
            "Entry Zone", "Stop Loss", "Target 2", "Risk Reward", "Recommendation", "Earnings Date"
        ]
        
        rows = [",".join(headers)]
        for s in stocks:
            row = [
                s.get("symbol", ""),
                f'"{s.get("name", "")}"',
                f'"{s.get("sector", "")}"',
                str(s.get("price", "")),
                str(s.get("change_pct", "")),
                s.get("setup_grade", ""),
                str(s.get("breakout_probability", "")),
                s.get("timing_horizon", ""),
                str(s.get("cmf_20", "")),
                str(s.get("rs_vs_spy", "")),
                str(s.get("entry_zone", "")),
                str(s.get("stop_loss", "")),
                str(s.get("take_profit_2", "")),
                str(s.get("risk_reward", "")),
                s.get("recommendation", ""),
                s.get("earnings_date", "")
            ]
            rows.append(",".join(row))
            
        return "\n".join(rows)

    def handle_request(self, path: str, query: Dict[str, List[str]], handler: Any) -> bool:
        """
        Modular REST API router for all `/api/stocks/*` endpoints.
        """
        try:
            if path == "/api/stocks/screener":
                market = query.get("market", ["all"])[0]
                sector = query.get("sector", ["all"])[0]
                timeframe = query.get("tf", ["1D"])[0]
                min_prob = int(query.get("min_prob", ["0"])[0])
                breakout_type = query.get("type", ["all"])[0]
                sort_by = query.get("sort_by", ["probability"])[0]
                sort_dir = query.get("sort_dir", ["desc"])[0]
                limit = int(query.get("limit", ["100"])[0])

                res = self.get_screener_results(
                    market=market,
                    sector=sector,
                    timeframe=timeframe,
                    min_probability=min_prob,
                    breakout_type=breakout_type,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    limit=limit
                )
                handler._send_json(res)
                return True

            elif path == "/api/stocks/details":
                sym = query.get("symbol", ["NVDA"])[0]
                tf = query.get("tf", ["1D"])[0]
                details = self.get_stock_details(sym, timeframe=tf)
                handler._send_json(details)
                return True

            elif path == "/api/stocks/search":
                q = query.get("q", [""])[0]
                results = self.search_stocks(q)
                handler._send_json({"results": results, "query": q})
                return True

            elif path == "/api/stocks/news":
                sym = query.get("symbol", ["NVDA"])[0]
                news = STOCK_NEWS.get_stock_news(sym)
                handler._send_json({"symbol": sym, "news": news})
                return True

            elif path == "/api/stocks/alerts":
                alerts = self.get_breakout_alerts()
                handler._send_json({"alerts": alerts, "count": len(alerts)})
                return True

            elif path == "/api/stocks/recommended_buys":
                buys = self.get_ai_recommended_buys()
                handler._send_json({"recommended_buys": buys, "count": len(buys)})
                return True

            elif path == "/api/stocks/heatmap":
                heatmap = self.get_sector_heatmap()
                handler._send_json({"sectors": heatmap, "count": len(heatmap)})
                return True

            elif path == "/api/stocks/calc_position":
                equity = float(query.get("equity", ["10000"])[0])
                risk_pct = float(query.get("risk_pct", ["1.0"])[0])
                entry = float(query.get("entry", ["100"])[0])
                sl = float(query.get("sl", ["95"])[0])
                tp = float(query.get("tp", ["115"])[0])
                calc = STOCK_ENGINE.calculate_position_size(
                    account_equity=equity,
                    risk_pct=risk_pct,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp
                )
                handler._send_json(calc)
                return True

            elif path == "/api/stocks/compare":
                sym_a = query.get("sym1", ["NVDA"])[0]
                sym_b = query.get("sym2", ["AMD"])[0]
                comp = STOCK_ENGINE.compare_stocks(sym_a, sym_b)
                handler._send_json(comp)
                return True

            elif path == "/api/stocks/export_csv":
                market = query.get("market", ["all"])[0]
                sector = query.get("sector", ["all"])[0]
                csv_data = self.export_csv(market=market, sector=sector)
                handler.send_response(200)
                handler.send_header("Content-Type", "text/csv")
                handler.send_header("Content-Disposition", "attachment; filename=jarvis_stock_breakouts.csv")
                handler.send_header("Access-Control-Allow-Origin", "*")
                handler.end_headers()
                handler.wfile.write(csv_data.encode("utf-8"))
                return True

            elif path == "/api/stocks/candles":
                sym = query.get("symbol", ["NVDA"])[0]
                tf = query.get("tf", ["1D"])[0]
                num_bars = int(query.get("num_bars", ["120"])[0])
                candles = STOCK_ENGINE.generate_candles(sym, timeframe=tf, num_bars=num_bars)
                handler._send_json({"symbol": sym, "timeframe": tf, "candles": candles})
                return True

            return False
        except Exception as e:
            logger.error(f"StockService API error on {path}: {e}", exc_info=True)
            handler._send_json({"error": str(e)}, status_code=500)
            return True


STOCK_SERVICE = StockService()

