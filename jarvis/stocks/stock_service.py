"""
JARVIS AI 3.0 — AI Stock Screener & Intelligence Service
Unified service orchestrating stock universe scans, filtering, search indexing,
breakout probability ranking, and REST API dispatching.
"""
import time
import json
import logging
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
        self._scan_cache_ttl = 4.0
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
        # Refresh universe scan cache every TTL interval
        if (now - self._last_full_scan_time) > self._scan_cache_ttl or not self._cached_screener_results:
            results = []
            symbols = get_all_symbols()
            
            for sym in symbols:
                try:
                    analysis = STOCK_ENGINE.analyze_stock(sym, timeframe=timeframe)
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
                        "trend_bias": analysis["trend_bias"],
                        "squeeze_status": analysis["squeeze_status"],
                        "is_squeeze": analysis["is_squeeze"],
                        "recommendation": analysis["recommendation"],
                        "risk_level": analysis["risk_level"],
                        "entry_zone": analysis["trade_setup"]["entry_zone"],
                        "stop_loss": analysis["trade_setup"]["stop_loss"],
                        "take_profit_2": analysis["trade_setup"]["take_profit_2"],
                        "risk_reward": analysis["trade_setup"]["risk_reward_ratio"],
                        "rsi": analysis["technicals"]["rsi_14"],
                        "tags": analysis["tags"]
                    }
                    results.append(row)
                except Exception as ex:
                    logger.error(f"Error analyzing stock {sym}: {ex}", exc_info=False)

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

        # 4. Breakout Type Filter
        if breakout_type and breakout_type.lower() != "all":
            bt = breakout_type.lower()
            if bt == "squeeze":
                filtered = [s for s in filtered if s["is_squeeze"] or "SQUEEZE" in s["squeeze_status"]]
            elif bt == "vol_surge":
                filtered = [s for s in filtered if s["rvol"] >= 1.5]
            elif bt == "fired_breakout":
                filtered = [s for s in filtered if "FIRED" in s["squeeze_status"] or "BREAKOUT" in s["recommendation"]]

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
            "stocks": filtered[:limit],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

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
        for sym, prof in STOCK_UNIVERSE.items():
            if q == sym or sym.startswith(q) or q in sym or q in prof["name"].upper():
                matches.append({
                    "symbol": sym,
                    "name": prof["name"],
                    "sector": prof["sector"],
                    "market_cap": prof["market_cap"]
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
