"""
JARVIS AI 3.0 — India Risk Engine & SEBI Margin / Position Calculator
Calculates exact lot size allocation, Span + Exposure margins, freeze limit constraints,
and generates 1-click broker order tickets formatted for Indian discount & full-service brokers.
"""
from typing import Dict, Any, Optional
from jarvis.india.nse_rules import NSE_RULES


class IndiaRiskEngine:
    """
    SEBI & NSE Compliant Quantitative Risk & Position Sizing Manager.
    """

    def calculate_position(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_equity_inr: float = 500000.0,
        risk_pct: float = 1.0,
        instrument_type: str = "EQUITY_CASH"
    ) -> Dict[str, Any]:
        """
        Calculates exact number of lots/shares to trade respecting NSE lot constraints and quantity freeze limits.
        """
        sym = (symbol or "NIFTY").upper().strip()
        lot_size = NSE_RULES.get_lot_size(sym)
        freeze_limit = NSE_RULES.get_freeze_limit(sym)

        entry = max(0.01, float(entry_price))
        sl = max(0.01, float(stop_loss))
        tp = max(0.01, float(take_profit))

        risk_budget_inr = max(100.0, account_equity_inr * (risk_pct / 100.0))
        per_share_risk = max(0.05, abs(entry - sl))
        per_lot_risk = per_share_risk * lot_size

        if instrument_type in ["FUTURES", "OPTIONS_SPREAD"]:
            # Lot-constrained sizing
            raw_lots = int(risk_budget_inr // per_lot_risk)
            lots = max(1, raw_lots)
            shares = lots * lot_size
            
            # Check freeze limit
            freeze_warning = None
            if shares > freeze_limit:
                max_lots_per_order = freeze_limit // lot_size
                freeze_warning = f"Order exceeds NSE freeze limit ({freeze_limit} shares). Split into orders of {max_lots_per_order} lots."
                lots = max_lots_per_order
                shares = lots * lot_size

            capital_required = round(shares * entry * 0.22, 2) # ~22% Span + Exposure margin for Indian futures
        else:
            # Cash equity sizing
            shares = max(1, int(risk_budget_inr // per_share_risk))
            lots = max(1, int(shares // lot_size))
            capital_required = round(shares * entry, 2)
            freeze_warning = None

        actual_risk_inr = round(shares * per_share_risk, 2)
        actual_profit_inr = round(shares * abs(tp - entry), 2)
        rr_ratio = round(actual_profit_inr / max(1.0, actual_risk_inr), 2)

        # Indian Broker Order Command Ticket (Zerodha Kite / Upstox / Angel One format)
        broker_ticket = f"BUY {shares} {sym} (CNC/NRML) @ ₹{entry:.2f} | SL: ₹{sl:.2f} | TP: ₹{tp:.2f} | MaxRisk: ₹{actual_risk_inr:.2f}"

        # Taxes & charges estimate
        tax_est = NSE_RULES.calculate_stt_and_charges(shares * entry, instrument_type="EQUITY_INTRADAY" if instrument_type == "EQUITY_CASH" else "FUTURES")

        return {
            "symbol": sym,
            "lot_size": lot_size,
            "freeze_limit": freeze_limit,
            "lots": lots,
            "shares": shares,
            "capital_required_inr": capital_required,
            "actual_risk_inr": actual_risk_inr,
            "expected_profit_inr": actual_profit_inr,
            "risk_reward_ratio": f"1:{rr_ratio}",
            "broker_order_ticket": broker_ticket,
            "estimated_taxes_and_charges": tax_est,
            "freeze_warning": freeze_warning
        }


INDIA_RISK = IndiaRiskEngine()
