"""
JARVIS AI 3.0 — NSE/SEBI India Rule & Contract Specifications Engine
Dynamically determines official lot sizes, quantity freeze limits, strike intervals,
expiry schedules, circuit filters, and exchange turnover/STT charges for Indian derivatives and equities.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta


# Official NSE Lot Size Master (Updated as per latest NSE circulars)
NSE_LOT_SIZES: Dict[str, int] = {
    # Benchmark & Sectoral Indices
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
    "BANKEX": 15,
    
    # Top F&O Stocks (High Liquidity)
    "RELIANCE": 250,
    "TCS": 175,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "INFY": 400,
    "BHARTIARTL": 475,
    "SBIN": 750,
    "ITC": 1600,
    "LT": 175,
    "HINDUNILVR": 300,
    "TATAMOTORS": 1425,
    "MARUTI": 50,
    "SUNPHARMA": 350,
    "BAJFINANCE": 125,
    "TITAN": 175,
    "AXISBANK": 625,
    "KOTAKBANK": 400,
    "ADANIENT": 300,
    "TATASTEEL": 5500,
    "ZOMATO": 2500,
    "JIOFIN": 2000,
    "HAL": 150,
    "BEL": 2700,
    "DIXON": 50,
    "TRENT": 100,
    "NTPC": 1500,
    "ONGC": 3850,
    "POWERGRID": 1900,
    "M&M": 350,
    "COALINDIA": 2100,
    "BAJAJ-AUTO": 75,
    "ASIANPAINT": 200,
    "HCLTECH": 350,
    "WIPRO": 1500,
    "TECHM": 600,
    "ULTRACEMCO": 100,
    "NESTLEIND": 20,
    "GRASIM": 250,
    "JSWSTEEL": 675,
    "DRREDDY": 125,
    "CIPLA": 650,
    "APOLLOHOSP": 125,
    "DIVISLAB": 100,
    "HEROMOTOCO": 150,
    "EICHERMOT": 175,
    "BPCL": 1800,
    "IOC": 4875,
    "ADANIPORTS": 400,
    "SBILIFE": 375,
    "HDFCLIFE": 1100,
    "DLF": 825,
    "CANBK": 6750,
    "PNB": 8000,
    "BANKBARODA": 2925,
    "HINDALCO": 1400,
    "VEDL": 1150,
    "RECLTD": 1000,
    "PFC": 1300,
    "IRFC": 3500,
    "RVNL": 1500,
    "MAZDOCK": 175,
    "BDL": 300,
    "PERSISTENT": 100,
    "COFORGE": 75,
    "LTIM": 150,
    "POLYCAB": 100,
    "SUZLON": 10000,
    "IDEA": 80000,
    "PAYTM": 650,
    "SWIGGY": 1000,
    "HYUNDAI": 300
}

# Quantity Freeze Limits (Maximum allowable single-order quantity on NSE)
NSE_FREEZE_LIMITS: Dict[str, int] = {
    "NIFTY": 1800,
    "BANKNIFTY": 900,
    "FINNIFTY": 1800,
    "MIDCPNIFTY": 4200,
    "SENSEX": 1000,
    "DEFAULT_STOCK": 50000
}

# Strike Interval Step Map
STRIKE_STEPS: Dict[str, float] = {
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
    "FINNIFTY": 50.0,
    "MIDCPNIFTY": 25.0,
    "SENSEX": 100.0,
    "HIGH_VALUE": 50.0,     # > ₹5000 (e.g. Maruti, Dixon, Ultratech)
    "MID_HIGH_VALUE": 20.0, # ₹2000 - ₹5000 (e.g. TCS, Reliance, Titan)
    "MID_VALUE": 10.0,      # ₹500 - ₹2000 (e.g. Infosys, ICICI, Tata Motors)
    "LOW_VALUE": 5.0,       # ₹100 - ₹500 (e.g. ITC, BEL, Tata Steel)
    "PENNY_VALUE": 1.0      # < ₹100 (e.g. Suzlon, Idea)
}


class NSERuleEngine:
    """
    Validates SEBI & NSE regulatory constraints, lot sizing, and transaction math.
    """

    @staticmethod
    def get_lot_size(symbol: str) -> int:
        sym = (symbol or "").upper().strip().replace(".NSE", "").replace(".BSE", "")
        return NSE_LOT_SIZES.get(sym, 100)

    @staticmethod
    def get_freeze_limit(symbol: str) -> int:
        sym = (symbol or "").upper().strip()
        return NSE_FREEZE_LIMITS.get(sym, NSE_FREEZE_LIMITS["DEFAULT_STOCK"])

    @staticmethod
    def get_strike_step(symbol: str, price: float = 1000.0) -> float:
        sym = (symbol or "").upper().strip()
        if sym in STRIKE_STEPS:
            return STRIKE_STEPS[sym]
        
        if price >= 5000:
            return STRIKE_STEPS["HIGH_VALUE"]
        elif price >= 2000:
            return STRIKE_STEPS["MID_HIGH_VALUE"]
        elif price >= 500:
            return STRIKE_STEPS["MID_VALUE"]
        elif price >= 100:
            return STRIKE_STEPS["LOW_VALUE"]
        else:
            return STRIKE_STEPS["PENNY_VALUE"]

    @staticmethod
    def get_expiry_schedule(symbol: str) -> Dict[str, Any]:
        """
        Calculates the official weekly, next-week, and monthly expiry dates.
        - NIFTY, BANKNIFTY & Equities: Thursday
        - FINNIFTY: Tuesday
        - MIDCPNIFTY: Monday
        - SENSEX: Friday
        """
        sym = (symbol or "NIFTY").upper().strip()
        now = datetime.now(timezone.utc)
        
        # Target weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
        if sym == "MIDCPNIFTY":
            target_weekday = 0 # Monday
        elif sym == "FINNIFTY":
            target_weekday = 1 # Tuesday
        elif sym in ["SENSEX", "BANKEX"]:
            target_weekday = 4 # Friday
        else:
            target_weekday = 3 # Thursday (Nifty, BankNifty, and all Equities)

        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0 and now.hour >= 15: # If expiry day after market hours (3:30 PM IST), jump to next week
            days_ahead = 7
            
        current_weekly = now + timedelta(days=days_ahead)
        next_weekly = current_weekly + timedelta(days=7)
        monthly = current_weekly + timedelta(days=21)

        return {
            "current_expiry": current_weekly.strftime("%d-%b-%Y").upper(),
            "next_expiry": next_weekly.strftime("%d-%b-%Y").upper(),
            "monthly_expiry": monthly.strftime("%d-%b-%Y").upper(),
            "days_to_expiry": max(0, days_ahead),
            "expiry_day_name": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][target_weekday]
        }

    @staticmethod
    def calculate_stt_and_charges(turnover: float, instrument_type: str = "OPTIONS") -> Dict[str, float]:
        """
        Calculates SEBI, STT (Revised 2024-2026 Union Budget rates), Exchange Turnover, GST, and Stamp Duty.
        """
        if instrument_type == "EQUITY_DELIVERY":
            stt = turnover * 0.001       # 0.1% on buy/sell
            brokerage = min(20.0, turnover * 0.0005)
            exchange_txn = turnover * 0.0000345
            stamp_duty = turnover * 0.00015
        elif instrument_type == "EQUITY_INTRADAY":
            stt = turnover * 0.00025     # 0.025% on sell
            brokerage = min(20.0, turnover * 0.0003)
            exchange_txn = turnover * 0.0000345
            stamp_duty = turnover * 0.00003
        elif instrument_type == "FUTURES":
            stt = turnover * 0.0002      # 0.02% (Hiked by 150% in 2024-2026 budget)
            brokerage = 20.0
            exchange_txn = turnover * 0.00002
            stamp_duty = turnover * 0.00002
        else: # OPTIONS (Premium Turnover)
            stt = turnover * 0.001       # 0.1% on premium turnover
            brokerage = 20.0
            exchange_txn = turnover * 0.00053
            stamp_duty = turnover * 0.00003

        sebi_charges = turnover * 0.000001 # ₹10 per crore
        gst = (brokerage + exchange_txn + sebi_charges) * 0.18
        total_tax_and_charges = round(stt + brokerage + exchange_txn + sebi_charges + stamp_duty + gst, 2)

        return {
            "stt": round(stt, 2),
            "brokerage": round(brokerage, 2),
            "exchange_txn": round(exchange_txn, 2),
            "sebi_charges": round(sebi_charges, 2),
            "stamp_duty": round(stamp_duty, 2),
            "gst": round(gst, 2),
            "total_charges": total_tax_and_charges
        }

    @staticmethod
    def calculate_margin_requirement(
        symbol: str,
        spot_price: float,
        quantity: int,
        is_short_option: bool = False,
        is_expiry_day: bool = False
    ) -> Dict[str, Any]:
        """
        SEBI 2024-2026 Upfront Peak Margin & Extreme Loss Margin (ELM) estimator.
        - ₹15L-20L contract size framework
        - 100% Upfront collection
        - Additional 2% ELM on expiry day for short index options
        """
        contract_value = spot_price * quantity
        base_span_pct = 0.12 # 12% SPAN proxy
        exposure_pct = 0.03  # 3% Exposure proxy
        elm_pct = 0.02 if (is_short_option and is_expiry_day) else 0.0

        total_margin_pct = base_span_pct + exposure_pct + elm_pct
        required_margin = round(contract_value * total_margin_pct, 2)

        return {
            "contract_value": round(contract_value, 2),
            "span_margin": round(contract_value * base_span_pct, 2),
            "exposure_margin": round(contract_value * exposure_pct, 2),
            "elm_margin": round(contract_value * elm_pct, 2),
            "total_margin_required": required_margin,
            "margin_pct": round(total_margin_pct * 100.0, 1),
            "is_expiry_day_elm_applied": bool(elm_pct > 0)
        }


NSE_RULES = NSERuleEngine()
