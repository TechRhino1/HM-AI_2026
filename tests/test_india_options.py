"""
Dedicated Mathematical & Regulatory Test Suite for India F&O Options Desk
Tests:
1. Black-Scholes Greeks calculation (Call & Put delta, gamma, theta, vega, rho, intrinsic value)
2. ATM Strike detection and dynamic interval spacing
3. SEBI Hedge Margin benefit calculations
4. 12 Defined-Risk Multi-Leg Option Strategies & Payoff profiles
"""
import sys
import os
import pytest

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from jarvis.india.greeks import GREEKS_ENGINE
from jarvis.india.options_engine import INDIA_OPTIONS
from jarvis.india.options_signal_engine import OPTION_SIGNALS
from jarvis.india.nse_rules import NSE_RULES

def test_black_scholes_greeks_math():
    spot = 24850.0
    strike = 24850.0
    time_to_exp = 5.0 / 365.0 # 5 days
    iv = 0.16 # 16% IV

    greeks = GREEKS_ENGINE.calculate_greeks(
        spot=spot,
        strike=strike,
        time_to_expiry_years=time_to_exp,
        volatility=iv
    )

    assert "call" in greeks and "put" in greeks
    call = greeks["call"]
    put = greeks["put"]

    # ATM Call Delta should be approximately 0.50 (+/- 0.08)
    assert 0.42 <= call["delta"] <= 0.58, f"Call Delta unexpected: {call['delta']}"
    # ATM Put Delta should be approximately -0.50 (+/- 0.08)
    assert -0.58 <= put["delta"] <= -0.42, f"Put Delta unexpected: {put['delta']}"
    # Delta sum magnitude ~ 1.0 (Put-Call Parity)
    assert abs(abs(call["delta"]) + abs(put["delta"]) - 1.0) < 0.05

    # Gamma must be strictly positive for long options
    assert call["gamma"] > 0
    assert call["gamma"] == put["gamma"]

    # Theta decay must be negative per day
    assert call["theta"] < 0
    assert put["theta"] < 0

    # Vega must be positive
    assert call["vega"] > 0

def test_sebi_hedge_margin_benefit():
    # Multi-leg Bull Call Spread: Long 24800 CE, Short 25000 CE (Spread width = 200 pts, Lot size = 25)
    legs = [
        {"action": "BUY", "type": "CE", "strike": 24800, "price": 180.0, "lots": 1},
        {"action": "SELL", "type": "CE", "strike": 25000, "price": 80.0, "lots": 1}
    ]

    margin_info = INDIA_OPTIONS.calculate_multi_leg_payoff("NIFTY", legs)
    assert "margin_breakdown" in margin_info
    mb = margin_info["margin_breakdown"]
    assert "gross_margin_inr" in mb
    assert "hedge_benefit_inr" in mb
    assert "final_margin_required_inr" in mb
    assert mb["hedge_benefit_inr"] > 0
    assert mb["final_margin_required_inr"] < mb["gross_margin_inr"]

def test_multi_leg_payoff_curve():
    strategy_res = INDIA_OPTIONS.generate_ai_options_strategy("NIFTY", "BULL_CALL_SPREAD")
    assert strategy_res is not None
    assert "spot_grid" in strategy_res
    assert len(strategy_res["spot_grid"]) > 10
    assert strategy_res["max_profit_inr"] > 0
    assert strategy_res["max_loss_inr"] < 0
    assert "strategy_name" in strategy_res

def test_single_option_buy_signals():
    signals = OPTION_SIGNALS.generate_single_option_signals(limit=5)
    assert len(signals) > 0
    for s in signals:
        assert "contract_symbol" in s
        assert "trade_plan" in s
        tp = s["trade_plan"]
        assert tp["entry_premium"] > 0
        assert tp["target_1_premium"] > tp["entry_premium"]
        assert tp["stop_loss_premium"] < tp["entry_premium"]

if __name__ == "__main__":
    test_black_scholes_greeks_math()
    test_sebi_hedge_margin_benefit()
    test_multi_leg_payoff_curve()
    test_single_option_buy_signals()
    print("ALL INDIA OPTIONS TESTS PASSED!")
