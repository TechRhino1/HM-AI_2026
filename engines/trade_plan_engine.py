import os
import json
from typing import Dict, Any, List

class TradePlanEngine:
    def __init__(self, plan_filepath: str = "trade_plans.json", logger: Any = None):
        self.plan_filepath = plan_filepath
        self.logger = logger

    def generate_trade_plans(self, opportunities: List[Dict[str, Any]], account_balance: float = 996.07) -> List[Dict[str, Any]]:
        trade_plans = []

        for opp in opportunities:
            symbol = opp.get("symbol", "N/A")
            score = float(opp.get("trade_score", 0.0))
            action = opp.get("action", "HOLD")
            regime = opp.get("regime", "UNCLEAR")
            price = float(opp.get("price", 0.0))
            sl = float(opp.get("sl", 0.0))
            tp = float(opp.get("tp", 0.0))
            rr = float(opp.get("rr", 1.5))
            decision = opp.get("decision", "REJECTED")

            if action in ["BUY", "SELL"] and price > 0:
                is_approved = (decision == "APPROVED" or score >= 75.0)
                status = "READY" if is_approved else "WAITING"

                # Dynamic Risk % based on AI score & account balance
                if score >= 88.0:
                    risk_pct = 0.75
                elif score >= 75.0:
                    risk_pct = 0.50
                else:
                    risk_pct = 0.25

                # Dynamic Lot Size calculation
                contract_size = 100.0 if ("XAU" in symbol or "GOLD" in symbol) else (1.0 if "BTC" in symbol else 100000.0)
                sl_dist = abs(price - sl) if (sl > 0 and abs(price - sl) > 0) else (price * 0.005)
                risk_amt = account_balance * (risk_pct / 100.0)
                calc_lots = risk_amt / (sl_dist * contract_size + 1e-9)
                lot_size = max(0.01, round(calc_lots, 2))

                # Precise Entry Zone & Trigger Condition
                entry_low = price * 0.9995 if action == "BUY" else price * 0.9995
                entry_high = price * 1.0005 if action == "BUY" else price * 1.0005
                entry_zone_str = f"${entry_low:,.2f} - ${entry_high:,.2f}"

                if action == "BUY":
                    trigger_cond = f"Price holds support zone ${price:,.2f} & AI Confidence >= 75.0%" if is_approved else f"Wait for pullback to ${price:,.2f} & score confirmation"
                else:
                    trigger_cond = f"Price retests resistance ${price:,.2f} & AI Confidence >= 75.0%" if is_approved else f"Wait for rejection at ${price:,.2f} & score confirmation"

                trade_plans.append({
                    "symbol": symbol,
                    "action": action,
                    "entry_zone": entry_zone_str,
                    "sl": sl,
                    "tp": tp,
                    "lot_size": lot_size,
                    "risk_pct": risk_pct,
                    "confidence": round(score, 1),
                    "expected_r": f"1:{rr:.1f} R",
                    "trigger_condition": trigger_cond,
                    "status": status,
                    "regime": regime
                })

        try:
            with open(self.plan_filepath, "w") as f:
                json.dump(trade_plans, f, indent=2)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save trade plans: {e}")

        return trade_plans
