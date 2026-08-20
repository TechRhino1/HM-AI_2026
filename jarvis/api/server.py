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
from typing import Any

from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.market.data_feed import DataFeedEngine
from jarvis.api.copilot import JarvisCopilot
from jarvis.execution.mt5_client import MT5Client
from jarvis.data.schemas import ExecutionMode

logger = logging.getLogger("JARVIS_WebServer")

class JarvisRequestHandler(BaseHTTPRequestHandler):
    state_manager: StateManager = GLOBAL_STATE
    mt5_client: MT5Client = MT5Client(mode="live")
    data_feed: DataFeedEngine = DataFeedEngine(mt5_client=mt5_client)
    copilot: JarvisCopilot = JarvisCopilot(GLOBAL_STATE)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)

    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/" or path == "/index.html":
                self._serve_terminal_ui()
            elif path.startswith("/static/"):
                self._serve_static_file(path)
            elif path == "/api/telemetry_state":
                self._send_json(self.state_manager.get_state_snapshot())
            elif path == "/api/candles":
                sym = query.get("symbol", ["XAUUSD"])[0]
                tf = query.get("tf", ["H1"])[0]
                df = self.data_feed.fetch_rates(sym, timeframe=tf, num_bars=150)
                candles = []
                for _, r in df.iterrows():
                    # Ensure timestamp is UTC UNIX seconds
                    t_val = r["time"]
                    if hasattr(t_val, "tzinfo") and t_val.tzinfo is None:
                        t_val = t_val.tz_localize("UTC")
                    
                    candles.append({
                        "time": int(t_val.timestamp()) if hasattr(t_val, "timestamp") else int(t_val),
                        "open": round(float(r["open"]), 2 if "XAU" in sym else 5),
                        "high": round(float(r["high"]), 2 if "XAU" in sym else 5),
                        "low": round(float(r["low"]), 2 if "XAU" in sym else 5),
                        "close": round(float(r["close"]), 2 if "XAU" in sym else 5),
                        "volume": float(r["volume"])
                    })
                self._send_json({"symbol": sym, "timeframe": tf, "candles": candles})
            elif path == "/api/radar":
                self._send_json({"opportunities": self.state_manager.radar_opportunities})
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

            if path == "/api/copilot/ask":
                query = data.get("query", "")
                response_text = self.copilot.ask(query)
                self._send_json({"query": query, "response": response_text})
            elif path == "/api/action/toggle_safe_mode":
                is_safe = self.state_manager.toggle_safe_mode()
                self._send_json({"safe_mode": is_safe})
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        payload = json.dumps(data, default=str)
        self.wfile.write(payload.encode("utf-8"))

    def _serve_static_file(self, req_path: str):
        rel = req_path.lstrip("/").replace("static/", "", 1)
        candidates = [
            os.path.join(self.base_dir, "ui", "static", rel),
            os.path.join(self.root_dir, "ui", "static", rel)
        ]

        found_path = None
        for p in candidates:
            if os.path.exists(p) and os.path.isfile(p):
                found_path = p
                break

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

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, f"Static file {req_path} not found")

    def _serve_terminal_ui(self):
        candidates = [
            os.path.join(self.base_dir, "ui", "templates", "index.html"),
            os.path.join(self.root_dir, "ui", "templates", "index.html")
        ]
        ui_path = None
        for c in candidates:
            if os.path.exists(c):
                ui_path = c
                break

        if ui_path:
            with open(ui_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode("utf-8"))))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404, "Terminal UI index.html not found")

def start_server(host: str = "0.0.0.0", port: int = 8501) -> ThreadingHTTPServer:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), JarvisRequestHandler)
    logger.info(f"JARVIS AI 3.0 Web Terminal Server running at http://{host}:{port}")
    return server

def run_web_server(port: int = 8501, host: str = "0.0.0.0"):
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), JarvisRequestHandler)
    logger.info(f"JARVIS AI 3.0 Web Terminal Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except Exception as e:
        logger.error(f"Web server serve_forever error: {e}", exc_info=True)

