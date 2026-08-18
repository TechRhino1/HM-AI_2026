import json
import urllib.request
import urllib.parse
from typing import Any

class TelegramNotifier:
    def __init__(self, bot_token: str = "", chat_id: str = "", logger: Any = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        self.enabled = bool(bot_token and chat_id)

    def send_message(self, message: str) -> bool:
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=4) as resp:
                return resp.status == 200
        except Exception as e:
            if self.logger:
                self.logger.error(f"Telegram notification failed: {e}")
            return False

    def notify_trade_execution(self, symbol: str, order_type: str, lots: float, price: float, sl: float, tp: float, score: float, regime: str):
        msg = (
            f"🚀 *AI TRADE EXECUTED*\n\n"
            f"🔹 *Symbol:* `{symbol}`\n"
            f"🔹 *Action:* `{order_type}`\n"
            f"🔹 *Volume:* `{lots} Lots`\n"
            f"🔹 *Entry:* `${price:,.2f}`\n"
            f"🔹 *Stop Loss:* `${sl:,.2f}`\n"
            f"🔹 *Take Profit:* `${tp:,.2f}`\n"
            f"🔹 *Market Regime:* `{regime}`\n"
            f"🔹 *Trade Score:* `{score:.1f}/100`\n"
        )
        self.send_message(msg)
