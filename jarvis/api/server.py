"""
JARVIS AI 3.0 — High-Performance Telemetry, Trading & Web Terminal Server.
Provides REST, JSON streaming, manual trading execution, position management, news feed, and static assets.
"""
import os
import json
import logging
import mimetypes
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from typing import Any, Optional, Dict

from jarvis.application.state_manager import StateManager, GLOBAL_STATE
import threading
import time
from jarvis.market.data_feed import DataFeedEngine
from jarvis.api.copilot import JarvisCopilot
from jarvis.execution.mt5_client import MT5Client
from jarvis.data.schemas import ExecutionMode
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.market.sessions import SessionEngine
from jarvis.api.remote_auth import RemoteAuthEngine

logger = logging.getLogger("JARVIS_WebServer")


class JarvisRequestHandler(BaseHTTPRequestHandler):
    state_manager: StateManager = GLOBAL_STATE
    mt5_client: MT5Client = MT5Client(mode="live")
    data_feed: DataFeedEngine = DataFeedEngine(mt5_client=mt5_client)
    copilot: JarvisCopilot = JarvisCopilot(GLOBAL_STATE)
    _bg_thread_started: bool = False
    _bg_lock = threading.Lock()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)

    def _extract_token(self) -> str:
        auth_header = self.headers.get("Authorization", "")
        cookie_header = self.headers.get("Cookie", "")
        token = ""

        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "jarvis_auth_token=" in cookie_header:
            try:
                for c in cookie_header.split(";"):
                    c = c.strip()
                    if c.startswith("jarvis_auth_token="):
                        token = c.split("=", 1)[1].strip()
                        break
            except Exception:
                pass

        return token

    def _get_auth_user(self) -> Optional[Dict[str, Any]]:
        token = self._extract_token()
        if not token:
            return None
        return RemoteAuthEngine.validate_token(token)

    def _check_auth(self) -> bool:
        return self._get_auth_user() is not None

    def _require_role(self, *allowed_roles: str):
        user = self._get_auth_user()
        if not user:
            self._send_json({"status": "UNAUTHORIZED", "error": "Authentication required"}, status_code=401)
            return False, None
        if user.get("role") not in allowed_roles:
            self._send_json({"status": "FORBIDDEN", "error": f"Role '{user.get('role')}' is not permitted to perform this action"}, status_code=403)
            return False, None
        return True, user


    @classmethod
    def start_background_syncer(cls):
        with cls._bg_lock:
            if cls._bg_thread_started:
                return
            cls._bg_thread_started = True

        def _bg_loop():
            from jarvis.market.market_context import MarketContextEngine
            from jarvis.intelligence.regime_engine import MarketRegimeClassifier
            from jarvis.analysts.parallel_runner import ParallelAnalystCluster
            from jarvis.intelligence.decision_engine import DecisionEngine

            symbols = ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "USDJPY"]
            ce = MarketContextEngine()
            rc = MarketRegimeClassifier()
            ac = ParallelAnalystCluster(parallel=False)
            de = DecisionEngine()

            while True:
                try:
                    # 1. Sync Account & Positions
                    acc = cls.mt5_client.get_account_snapshot()
                    pos = cls.mt5_client.get_open_positions()
                    cls.state_manager.sync_broker_state(acc, pos)

                    # If the main Orchestrator is actively running, let it drive the radar sweeps
                    if cls.state_manager.is_orchestrator_active():
                        time.sleep(2.0)
                        continue

                    # 2. Standalone Fallback: Sweep Multi-Asset Radar
                    radar_results = []
                    account = cls.state_manager.account or acc

                    trade_style = getattr(cls.state_manager, "trade_style", "SWING")
                    for sym in symbols:
                        try:
                            mtf = cls.data_feed.fetch_multi_timeframe(sym, trade_style=trade_style)
                            spec = resolve_symbol(sym)
                            ctx = ce.build_context(sym, mtf, current_spread_pips=spec.typical_spread_pips, max_allowed_spread_pips=spec.max_spread_pips, trade_style=trade_style)
                            cls.state_manager.update_market_context(sym, ctx)
                            regime = rc.classify_regime(ctx)
                            tentative_bias = "BUY" if ctx.structure.bias == "BULLISH" else ("SELL" if ctx.structure.bias == "BEARISH" else ("SELL" if getattr(ctx.momentum, "trend_score", 0.0) < 0 else "BUY"))
                            reports, devil = ac.run_all_parallel(ctx, regime, tentative_bias)
                            d = de.evaluate(ctx, regime, reports, devil, account_balance=account.equity, mtf_data=mtf)
                            cls.state_manager.record_decision(sym, d)

                            mkt_status = SessionEngine.get_market_trading_status(sym)
                            is_mkt_open = mkt_status.get("is_open", True)

                            win_p = d.probabilities.get(d.bias.lower(), d.model_confidence) if d.bias in ["BUY", "SELL"] else d.model_confidence
                            if not is_mkt_open:
                                status_label = "MARKET CLOSED"
                            elif d.decision == "EXECUTE":
                                status_label = f"{d.bias} READY"
                            elif d.decision == "WAIT" and d.bias in ["BUY", "SELL"]:
                                status_label = f"WAIT: {d.bias}"
                            elif d.decision == "NO_TRADE":
                                if not d.quality_gate.passed and any("Invalid" in r or "Devil" in r or "Adversarial" in r for r in d.quality_gate.failing_reasons):
                                    status_label = f"INVALID: {d.bias}" if d.bias in ["BUY", "SELL"] else "TRADE INVALIDATED"
                                elif d.bias in ["BUY", "SELL"]:
                                    status_label = f"NO TRADE: {d.bias}"
                                else:
                                    status_label = "NO SETUP"
                            elif d.bias in ["BUY", "SELL"]:
                                status_label = f"WAIT: {d.bias}"
                            else:
                                status_label = "NO SETUP"

                            radar_results.append({
                                "symbol": sym,
                                "trade_style": trade_style,
                                "timeframe": "D1/H4/H1" if trade_style == "SWING" else ("H1/M15/M5" if trade_style in ("DAY_TRADING", "INTRADAY", "DAY") else "H1/M5/M1"),
                                "bias": d.bias,
                                "action": status_label,
                                "status_label": status_label,
                                "decision": d.decision,
                                "score": round(win_p * 100.0, 0),
                                "win_prob": round(win_p * 100.0, 0),
                                "entry_price": d.entry_price,
                                "stop_loss": d.stop_loss,
                                "take_profit": d.take_profit,
                                "risk_reward_ratio": round(d.risk_reward_ratio, 2) if d.risk_reward_ratio else 2.50,
                                "ev": round(d.expected_value, 2) if d.expected_value else 0.0,
                                "regime": d.regime.primary_regime.value if d.regime else "UNKNOWN",
                                "strategy": d.strategy or "STRUCTURE",
                                "adversarial_penalty": round(d.adversarial_penalty, 1) if d.adversarial_penalty else 0.0,
                                "invalidation_levels": d.invalidation_levels or [],
                                "risk_factors": d.risk_factors or [],
                                "gate_passed": d.quality_gate.passed,
                                "failing_reasons": d.quality_gate.failing_reasons,
                                "checks": d.quality_gate.checks,
                                "mtf_alignment": ctx.mtf_alignment,
                                "mtf_confluence": ctx.mtf_confluence_score,
                                "waiting_reasons": getattr(d, "waiting_reasons", []),
                                "rejection_reasons": getattr(d, "rejection_reasons", [])
                            })
                        except Exception as e_sym:
                            logger.error(f"Radar sweep error for {sym}: {e_sym}", exc_info=True)

                    if radar_results:
                        def _radar_sort_key(item):
                            act = item.get("action", "")
                            is_open = 0 if "CLOSED" in act else 1
                            if "READY" in act:
                                conv = 3
                            elif "WAIT" in act:
                                conv = 2
                            elif "NO TRADE" in act or "INVALID" in act:
                                conv = 1
                            else:
                                conv = 0
                            prob = item.get("win_prob", 0) or item.get("score", 0) or 0
                            ev = item.get("ev", 0) or 0
                            return (is_open, conv, prob, ev)

                        radar_results.sort(key=_radar_sort_key, reverse=True)
                        cls.state_manager.update_radar(radar_results)

                except Exception as e:
                    logger.error(f"Background telemetry sync error: {e}", exc_info=True)

                time.sleep(3.0)

        t = threading.Thread(target=_bg_loop, daemon=True, name="web_bg_telemetry_syncer")
        t.start()

    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        JarvisRequestHandler.start_background_syncer()
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/" or path == "/index.html":
                self._serve_terminal_ui()
            elif path in ["/stocks", "/stocks.html", "/screener"]:
                self._serve_stocks_ui()
            elif path in ["/india", "/india.html", "/india/stocks", "/nse", "/bse"]:
                self._serve_india_ui()
            elif path in ["/options", "/options.html", "/india/options", "/india-options", "/fno"]:
                self._serve_options_ui()
            elif path.startswith("/static/"):
                self._serve_static_file(path)
            elif path.startswith("/api/stocks/"):
                from jarvis.stocks.stock_service import STOCK_SERVICE
                if not STOCK_SERVICE.handle_request(path, query, self):
                    self.send_error(404, f"Stock API {path} not found")
            elif path.startswith("/api/india/"):
                from jarvis.india.india_service import INDIA_SERVICE
                if not INDIA_SERVICE.handle_request(path, query, self):
                    self.send_error(404, f"India API {path} not found")
            elif path == "/api/telemetry_state":
                snap = self.state_manager.get_state_snapshot()
                if not snap.get("account"):
                    acc = self.mt5_client.get_account_snapshot()
                    pos = self.mt5_client.get_open_positions()
                    self.state_manager.sync_broker_state(acc, pos)
                    snap = self.state_manager.get_state_snapshot()
                
                from jarvis.market.sessions import SessionEngine
                sym = query.get("symbol", ["XAUUSD"])[0]
                snap["active_market_status"] = SessionEngine.get_market_trading_status(sym)
                snap["market_statuses"] = {
                    s: SessionEngine.get_market_trading_status(s)
                    for s in ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD"]
                }
                self._send_json(snap)
            elif path == "/api/market-status":
                from jarvis.market.sessions import SessionEngine
                sym = query.get("symbol", ["XAUUSD"])[0]
                status = SessionEngine.get_market_trading_status(sym)
                self._send_json(status)
            elif path == "/api/candles":
                sym = query.get("symbol", ["XAUUSD"])[0]
                tf = query.get("tf", ["H1"])[0]
                df = self.data_feed.fetch_rates(sym, timeframe=tf, num_bars=150, include_current_bar=True)
                spec = resolve_symbol(sym)
                digits = getattr(spec, "digits", 2 if "XAU" in sym or "BTC" in sym else 5)
                candles = []
                for _, r in df.iterrows():
                    # Ensure timestamp is UTC UNIX seconds
                    t_val = r["time"]
                    if hasattr(t_val, "tzinfo") and t_val.tzinfo is None:
                        t_val = t_val.tz_localize("UTC")
                    
                    candles.append({
                        "time": int(t_val.timestamp()) if hasattr(t_val, "timestamp") else int(t_val),
                        "open": round(float(r["open"]), digits),
                        "high": round(float(r["high"]), digits),
                        "low": round(float(r["low"]), digits),
                        "close": round(float(r["close"]), digits),
                        "volume": float(r["volume"])
                    })
                self._send_json({"symbol": sym, "timeframe": tf, "candles": candles})
            elif path == "/api/rates":
                sym = query.get("symbol", ["XAUUSD"])[0]
                tf = query.get("tf", query.get("timeframe", ["H1"]))[0]
                trade_style = query.get("trade_style", [None])[0]
                bars = int(query.get("num_bars", query.get("bars", [150]))[0])
                if trade_style:
                    mtf = self.data_feed.fetch_multi_timeframe(sym, trade_style=trade_style, num_bars=bars)
                    res = {}
                    for role, df in mtf.items():
                        res[role] = df.tail(bars).to_dict(orient="records")
                    self._send_json({"symbol": sym, "trade_style": trade_style, "rates": res})
                else:
                    df = self.data_feed.fetch_rates(sym, timeframe=tf, num_bars=bars, include_current_bar=True)
                    self._send_json({"symbol": sym, "timeframe": tf, "rates": df.to_dict(orient="records")})
            elif path == "/api/radar":
                style_filter = query.get("trade_style", [None])[0]
                opps = self.state_manager.radar_opportunities
                if style_filter and style_filter.upper() != "ALL":
                    opps = [o for o in opps if str(o.get("trade_style", "")).upper() == style_filter.upper()]
                self._send_json({"opportunities": opps})
            elif path == "/api/history":
                try:
                    from jarvis.data.database import TRADE_DB
                    trades = TRADE_DB.fetch_recent_trades(limit=15)
                    self._send_json(trades)
                except Exception as e:
                    self._send_json({"error": str(e)})
            elif path == "/api/news":
                # Real-Time Institutional Macro News & Economic Calendar
                from jarvis.market.news import GLOBAL_NEWS_ENGINE
                news_items = GLOBAL_NEWS_ENGINE.get_news_calendar()
                self._send_json({"news": news_items, "timestamp": datetime.now(timezone.utc).isoformat()})
            elif path in ["/api/auth/me", "/api/auth/verify"]:
                user = self._get_auth_user()
                if user:
                    self._send_json({"status": "AUTHENTICATED", "valid": True, "user": user})
                else:
                    self._send_json({"status": "UNAUTHORIZED", "valid": False, "error": "Not authenticated"}, status_code=401)
            elif path == "/api/stream/telemetry":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                cors_origin = os.environ.get("JARVIS_CORS_ORIGIN", "*")
                if cors_origin:
                    self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.end_headers()

                # Stream initial state snapshot
                snap = self.state_manager.get_state_snapshot()
                init_msg = f"event: telemetry\ndata: {json.dumps(snap, default=str)}\n\n"
                try:
                    self.wfile.write(init_msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    return

                # SSE Event Loop
                last_ver = self.state_manager.get_state_version()
                for _ in range(60): # 60 iterations (approx 1-2 mins before clean client reconnect)
                    time.sleep(1.0)
                    cur_ver = self.state_manager.get_state_version()
                    try:
                        if cur_ver != last_ver:
                            last_ver = cur_ver
                            cur_snap = self.state_manager.get_state_snapshot()
                            msg = f"event: telemetry\ndata: {json.dumps(cur_snap, default=str)}\n\n"
                            self.wfile.write(msg.encode("utf-8"))
                            self.wfile.flush()
                        else:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                    except Exception:
                        break
                return
            elif path == "/api/diagnostics":
                snap = self.state_manager.get_state_snapshot()
                self._send_json({
                    "status": "SAFE_MODE" if snap["safe_mode"] else "OPERATIONAL",
                    "services": snap["services"],
                    "account": snap["account"],
                    "timestamp": snap["timestamp"]
                })
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"Error handling GET {path}: {e}", exc_info=True)
            self._send_json({"error": str(e)}, status_code=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            if path == "/api/auth/login":
                username = data.get("username", "").strip()
                password = data.get("password", "").strip()
                client_ip = self.headers.get("X-Forwarded-For", self.client_address[0] if hasattr(self, "client_address") and self.client_address else "global")
                user_info, err_msg = RemoteAuthEngine.verify_credentials(username, password, client_ip=client_ip)
                if user_info:
                    session_info = RemoteAuthEngine.create_session_token(username)
                    self._send_json(session_info)
                else:
                    status_code = 429 if "locked" in (err_msg or "").lower() else 401
                    self._send_json({"status": "UNAUTHORIZED" if status_code == 401 else "LOCKED", "error": err_msg or "Invalid username or password"}, status_code=status_code)
                return
            elif path == "/api/auth/logout":
                token = self._extract_token()
                RemoteAuthEngine.revoke_token(token)
                self._send_json({"status": "LOGGED_OUT", "message": "Session terminated successfully"})
                return
            elif path == "/api/auth/verify":
                user = self._get_auth_user()
                if user:
                    self._send_json({"status": "AUTHENTICATED", "valid": True, "user": user})
                else:
                    self._send_json({"status": "UNAUTHORIZED", "valid": False, "error": "Invalid or expired session"}, status_code=401)
                return
            elif path == "/api/auth/change_password":
                user = self._get_auth_user()
                if not user:
                    self._send_json({"status": "UNAUTHORIZED", "error": "Authentication required"}, status_code=401)
                    return
                old_pwd = data.get("old_password", "")
                new_pwd = data.get("new_password", "")
                success, msg = RemoteAuthEngine.change_password(user["username"], old_pwd, new_pwd)
                if success:
                    self._send_json({"status": "SUCCESS", "message": msg})
                else:
                    self._send_json({"status": "FAILED", "error": msg}, status_code=400)
                return

            # Protected Action Endpoints — Require Authentication + appropriate role
            if path.startswith("/api/action/"):
                ok, _ = self._require_role("ADMIN", "TRADER")
                if not ok:
                    return
            elif path.startswith("/api/copilot/"):
                if not self._check_auth():
                    self._send_json({"status": "UNAUTHORIZED", "error": "Authentication required"}, status_code=401)
                    return

            if path == "/api/copilot/ask":
                query = data.get("query", "")
                response_text = self.copilot.ask(query)
                self._send_json({"query": query, "response": response_text})
            elif path == "/api/action/toggle_safe_mode":
                is_safe = self.state_manager.toggle_safe_mode()
                self._send_json({"safe_mode": is_safe})
            elif path == "/api/action/set_trade_style":
                style = data.get("trade_style", "SWING").upper()
                self.state_manager.set_trade_style(style)
                if hasattr(self, "orchestrator") and self.orchestrator:
                    self.orchestrator.trade_style = style
                self._send_json({"status": "SUCCESS", "trade_style": style})
            elif path == "/api/action/set_mode":
                mode_str = data.get("mode", "PAPER").upper()
                try:
                    mode = ExecutionMode(mode_str)
                    self.state_manager.set_execution_mode(mode)
                    self._send_json({"status": "SUCCESS", "mode": mode.value})
                except Exception as e:
                    self._send_json({"status": "FAILED", "error": str(e)}, status_code=400)
            elif path == "/api/action/close_position":
                ticket = int(data.get("ticket", 0))
                if ticket <= 0:
                    self._send_json({"status": "FAILED", "error": "Invalid ticket number"}, status_code=400)
                    return
                res = self.mt5_client.close_position(ticket)
                # Re-sync positions in state manager immediately
                fresh_pos = self.mt5_client.get_open_positions()
                fresh_acc = self.mt5_client.get_account_snapshot()
                self.state_manager.sync_broker_state(fresh_acc, fresh_pos)
                self._send_json(res)
            elif path == "/api/action/close_all_positions":
                results = self.mt5_client.close_all_positions()
                fresh_pos = self.mt5_client.get_open_positions()
                fresh_acc = self.mt5_client.get_account_snapshot()
                self.state_manager.sync_broker_state(fresh_acc, fresh_pos)
                self._send_json({"status": "SUCCESS", "closed_count": len(results), "details": results})
            elif path == "/api/action/manual_trade":
                sym = data.get("symbol", "XAUUSD")
                action = data.get("action", "BUY").upper()
                lots = float(data.get("lots", 0.01))
                sl = float(data.get("sl", 0.0))
                tp = float(data.get("tp", 0.0))
                comment = data.get("comment", "JARVIS_ManualDesk")

                # Sanitize and auto-validate protective SL & TP
                try:
                    from jarvis.data.symbol_registry import resolve as resolve_symbol
                    spec = resolve_symbol(sym)
                    digits = spec.digits
                    df = self.data_feed.fetch_rates(sym, "H1", 20)
                    if df is not None and len(df) > 0:
                        c_price = float(df["close"].iloc[-1])
                        highs = df["high"].values
                        lows = df["low"].values
                        atr_val = float((highs[-14:] - lows[-14:]).mean()) if len(df) >= 14 else (c_price * 0.005)
                        min_dist = atr_val * 0.4

                        if action == "BUY":
                            if sl <= 0 or sl >= c_price or (c_price - sl) < min_dist:
                                sl = round(c_price - (atr_val * 1.5), digits)
                            if tp <= 0 or tp <= c_price:
                                tp = round(c_price + (abs(c_price - sl) * 2.5), digits)
                        else:  # SELL
                            if sl <= 0 or sl <= c_price or (sl - c_price) < min_dist:
                                sl = round(c_price + (atr_val * 1.5), digits)
                            if tp <= 0 or tp >= c_price:
                                tp = round(c_price - (abs(sl - c_price) * 2.5), digits)
                except Exception as ex:
                    logger.debug(f"Error checking manual SL/TP sanitization: {ex}")

                res = self.mt5_client.send_market_order(
                    symbol=sym,
                    order_type=action,
                    volume=lots,
                    sl_price=sl,
                    tp_price=tp,
                    comment=comment
                )
                if res and res.get("status") == "FILLED":
                    try:
                        from jarvis.data.database import TRADE_DB
                        TRADE_DB.log_trade(
                            ticket=res.get("ticket", 0),
                            symbol=sym,
                            action=action,
                            entry=float(res.get("price", 0.0)),
                            sl=sl,
                            tp=tp,
                            volume=lots,
                            score=100.0,
                            regime="MANUAL_EXECUTION",
                            ev=0.0,
                            executor="MANUAL"
                        )
                    except Exception as ex:
                        logger.error(f"Error logging manual trade to DB: {ex}")

                fresh_pos = self.mt5_client.get_open_positions()
                fresh_acc = self.mt5_client.get_account_snapshot()
                self.state_manager.sync_broker_state(fresh_acc, fresh_pos)
                self._send_json(res)
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"Error handling POST {path}: {e}", exc_info=True)
            self._send_json({"error": str(e)}, status_code=500)

    def _send_json(self, data: Any, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        cors_origin = os.environ.get("JARVIS_CORS_ORIGIN", "")
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.end_headers()
        payload = json.dumps(data, default=str)
        self.wfile.write(payload.encode("utf-8"))

    _STATIC_CACHE = {}

    def _serve_static_file(self, req_path: str):
        now = time.time()
        if req_path in self._STATIC_CACHE:
            content, mime_type, ts = self._STATIC_CACHE[req_path]
            if now - ts < 5.0:
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return

        static_dir = os.path.abspath(os.path.join(self.base_dir, "ui", "static"))
        rel = req_path.lstrip("/").replace("static/", "", 1)
        target_path = os.path.abspath(os.path.join(static_dir, rel))
        found_path = None
        if target_path.startswith(static_dir) and os.path.exists(target_path) and os.path.isfile(target_path):
            found_path = target_path

        if found_path:
            mime_type, _ = mimetypes.guess_type(found_path)
            if not mime_type:
                mime_type = "text/plain"
            if found_path.endswith(".css"):
                mime_type = "text/css"
            elif found_path.endswith(".js"):
                mime_type = "application/javascript"

            with open(found_path, "rb") as f:
                content = f.read()

            self._STATIC_CACHE[req_path] = (content, mime_type, now)

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, f"Static file {req_path} not found")

    def _serve_template(self, template_name: str):
        templates_dir = os.path.abspath(os.path.join(self.base_dir, "ui", "templates"))
        clean_name = os.path.basename(template_name)
        ui_path = os.path.abspath(os.path.join(templates_dir, clean_name))
        if ui_path.startswith(templates_dir) and os.path.exists(ui_path) and os.path.isfile(ui_path):
            with open(ui_path, "r", encoding="utf-8") as f:
                content = f.read()
            content_bytes = content.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content_bytes)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content_bytes)
        else:
            self.send_error(404, f"Template {template_name} not found")

    def _serve_terminal_ui(self):
        self._serve_template("index.html")

    def _serve_stocks_ui(self):
        self._serve_template("stocks.html")

    def _serve_india_ui(self):
        self._serve_template("india.html")

    def _serve_options_ui(self):
        self._serve_template("india_options.html")

def start_server(host: str = "0.0.0.0", port: int = 8501) -> ThreadingHTTPServer:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), JarvisRequestHandler)
    JarvisRequestHandler.start_background_syncer()
    logger.info(f"JARVIS AI 3.0 Web Terminal Server running at http://{host}:{port}")
    return server

def run_web_server(port: int = 8501, host: str = "0.0.0.0"):
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), JarvisRequestHandler)
    JarvisRequestHandler.start_background_syncer()
    logger.info(f"JARVIS AI 3.0 Web Terminal Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except Exception as e:
        logger.error(f"Web server serve_forever error: {e}", exc_info=True)

