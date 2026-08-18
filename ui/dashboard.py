from datetime import datetime
from typing import Dict, Any

class TelemetryDashboard:
    @staticmethod
    def render(
        symbol: str,
        account_info: Dict[str, Any],
        regime_info: Dict[str, Any],
        volatility_info: Dict[str, Any],
        news_info: Dict[str, Any],
        decision_info: Dict[str, Any]
    ):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        regime = regime_info.get("regime", "N/A")
        confidence = regime_info.get("confidence", 0.0)
        vol_state = volatility_info.get("state", "N/A")
        spread = volatility_info.get("current_spread_pips", 0.0)
        news_status = news_info.get("news_status", "N/A")
        
        score = decision_info.get("trade_score", 0.0)
        action = decision_info.get("action", "HOLD")
        decision = decision_info.get("decision", "NO_TRADE")
        strategy = decision_info.get("strategy", "N/A")
        
        balance = account_info.get("balance", 0.0)
        equity = account_info.get("equity", 0.0)

        lines = [
            "================================================================================",
            f"                     AI ADAPTIVE MT5 TRADER - TELEMETRY CONTROL                ",
            f"                             Local Time: {now}                           ",
            "================================================================================",
            f" [ACCOUNT] Balance: ${balance:,.2f} USD  | Equity: ${equity:,.2f} USD",
            f" [SYMBOL]  Instrument: {symbol} | Spread: {spread} pips",
            "--------------------------------------------------------------------------------",
            f" [REGIME]   {regime} (Confidence: {confidence:.1f}%)",
            f" [VOL]      State: {vol_state} | News Risk: {news_status}",
            f" [STRATEGY] Active: {strategy}",
            "--------------------------------------------------------------------------------",
            f" [DECISION] {decision} | Action: {action} | Trade Score: {score:.1f}/100",
            "--------------------------------------------------------------------------------",
        ]

        reasons = decision_info.get("reasons", [])
        if reasons:
            lines.append(" Triggers:")
            for r in reasons[:3]:
                lines.append(f"  + {r}")

        reasons_not = decision_info.get("reasons_not_to_trade", [])
        if reasons_not:
            lines.append(" Risk Filters / Inhibitors:")
            for rn in reasons_not[:3]:
                lines.append(f"  - {rn}")

        lines.append("================================================================================")
        print("\n".join(lines))
