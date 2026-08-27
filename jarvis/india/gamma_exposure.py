"""
JARVIS AI 4.0 — Gamma Exposure (GEX) / Dealer-Flow Analytics for India Options.

Implements the standard institutional dealer-gamma framework (Squeezemetrics /
vannacharm style):

  * Per-strike dealer gamma exposure:
        Call GEX =  call_gamma * call_OI * spot * multiplier   (dealers are net SHORT calls)
        Put  GEX = -put_gamma  * put_OI  * spot * multiplier   (dealers are net SHORT puts)
  * Net GEX, the Zero-Gamma ("gamma flip") level, and regime classification:
        POSITIVE (dealers long gamma) -> expect mean-reversion / absorption
        NEGATIVE (dealers short gamma) -> expect momentum / acceleration
  * Vanna & Charm exposure -> directional dealer hedging flow pressure.
  * A resulting directional read used to bias option-buying signals.

The math is correct for ANY option chain feed (live or synthetic); results are only
as good as the underlying OI/IV data. When chain data is synthetic, the engine flags
`data_source="synthetic"` so the UI cannot mistake it for a real read.
"""
from typing import Dict, Any, List, Optional
import math

from jarvis.india.greeks import GREEKS_ENGINE


def _gamma_for(spot, strike, t_years, vol):
    g = GREEKS_ENGINE.calculate_greeks(spot=spot, strike=strike, time_to_expiry_years=t_years, volatility=vol)
    return g["call"]["gamma"], g["put"]["gamma"]


def compute_gex(
    chain: Dict[str, Any],
    spot: float,
    multiplier: float,
    time_years: float,
    volatility: float,
    r_rate: float = 0.06
) -> Dict[str, Any]:
    """Compute dealer gamma / vanna / charm exposure from an option-chain payload.

    chain: {'chain': [ {strike, call:{oi,gamma,delta,vega,...}, put:{oi,gamma,delta,vega,...}} ]}
    multiplier: contract lot size (positions multiplier).
    Returns structured dealer-flow analytics.
    """
    rows = chain.get("chain", [])
    if not rows or spot <= 0:
        return {"data_source": "empty", "net_gex": 0.0, "zero_gamma_level": spot, "regime": "UNKNOWN"}

    # Per-strike contributions at current spot
    per_strike = []
    net_gex = 0.0
    net_vanna = 0.0
    net_charm = 0.0
    for r in rows:
        k = float(r["strike"])
        c_oi = float(r["call"].get("oi", 0.0))
        p_oi = float(r["put"].get("oi", 0.0))
        c_g, p_g = _gamma_for(spot, k, time_years, volatility)
        # Dealer exposure signs: dealers are net short both calls and puts to customers
        call_gex = c_g * c_oi * spot * multiplier
        put_gex = -p_g * p_oi * spot * multiplier
        gex = call_gex + put_gex
        net_gex += gex
        # Vanna (dDelta/dVol) ~ proportional to vega * d1 shape; approximate via vega * (1 - 2*delta)
        c_v = float(r["call"].get("vega", 0.0))
        p_v = float(r["put"].get("vega", 0.0))
        c_d = float(r["call"].get("delta", 0.0))
        p_d = float(r["put"].get("delta", 0.0))
        vanna_c = c_v * (1.0 - 2.0 * abs(c_d)) * c_oi * multiplier
        vanna_p = -p_v * (1.0 - 2.0 * abs(p_d)) * p_oi * multiplier
        net_vanna += vanna_c + vanna_p
        # Charm (dDelta/dt) ~ theta-scaled; approximate with theta * delta sign
        c_t = float(r["call"].get("theta", 0.0))
        p_t = float(r["put"].get("theta", 0.0))
        net_charm += (c_t * c_oi + p_t * p_oi) * multiplier
        per_strike.append({"strike": k, "gex": round(gex, 1), "call_gex": round(call_gex, 1), "put_gex": round(put_gex, 1)})

    # Find zero-gamma (gamma flip) by scanning spot grid
    lo = spot * 0.85
    hi = spot * 1.15
    grid = 240
    step = (hi - lo) / grid
    prev_net = None
    zero_level = None
    for i in range(grid + 1):
        s = lo + i * step
        gsum = 0.0
        for r in rows:
            k = float(r["strike"])
            c_oi = float(r["call"].get("oi", 0.0))
            p_oi = float(r["put"].get("oi", 0.0))
            c_g, p_g = _gamma_for(s, k, time_years, volatility)
            gsum += (c_g * c_oi * s * multiplier) + (-p_g * p_oi * s * multiplier)
        if prev_net is not None and ((prev_net <= 0 and gsum > 0) or (prev_net >= 0 and gsum < 0)):
            # linear interpolate crossing
            denom = (prev_net - gsum)
            if abs(denom) > 1e-9:
                frac = (0.0 - prev_net) / denom
                zero_level = s - step + frac * step
                break
        prev_net = gsum

    regime = "POSITIVE" if net_gex > 0 else ("NEGATIVE" if net_gex < 0 else "NEUTRAL")

    # Directional read from dealer flow:
    #  - Positive GEX => pin/mean-revert: fade away from zero_gamma_level.
    #  - Negative GEX => follow momentum: bias toward breakout.
    #  - Vanna positive => dealers buy gamma on rallies (pro-uptrend); negative => pro-down.
    bias = "NEUTRAL"
    if regime == "POSITIVE":
        if zero_level and spot > zero_level:
            bias = "BEARISH"  # above flip -> dealers sell into strength (mean revert down)
        elif zero_level and spot < zero_level:
            bias = "BULLISH"
        else:
            bias = "NEUTRAL"
    elif regime == "NEGATIVE":
        bias = "BULLISH" if net_vanna >= 0 else "BEARISH"
    else:
        bias = "NEUTRAL"

    return {
        "data_source": chain.get("data_source", "synthetic"),
        "spot": round(spot, 2),
        "net_gex": round(net_gex, 1),
        "vanna_exposure": round(net_vanna, 1),
        "charm_exposure": round(net_charm, 1),
        "zero_gamma_level": round(zero_level, 2) if zero_level else None,
        "regime": regime,
        "dealer_bias": bias,
        "per_strike": per_strike,
    }


def interpret_for_signal(gex: Dict[str, Any]) -> Dict[str, Any]:
    """Translate GEX analytics into a plain-language overlay for option signals."""
    if not gex or gex.get("data_source") in (None, "empty"):
        return {"gex_applicable": False, "note": "No option chain data available."}
    regime = gex.get("regime")
    bias = gex.get("dealer_bias")
    z = gex.get("zero_gamma_level")
    notes = []
    if regime == "POSITIVE":
        notes.append("Dealers LONG gamma — expect range-bound pinning; favor short premium / fade extremes.")
    elif regime == "NEGATIVE":
        notes.append("Dealers SHORT gamma — expect momentum acceleration; favor directional breakout buys.")
    if z:
        notes.append(f"Zero-Gamma flip at {z:.0f} (spot {gex.get('spot'):.0f}).")
    if gex.get("vanna_exposure", 0) > 0:
        notes.append("Positive Vanna — dealer hedging supports upside.")
    elif gex.get("vanna_exposure", 0) < 0:
        notes.append("Negative Vanna — dealer hedging pressures downside.")
    return {
        "gex_applicable": True,
        "regime": regime,
        "dealer_bias": bias,
        "confidence_adj": 6 if regime == "NEGATIVE" and bias in ("BULLISH", "BEARISH") else 3,
        "notes": notes,
    }
