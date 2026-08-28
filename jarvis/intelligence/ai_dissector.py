"""
JARVIS AI 4.0 — Real-Time AI Dissection Engine.
Breaks a trade setup into 7 independent pillars, scores each, and returns
a dissection confidence that directly predicts win probability.
Used to filter low-quality setups before execution — the core win-rate booster.
"""
from typing import Dict, Any, Tuple

class AIDissector:
    """
    Dissects a potential trade into 7 pillars. Each pillar contributes 0-15 pts.
    Total 0-105 normalized to 0-100. High score = high confluence = high win prob.
    Pillars:
      1. Structure (BOS/CHOCH, HH/HL, zones, OB/FVG)
      2. Momentum (trend_score, ADX, EMA stack)
      3. Liquidity (sweep, eq highs/lows, magnitude)
      4. Volatility (ATR state, spread)
      5. MTF Confluence (D1/H4/H1 alignment)
      6. Order Flow (delta, institutional activity)
      7. Risk/Reward (RR, EV, SL distance)
    """
    def dissect(
        self,
        context,
        regime,
        rr_ratio: float,
        ev: float,
        ai_score: float,
        calibrated_win_p: float,
    ) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        reasons: Dict[str, str] = {}

        # 1. Structure 0-15
        st = getattr(context, "structure", None)
        s = 0
        if st:
            if getattr(st, "bos", False): s += 5
            if getattr(st, "choch", False): s += 4
            bias = getattr(st, "bias", "NEUTRAL")
            if bias in ("BULLISH","BEARISH"): s += 3
            if getattr(st, "higher_highs", False) or getattr(st, "higher_lows", False): s += 2
            if getattr(st, "lower_highs", False) or getattr(st, "lower_lows", False): s += 2
            try:
                dz = getattr(st, "demand_zone", (0,0))
                sz = getattr(st, "supply_zone", (0,0))
                if dz[0] > 0 or sz[1] > 0: s += 1
            except Exception:
                pass
        s = min(15, s)
        scores["structure"] = s
        reasons["structure"] = f"BOS={getattr(st,'bos',False)} CHOCH={getattr(st,'choch',False)} bias={getattr(st,'bias','?')}"

        # 2. Momentum 0-15
        mo = getattr(context, "momentum", None)
        m = 0
        if mo:
            ts = float(getattr(mo, "trend_score", 0) or 0)
            adx = float(getattr(mo, "adx", 0) or 0)
            if abs(ts) >= 40: m += 6
            elif abs(ts) >= 20: m += 4
            elif abs(ts) >= 10: m += 2
            if adx >= 25: m += 5
            elif adx >= 20: m += 3
            elif adx >= 15: m += 1
            if abs(ts) >= 20 and adx >= 20: m += 2
        m = min(15, m)
        scores["momentum"] = m

        # 3. Liquidity 0-15
        liq = getattr(context, "liquidity", None)
        l = 0
        if liq:
            if getattr(liq, "sweep_detected", False):
                mag = float(getattr(liq, "sweep_magnitude", 0) or 0)
                l += 7
                if mag >= 1.0: l += 3
            if getattr(liq, "equal_highs", None) or getattr(liq, "equal_lows", None):
                l += 2
            if getattr(liq, "sweep_detected", False) and getattr(st, "bos", False):
                l += 3
        l = min(15, l)
        scores["liquidity"] = l

        # 4. Volatility 0-15
        vol = getattr(context, "volatility", None)
        v = 7
        if vol:
            atr = float(getattr(vol, "atr", 0) or 0)
            state = str(getattr(vol, "state", "NORMAL") or "NORMAL")
            spread_ok = not bool(getattr(vol, "is_excessive_spread", False))
            if state in ("NORMAL","EXPANSION"): v += 4
            elif state == "COMPRESSION": v += 1
            elif state == "EXTREME": v += 0
            if spread_ok: v += 4
        v = min(15, max(0, v))
        scores["volatility"] = v

        # 5. MTF 0-15
        mtf_score = float(getattr(context, "mtf_confluence_score", 0) or 0)
        mtf_align = getattr(context, "mtf_alignment", {}) or {}
        mf = 0
        if abs(mtf_score) >= 50: mf += 8
        elif abs(mtf_score) >= 30: mf += 5
        elif abs(mtf_score) >= 15: mf += 2
        bullish = sum(1 for v in mtf_align.values() if v == "BULLISH")
        bearish = sum(1 for v in mtf_align.values() if v == "BEARISH")
        if max(bullish, bearish) >= 3: mf += 5
        elif max(bullish, bearish) == 2: mf += 2
        mf = min(15, mf)
        scores["mtf"] = mf

        # 6. Order Flow 0-15
        of = getattr(context, "order_flow", {}) or {}
        o = 0
        if isinstance(of, dict):
            inst = bool(of.get("institutional_activity", False))
            delta = float(of.get("delta_score", 0) or 0)
            if inst: o += 6
            if abs(delta) >= 35: o += 5
            elif abs(delta) >= 20: o += 3
            if inst and abs(delta) >= 20: o += 2
        o = min(15, o)
        scores["orderflow"] = o

        # 7. Risk/Reward 0-15
        r = 0
        if rr_ratio >= 3.0: r += 7
        elif rr_ratio >= 2.5: r += 5
        elif rr_ratio >= 2.0: r += 3
        elif rr_ratio >= 1.5: r += 1
        if ev >= 5: r += 5
        elif ev >= 1: r += 3
        elif ev > 0: r += 1
        if ai_score >= 80: r += 3
        elif ai_score >= 70: r += 1
        r = min(15, r)
        scores["risk_reward"] = r

        total = sum(scores.values())
        dissection_score = round((total / 105.0) * 100.0, 1)
        if dissection_score >= 70:
            prob_boost = 0.03
            tier = "HIGH"
        elif dissection_score >= 55:
            prob_boost = 0.01
            tier = "MODERATE"
        else:
            prob_boost = 0.00
            tier = "WEAK"

        return {
            "scores": scores,
            "total": total,
            "dissection_score": dissection_score,
            "tier": tier,
            "prob_boost": prob_boost,
            "reasons": reasons,
        }

    def is_high_quality(self, dissection_score: float, symbol: str) -> Tuple[bool, str]:
        threshold = 40.0
        if dissection_score >= threshold:
            return True, f"Dissection {dissection_score:.1f} >= {threshold} ({symbol.upper()})"
        return False, f"Dissection {dissection_score:.1f} < {threshold} — low confluence"
