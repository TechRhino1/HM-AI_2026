import os
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Any, List

class NewsIntelligenceEngine:
    def __init__(
        self,
        enabled: bool = True,
        elevate_threshold_on_news_offline: bool = False,
        api_url: str = "https://nouveau-calendar.forexfactory.com/week/current.json",
        buffer_before_mins: int = 30,
        buffer_after_mins: int = 30,
        local_calendar_path: str = "",
        logger: Any = None
    ):
        self.enabled = enabled
        self.elevate_threshold_on_news_offline = elevate_threshold_on_news_offline
        self.api_urls = [
            api_url,
            "https://nouveau-calendar.forexfactory.com/week/current.json",
            "https://nfp.ourway.workers.dev/economic-calendar"
        ]
        self.buffer_before_mins = buffer_before_mins
        self.buffer_after_mins = buffer_after_mins
        self.local_calendar_path = local_calendar_path or os.path.join("config", "economic_calendar.json")
        self.logger = logger

    def fetch_calendar_events(self) -> tuple[List[Dict[str, Any]], str]:
        """Multi-Source News Retriever: Tries Forex Factory live feeds, falls back to local master calendar."""
        if not self.enabled:
            return [], "DISABLED"

        # Create unverified SSL context to prevent SSL cert issues
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Try Live Sources (Forex Factory)
        for url in self.api_urls:
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
                    if resp.status == 200:
                        raw_data = resp.read().decode("utf-8")
                        data = json.loads(raw_data)
                        events = data if isinstance(data, list) else data.get("events", [])
                        if events:
                            if self.logger:
                                self.logger.info(f"Successfully fetched live calendar from {url} ({len(events)} events)")
                            return events, "FOREX_FACTORY_LIVE"
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not fetch live calendar from {url}: {e}")
                continue

        # Fallback to Master Local Economic Calendar
        if os.path.exists(self.local_calendar_path):
            try:
                with open(self.local_calendar_path, "r") as f:
                    local_data = json.load(f)
                    events = local_data.get("events", [])
                    if self.logger:
                        self.logger.info(f"Using Master Local Economic Calendar ({len(events)} high-impact events configured)")
                    return events, "LOCAL_MASTER_CALENDAR"
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error loading local calendar: {e}")

        return [], "NEWS_DATA_UNAVAILABLE"

    def evaluate_news_risk(self, symbol: str) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "news_status": "NEWS_RISK_LOW",
                "high_impact_imminent": False,
                "news_source": "DISABLED",
                "minutes_to_next_high_impact": None,
                "reasons_not_to_trade": []
            }

        events, source = self.fetch_calendar_events()

        if source == "NEWS_DATA_UNAVAILABLE":
            status = "NEWS_DATA_UNAVAILABLE" if self.elevate_threshold_on_news_offline else "NEWS_RISK_LOW"
            reasons = ["Real-time news feed unavailable; requiring elevated score threshold."] if self.elevate_threshold_on_news_offline else []
            return {
                "news_status": status,
                "high_impact_imminent": False,
                "news_source": source,
                "minutes_to_next_high_impact": None,
                "reasons_not_to_trade": reasons
            }

        now = datetime.utcnow()
        currency_map = {
            "XAUUSD": "USD",
            "GOLD.i#": "USD",
            "GOLD": "USD",
            "EURUSD": ["USD", "EUR"],
            "GBPUSD": ["USD", "GBP"],
            "USDJPY": ["USD", "JPY"],
            "BTCUSD": "USD"
        }

        target_currencies = currency_map.get(symbol, ["USD"])
        if isinstance(target_currencies, str):
            target_currencies = [target_currencies]

        high_impact_imminent = False
        closest_mins = 9999

        for event in events:
            curr = event.get("country", event.get("currency", "")).upper()
            impact = str(event.get("impact", "")).upper()

            if curr in target_currencies and impact in ["HIGH", "RED"]:
                time_str = event.get("timestamp", event.get("date", ""))
                if time_str:
                    try:
                        event_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        diff_mins = (event_dt - now).total_seconds() / 60.0

                        if -self.buffer_after_mins <= diff_mins <= self.buffer_before_mins:
                            high_impact_imminent = True
                        
                        if abs(diff_mins) < abs(closest_mins):
                            closest_mins = int(diff_mins)
                    except Exception:
                        continue

        return {
            "news_status": "NEWS_RISK_HIGH" if high_impact_imminent else "NEWS_RISK_LOW",
            "high_impact_imminent": high_impact_imminent,
            "news_source": source,
            "minutes_to_next_high_impact": closest_mins if closest_mins != 9999 else None,
            "reasons_not_to_trade": ["High-impact Forex Factory / Economic event imminent inside buffer window."] if high_impact_imminent else []
        }
