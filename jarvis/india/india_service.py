"""
JARVIS AI 3.0 — India Markets REST Dispatcher & Service Coordinator
Provides unified JSON API endpoints for Indian Market Scanning, Option Chain Analytics,
Greeks, FII/DII Institutional Flows, CPR/Camarilla Pivots, and NSE/SEBI Rule Validation.
"""
import json
import csv
import io
import time
import concurrent.futures
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from jarvis.india.universe import (
    INDIA_UNIVERSE,
    get_all_india_symbols,
    get_all_india_stocks,
    get_india_profile,
    get_india_indices
)
from jarvis.india.india_engine import INDIA_ENGINE
from jarvis.india.options_engine import INDIA_OPTIONS
from jarvis.india.options_signal_engine import OPTION_SIGNALS
from jarvis.india.nse_rules import NSE_RULES
from jarvis.india.news_analyzer import INDIA_NEWS
from jarvis.india.risk_engine import INDIA_RISK

logger = logging.getLogger("jarvis.india_service")


class IndiaMarketsService:
    """
    Central API Service for India Markets (NSE/BSE & F&O).
    Provides high-speed parallel scanning and 15-second TTL in-memory caching.
    """

    def __init__(self):
        self._cached_scanner_results: Dict[str, Any] = {}
        self._last_full_scan_time: float = 0.0
        self._scan_cache_ttl: float = 15.0
        self._master_scan_cache: Dict[str, Dict[str, Any]] = {}

        self._cached_indices_snapshot: Optional[List[Dict[str, Any]]] = None
        self._last_indices_scan_time: float = 0.0
        self._indices_cache_ttl: float = 15.0

    def get_indices_snapshot(self) -> List[Dict[str, Any]]:
        """
        Returns live telemetry summary for major Indian Benchmark & Sectoral indices with 15s caching and parallel execution.
        """
        now = time.time()
        if self._cached_indices_snapshot is not None and (now - self._last_indices_scan_time) < self._indices_cache_ttl:
            return self._cached_indices_snapshot

        indices_syms = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYIT", "NIFTYAUTO"]
        results_map: Dict[str, Dict[str, Any]] = {}

        try:
            from jarvis.data.tradingview_provider import TRADINGVIEW_PROVIDER
            TRADINGVIEW_PROVIDER.fetch_quotes(indices_syms)
        except Exception:
            pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_sym = {
                executor.submit(INDIA_ENGINE.analyze_india_instrument, sym, "1D"): sym
                for sym in indices_syms
            }
            for future in concurrent.futures.as_completed(future_to_sym):
                sym = future_to_sym[future]
                try:
                    results_map[sym] = future.result()
                except Exception as exc:
                    logger.debug("Failed analyzing index %s: %s", sym, exc)

        res = []
        for sym in indices_syms:
            data = results_map.get(sym) or INDIA_ENGINE.analyze_india_instrument(sym, timeframe="1D")
            res.append({
                "symbol": data["symbol"],
                "name": data["name"],
                "price": data["current_price"],
                "change_pct": data["change_pct"],
                "change_val": data["change_val"],
                "cpr_classification": data["cpr"]["width_classification"],
                "cpr_label": data["cpr"]["width_label"],
                "camarilla_h4": data["camarilla"]["h4_breakout"],
                "camarilla_l4": data["camarilla"]["l4_breakdown"],
                "vwap": data["vwap_structure"]["vwap"],
                "bias": data["multi_timeframe"]["1D"]["bias"]
            })

        self._cached_indices_snapshot = res
        self._last_indices_scan_time = now
        return res

    def _refresh_master_scan(self):
        """
        Refreshes master technical analysis across the Indian universe in parallel using 8 worker threads.
        """
        now = time.time()
        if self._master_scan_cache and (now - self._last_full_scan_time) < self._scan_cache_ttl:
            return

        symbols = get_all_india_symbols()
        try:
            from jarvis.data.tradingview_provider import TRADINGVIEW_PROVIDER
            TRADINGVIEW_PROVIDER.fetch_quotes(symbols)
        except Exception:
            pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_sym = {
                executor.submit(INDIA_ENGINE.analyze_india_instrument, sym, "1D"): sym
                for sym in symbols
            }
            for future in concurrent.futures.as_completed(future_to_sym):
                sym = future_to_sym[future]
                try:
                    self._master_scan_cache[sym] = future.result()
                except Exception as exc:
                    logger.debug("Failed scanning symbol %s: %s", sym, exc)

        self._last_full_scan_time = now
        self._cached_scanner_results.clear()

    def get_scanner_data(
        self,
        sector: str = "all",
        market: str = "all",
        cpr_type: str = "all",
        min_prob: float = 0.0,
        sort_by: str = "probability",
        sort_dir: str = "desc",
        include_indices: bool = False
    ) -> Dict[str, Any]:
        """
        Scans Indian universe instruments with 15-second TTL in-memory caching.
        Strictly scans individual corporate equities when include_indices=False.
        """
        cache_key = f"{sector}_{market}_{cpr_type}_{min_prob}_{sort_by}_{sort_dir}_{include_indices}"
        now = time.time()
        if (now - self._last_full_scan_time) < self._scan_cache_ttl and cache_key in self._cached_scanner_results:
            return self._cached_scanner_results[cache_key]

        self._refresh_master_scan()

        if include_indices:
            symbols = get_all_india_symbols()
        else:
            symbols = get_all_india_stocks()

        scanned_list = []

        for sym in symbols:
            analysis = self._master_scan_cache.get(sym)
            if not analysis:
                analysis = INDIA_ENGINE.analyze_india_instrument(sym, timeframe="1D")
                self._master_scan_cache[sym] = analysis

            # Strictly exclude indices unless explicitly requested
            if not include_indices and (analysis.get("is_index", False) or analysis.get("sector") == "Indices"):
                continue
            
            # Filter by sector
            if sector != "all" and analysis["sector"].lower() != sector.lower():
                continue

            # Filter by market (NSE_INDEX, NSE_EQUITY, BSE_INDEX)
            if market != "all" and analysis["market"].lower() != market.lower():
                continue

            # Filter by CPR type
            if cpr_type != "all":
                if cpr_type == "narrow" and analysis["cpr"]["width_classification"] != "NARROW_CPR":
                    continue
                elif cpr_type == "wide" and analysis["cpr"]["width_classification"] != "WIDE_CPR":
                    continue

            # Filter by min probability
            if analysis["breakout_probability"] < min_prob:
                continue

            scanned_list.append({
                "symbol": analysis["symbol"],
                "name": analysis["name"],
                "sector": analysis["sector"],
                "market": analysis["market"],
                "is_index": analysis.get("is_index", False),
                "price": analysis["current_price"],
                "change_pct": analysis["change_pct"],
                "change_val": analysis["change_val"],
                "breakout_probability": analysis["breakout_probability"],
                "setup_grade": analysis["setup_grade"],
                "grade_badge": analysis["grade_badge"],
                "opportunity_state": analysis["opportunity_state"],
                "recommendation": analysis["recommendation"],
                "rvol": analysis["rvol"],
                "is_squeeze": analysis["is_squeeze"],
                "squeeze_status": analysis["squeeze_status"],
                "lot_size": analysis["lot_size"],
                "notional_contract_value_inr": analysis.get("notional_contract_value_inr", round(analysis["current_price"] * analysis["lot_size"], 2)),
                "sebi_regulatory": analysis.get("sebi_regulatory", {}),
                "score_breakdown": analysis.get("score_breakdown", {}),
                "cpr": analysis["cpr"],
                "camarilla": analysis["camarilla"],
                "vwap": analysis["vwap_structure"]["vwap"],
                "vwap_dist_pct": analysis["vwap_structure"]["distance_from_vwap_pct"],
                "entry_zone": analysis["trade_setup"]["entry_zone"],
                "stop_loss": analysis["trade_setup"]["stop_loss"],
                "take_profit_2": analysis["trade_setup"]["take_profit_2"],
                "expected_gain_pct": analysis["trade_setup"]["expected_gain_pct"]
            })

        # Sorting
        rev = (sort_dir.lower() == "desc")
        if sort_by == "probability":
            scanned_list.sort(key=lambda x: x["breakout_probability"], reverse=rev)
        elif sort_by == "price":
            scanned_list.sort(key=lambda x: x["price"], reverse=rev)
        elif sort_by == "change_pct":
            scanned_list.sort(key=lambda x: x["change_pct"], reverse=rev)
        elif sort_by == "symbol":
            scanned_list.sort(key=lambda x: x["symbol"], reverse=not rev)

        # Curate Top 4 "AI Recommended: Buy Now" Opportunities (Strictly Non-Index Equities)
        ai_buys = self.get_ai_recommended_stock_buys(limit=4)

        result = {
            "count": len(scanned_list),
            "stocks": scanned_list,
            "ai_recommended_buys": ai_buys,
            "scanned_at": datetime.now(timezone.utc).isoformat()
        }
        self._cached_scanner_results[cache_key] = result
        return result

    def get_ai_recommended_stock_buys(self, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Extracts the highest-conviction 'BUY NOW' Indian corporate stock setups.
        Guaranteed to return top 4 prime setups with complete fallback.
        """
        self._refresh_master_scan()
        all_stocks = get_all_india_stocks()
        candidates = []

        for sym in all_stocks:
            data = self._master_scan_cache.get(sym) or INDIA_ENGINE.analyze_india_instrument(sym, timeframe="1D")
            if data.get("is_index", False) or data.get("sector") == "Indices":
                continue
            if data.get("sebi_regulatory", {}).get("is_fno_ban", False):
                continue

            candidates.append({
                "symbol": data["symbol"],
                "name": data["name"],
                "sector": data["sector"],
                "price": data["current_price"],
                "change_pct": data["change_pct"],
                "breakout_probability": data["breakout_probability"],
                "setup_grade": data["setup_grade"],
                "grade_badge": data["grade_badge"],
                "opportunity_state": data["opportunity_state"],
                "recommendation": data["recommendation"],
                "entry_zone": data["trade_setup"]["entry_zone"],
                "stop_loss": data["trade_setup"]["stop_loss"],
                "take_profit_2": data["trade_setup"]["take_profit_2"],
                "expected_gain_pct": data["trade_setup"]["expected_gain_pct"],
                "max_risk_pct": data["trade_setup"]["max_risk_pct"],
                "cpr": data["cpr"],
                "camarilla": data["camarilla"],
                "vwap": data["vwap_structure"]["vwap"],
                "lot_size": data["lot_size"]
            })

        # Sort by Breakout Probability descending
        candidates.sort(key=lambda x: x["breakout_probability"], reverse=True)
        return candidates[:limit]

    def get_sector_heatmap(self) -> Dict[str, Any]:
        """
        Aggregates Indian sectoral performance and smart money capital flows.
        """
        self._refresh_master_scan()
        sectors_map: Dict[str, List[Dict[str, Any]]] = {}
        for sym, prof in INDIA_UNIVERSE.items():
            if prof.get("sector") == "Indices":
                continue
            sec = prof.get("sector", "Diversified")
            if sec not in sectors_map:
                sectors_map[sec] = []
            
            data = self._master_scan_cache.get(sym) or INDIA_ENGINE.analyze_india_instrument(sym, timeframe="1D")
            sectors_map[sec].append(data)

        heatmap_list = []
        for sec, items in sectors_map.items():
            if not items:
                continue
            avg_chg = sum(x["change_pct"] for x in items) / len(items)
            sorted_items = sorted(items, key=lambda x: x["change_pct"], reverse=True)
            top_lead = sorted_items[0]

            if avg_chg >= 1.2:
                status = "LEADING_INFLOW"
            elif avg_chg >= 0.0:
                status = "ACCUMULATION"
            elif avg_chg >= -1.0:
                status = "ROTATION_NEUTRAL"
            else:
                status = "OUTFLOW_DEFENSIVE"

            heatmap_list.append({
                "sector": sec,
                "stock_count": len(items),
                "avg_change_pct": round(avg_chg, 2),
                "top_leader_symbol": top_lead["symbol"],
                "top_leader_change": top_lead["change_pct"],
                "rotation_status": status
            })

        heatmap_list.sort(key=lambda x: x["avg_change_pct"], reverse=True)
        return {"sectors": heatmap_list}

    def export_csv(self, sector: str = "all", market: str = "all") -> str:
        """
        Generates clean CSV output for all scanned Indian instruments.
        """
        res = self.get_scanner_data(sector=sector, market=market)
        stocks = res.get("stocks", [])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Symbol", "Name", "Sector", "Market", "Price (INR)", "Change %", "Breakout Prob %",
            "Grade", "Recommendation", "Opportunity State", "CPR Classification", "CPR Pivot",
            "Camarilla H4 Breakout", "VWAP (INR)", "Lot Size", "Entry Zone (INR)", "Stop Loss (INR)", "Target (INR)"
        ])

        for s in stocks:
            writer.writerow([
                s["symbol"],
                s["name"],
                s["sector"],
                s["market"],
                f"₹{s['price']:.2f}",
                f"{s['change_pct']:.2f}%",
                f"{s['breakout_probability']}%",
                s["setup_grade"],
                s["recommendation"],
                s["opportunity_state"],
                s["cpr"]["width_classification"],
                f"₹{s['cpr']['pivot']:.2f}",
                f"₹{s['camarilla']['h4_breakout']:.2f}",
                f"₹{s['vwap']:.2f}",
                s["lot_size"],
                f"₹{s['entry_zone']:.2f}",
                f"₹{s['stop_loss']:.2f}",
                f"₹{s['take_profit_2']:.2f}"
            ])

        return output.getvalue()

    def handle_request(self, path: str, query: Dict[str, List[str]], handler) -> bool:
        """
        HTTP Request router for all `/api/india/*` endpoints.
        """
        try:
            if path in ["/api/india/scanner", "/api/india/stocks"]:
                sector = query.get("sector", ["all"])[0]
                market = query.get("market", ["all"])[0]
                cpr_type = query.get("cpr", ["all"])[0]
                min_prob = float(query.get("min_prob", [0.0])[0])
                sort_by = query.get("sort_by", ["probability"])[0]
                sort_dir = query.get("sort_dir", ["desc"])[0]
                inc_idx = query.get("include_indices", ["0"])[0] in ["1", "true", "True"]

                res = self.get_scanner_data(
                    sector=sector,
                    market=market,
                    cpr_type=cpr_type,
                    min_prob=min_prob,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    include_indices=inc_idx
                )
                self._send_json(handler, res)
                return True

            elif path == "/api/india/indices":
                res = self.get_indices_snapshot()
                self._send_json(handler, {"indices": res})
                return True

            elif path == "/api/india/details":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                tf = query.get("tf", ["1D"])[0].upper().strip()
                analysis = INDIA_ENGINE.analyze_india_instrument(sym, timeframe=tf)
                analysis["news"] = INDIA_NEWS.get_stock_news(sym)
                analysis["rules"] = {
                    "lot_size": NSE_RULES.get_lot_size(sym),
                    "freeze_limit": NSE_RULES.get_freeze_limit(sym),
                    "strike_step": NSE_RULES.get_strike_step(sym, analysis["current_price"]),
                    "expiry_schedule": NSE_RULES.get_expiry_schedule(sym)
                }
                self._send_json(handler, analysis)
                return True

            elif path in ["/api/india/option_chain", "/api/india/options/chain"]:
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                exp = query.get("expiry", [None])[0]
                res = INDIA_OPTIONS.generate_option_chain(sym, expiry=exp)
                self._send_json(handler, res)
                return True

            elif path in ["/api/india/options_ai", "/api/india/options/strategies"]:
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                bias = query.get("bias", ["BULLISH"])[0].upper().strip()
                res = INDIA_OPTIONS.generate_ai_options_strategy(sym, bias=bias)
                self._send_json(handler, res)
                return True

            elif path == "/api/india/options/payoff":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                days_tgt = float(query.get("days_to_target", [0.0])[0])
                legs_raw = query.get("legs", [None])[0]
                legs = None
                if legs_raw:
                    try:
                        legs = json.loads(legs_raw)
                    except Exception:
                        pass
                res = INDIA_OPTIONS.calculate_multi_leg_payoff(sym, legs=legs, days_to_target=days_tgt)
                self._send_json(handler, res)
                return True

            elif path == "/api/india/options/oi_distribution":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                res = INDIA_OPTIONS.get_oi_distribution(sym)
                self._send_json(handler, res)
                return True

            elif path in ["/api/india/options/single_signals", "/api/india/options/signals"]:
                limit = int(query.get("limit", [8])[0])
                sigs = OPTION_SIGNALS.generate_single_option_signals(limit=limit)
                self._send_json(handler, {"signals": sigs, "count": len(sigs)})
                return True

            elif path == "/api/india/options/recommendations":
                res = INDIA_OPTIONS.get_ai_recommended_options_trades()
                self._send_json(handler, {"recommendations": res})
                return True

            elif path in ["/api/india/stocks/recommendations", "/api/india/recommended_buys"]:
                res = self.get_ai_recommended_stock_buys(limit=4)
                self._send_json(handler, {"ai_recommended_buys": res})
                return True

            elif path == "/api/india/options/straddle":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                chain = INDIA_OPTIONS.generate_option_chain(sym)
                self._send_json(handler, chain["atm_straddle"])
                return True

            elif path == "/api/india/fii_dii":
                res = INDIA_NEWS.get_fii_dii_flows()
                self._send_json(handler, res)
                return True

            elif path == "/api/india/heatmap":
                res = self.get_sector_heatmap()
                self._send_json(handler, res)
                return True

            elif path == "/api/india/rules":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                profile = get_india_profile(sym)
                rules = {
                    "symbol": sym,
                    "lot_size": NSE_RULES.get_lot_size(sym),
                    "freeze_limit": NSE_RULES.get_freeze_limit(sym),
                    "strike_step": NSE_RULES.get_strike_step(sym, profile.get("base_price", 1000.0)),
                    "expiry_schedule": NSE_RULES.get_expiry_schedule(sym)
                }
                self._send_json(handler, rules)
                return True

            elif path == "/api/india/calc_position":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                entry = float(query.get("entry", [1000.0])[0])
                sl = float(query.get("sl", [980.0])[0])
                tp = float(query.get("tp", [1050.0])[0])
                equity = float(query.get("equity", [500000.0])[0])
                risk_pct = float(query.get("risk_pct", [1.0])[0])
                itype = query.get("type", ["EQUITY_CASH"])[0]

                res = INDIA_RISK.calculate_position(
                    symbol=sym,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    account_equity_inr=equity,
                    risk_pct=risk_pct,
                    instrument_type=itype
                )
                self._send_json(handler, res)
                return True

            elif path == "/api/india/search":
                q = query.get("q", [""])[0].lower().strip()
                matches = []
                for sym, prof in INDIA_UNIVERSE.items():
                    if q in sym.lower() or q in prof.get("name", "").lower():
                        matches.append({
                            "symbol": sym,
                            "name": prof.get("name"),
                            "sector": prof.get("sector"),
                            "price": prof.get("base_price"),
                            "lot_size": prof.get("lot_size", 100)
                        })
                self._send_json(handler, {"results": matches[:10]})
                return True

            elif path == "/api/india/candles":
                sym = query.get("symbol", ["NIFTY"])[0].upper().strip()
                tf = query.get("tf", ["1D"])[0].upper().strip()
                candles = INDIA_ENGINE.generate_candles(sym, timeframe=tf)
                self._send_json(handler, {"symbol": sym, "timeframe": tf, "candles": candles})
                return True

            elif path == "/api/india/export_csv":
                sec = query.get("sector", ["all"])[0]
                mkt = query.get("market", ["all"])[0]
                csv_data = self.export_csv(sector=sec, market=mkt)
                
                handler.send_response(200)
                handler.send_header("Content-Type", "text/csv; charset=utf-8")
                handler.send_header("Content-Disposition", 'attachment; filename="NSE_India_AI_Breakouts.csv"')
                handler.send_header("Access-Control-Allow-Origin", "*")
                handler.end_headers()
                handler.wfile.write(csv_data.encode("utf-8"))
                return True

            return False

        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return True

    def _send_json(self, handler, data: Any):
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(json.dumps(data, indent=2).encode("utf-8"))


INDIA_SERVICE = IndiaMarketsService()
