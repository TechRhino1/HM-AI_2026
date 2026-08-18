"""
JARVIS AI 3.0 — High-Performance Telemetry & Web Terminal Server.
Provides REST, JSON streaming, and static assets for live institutional terminal UI.
"""
import os
import json
import logging
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from typing import Any

from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.market.data_feed import DataFeedEngine
from jarvis.api.copilot import JarvisCopilot
from jarvis.data.schemas import ExecutionMode

logger = logging.getLogger("JARVIS_WebServer")

class JarvisRequestHandler(BaseHTTPRequestHandler):
    state_manager: StateManager = GLOBAL_STATE
    data_feed: DataFeedEngine = DataFeedEngine()
    copilot: JarvisCopilot = JarvisCopilot(GLOBAL_STATE)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)

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
                    candles.append({
                        "time": int(r["time"].timestamp()) if hasattr(r["time"], "timestamp") else int(r["time"]),
                        "open": round(float(r["open"]), 2 if "XAU" in sym else 5),
                        "high": round(float(r["high"]), 2 if "XAU" in sym else 5),
                        "low": round(float(r["low"]), 2 if "XAU" in sym else 5),
                        "close": round(float(r["close"]), 2 if "XAU" in sym else 5),
                        "volume": float(r["volume"])
                    })
                self._send_json({"symbol": sym, "timeframe": tf, "candles": candles})
            elif path == "/api/radar":
                self._send_json({"opportunities": self.state_manager.radar_opportunities})
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
        # Resolve relative path under static/
        rel = req_path.lstrip("/").replace("static/", "", 1)
        
        # Check potential candidate locations
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
            self.send_header("Cache-Control", "no-cache")
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
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(500, "UI template not found")

    def log_message(self, format, *args):
        pass

def run_web_server(port: int = 8501):
    server = ThreadingHTTPServer(("0.0.0.0", port), JarvisRequestHandler)
    logger.info(f"JARVIS 3.0 Web Terminal running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
