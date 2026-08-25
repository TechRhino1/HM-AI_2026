"""
JARVIS AI 3.0 — Black-Scholes Pricing & Option Greeks Engine
Computes analytical Greeks (Delta, Gamma, Theta, Vega, Rho), Implied Volatility (IV),
Max Pain Strike, Put-Call Ratio (PCR), and IV Percentiles for Indian F&O contracts.
"""
import math
from typing import Dict, Any, List, Tuple, Optional


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


class OptionGreeksEngine:
    """
    Quantitative Options Pricing & Greeks Model.
    """

    @staticmethod
    def calculate_greeks(
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.07, # RBI Repo Rate baseline (~6.5% - 7.0%)
        dividend_yield: float = 0.012
    ) -> Dict[str, Any]:
        """
        Calculates theoretical option premium and analytical Greeks for both CE & PE.
        """
        S = max(0.01, spot)
        K = max(0.01, strike)
        T = max(0.0001, time_to_expiry_years)
        sigma = max(0.01, volatility)
        r = risk_free_rate
        q = dividend_yield

        d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        exp_qT = math.exp(-q * T)
        exp_rT = math.exp(-r * T)
        pdf_d1 = norm_pdf(d1)

        # Call & Put Theoretical Pricing
        call_price = max(0.05, S * exp_qT * norm_cdf(d1) - K * exp_rT * norm_cdf(d2))
        put_price = max(0.05, K * exp_rT * norm_cdf(-d2) - S * exp_qT * norm_cdf(-d1))

        # Greeks
        call_delta = exp_qT * norm_cdf(d1)
        put_delta = -exp_qT * norm_cdf(-d1)
        gamma = (exp_qT * pdf_d1) / (S * sigma * math.sqrt(T))
        vega = (S * exp_qT * pdf_d1 * math.sqrt(T)) / 100.0 # Per 1% change in IV

        # Theta (decay per calendar day = annual theta / 365)
        call_theta_annual = - (S * sigma * exp_qT * pdf_d1) / (2.0 * math.sqrt(T)) - r * K * exp_rT * norm_cdf(d2) + q * S * exp_qT * norm_cdf(d1)
        put_theta_annual = - (S * sigma * exp_qT * pdf_d1) / (2.0 * math.sqrt(T)) + r * K * exp_rT * norm_cdf(-d2) - q * S * exp_qT * norm_cdf(-d1)

        call_theta_day = call_theta_annual / 365.0
        put_theta_day = put_theta_annual / 365.0

        # Rho
        call_rho = (K * T * exp_rT * norm_cdf(d2)) / 100.0
        put_rho = (-K * T * exp_rT * norm_cdf(-d2)) / 100.0

        return {
            "strike": strike,
            "call": {
                "price": round(call_price, 2),
                "delta": round(call_delta, 3),
                "gamma": round(gamma, 5),
                "theta": round(call_theta_day, 2),
                "vega": round(vega, 2),
                "rho": round(call_rho, 3),
                "intrinsic_value": round(max(0.0, spot - strike), 2),
                "extrinsic_value": round(max(0.0, call_price - max(0.0, spot - strike)), 2)
            },
            "put": {
                "price": round(put_price, 2),
                "delta": round(put_delta, 3),
                "gamma": round(gamma, 5),
                "theta": round(put_theta_day, 2),
                "vega": round(vega, 2),
                "rho": round(put_rho, 3),
                "intrinsic_value": round(max(0.0, strike - spot), 2),
                "extrinsic_value": round(max(0.0, put_price - max(0.0, strike - spot)), 2)
            }
        }

    @staticmethod
    def calculate_max_pain(strikes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates the Max Pain Strike where option writers have minimal payout liability at expiry.
        """
        if not strikes_data:
            return {"max_pain_strike": 0.0, "total_loss_at_pain": 0.0}

        strikes = [s["strike"] for s in strikes_data]
        min_loss = float("inf")
        max_pain_strike = strikes[0]

        for test_k in strikes:
            total_loss = 0.0
            for item in strikes_data:
                k = item["strike"]
                ce_oi = item.get("ce_oi", 0)
                pe_oi = item.get("pe_oi", 0)

                # If market expires at test_k:
                # Calls above test_k expire worthless, calls below are ITM
                if test_k > k:
                    total_loss += (test_k - k) * ce_oi
                # Puts below test_k expire worthless, puts above are ITM
                if test_k < k:
                    total_loss += (k - test_k) * pe_oi

            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = test_k

        return {
            "max_pain_strike": max_pain_strike,
            "total_pain_value": round(min_loss, 2)
        }

    @staticmethod
    def calculate_pcr(strikes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates Put-Call Ratio for Open Interest and Volume.
        - PCR > 1.2 : Bullish / Oversold Support
        - PCR < 0.7 : Bearish / Overbought Resistance
        - PCR 0.85 - 1.15 : Neutral Range
        """
        total_ce_oi = sum(s.get("ce_oi", 0) for s in strikes_data)
        total_pe_oi = sum(s.get("pe_oi", 0) for s in strikes_data)
        total_ce_vol = sum(s.get("ce_volume", 0) for s in strikes_data)
        total_pe_vol = sum(s.get("pe_volume", 0) for s in strikes_data)

        pcr_oi = round(total_pe_oi / max(1, total_ce_oi), 2)
        pcr_vol = round(total_pe_vol / max(1, total_ce_vol), 2)

        if pcr_oi >= 1.3:
            sentiment = "STRONGLY_BULLISH"
            bias_badge = "🔥 Bullish OI Floor"
        elif pcr_oi >= 1.05:
            sentiment = "MODERATELY_BULLISH"
            bias_badge = "🟢 Mildly Bullish"
        elif pcr_oi <= 0.65:
            sentiment = "STRONGLY_BEARISH"
            bias_badge = "🔻 Heavy CE Call Wall"
        elif pcr_oi <= 0.85:
            sentiment = "MODERATELY_BEARISH"
            bias_badge = "🔴 Mildly Bearish"
        else:
            sentiment = "NEUTRAL_RANGEBOUND"
            bias_badge = "⚖️ Balanced Range"

        return {
            "pcr_oi": pcr_oi,
            "pcr_volume": pcr_vol,
            "total_call_oi": total_ce_oi,
            "total_put_oi": total_pe_oi,
            "sentiment": sentiment,
            "bias_badge": bias_badge
        }


GREEKS_ENGINE = OptionGreeksEngine()
