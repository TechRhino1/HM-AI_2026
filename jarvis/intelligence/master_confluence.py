"""
JARVIS AI 4.0 — Master Confluence Engine.
Synthesizes PROVEN combinations from top trading masters — the highest win-rate
stacks documented over 100 years, verified by backtests and audited track records.
Sources researched (2026):
- Wyckoff + ICT/SMC fusion: "strongest approach that exists"
- Mark Minervini SEPA + VCP: 8-point Trend Template + VCP, audited 255% and 334.8%
- ICT Core 5: Market Structure + Liquidity + FVG + Kill Zones + Displacement
- ICT Silver Bullet: sweep + displacement + FVG inside Kill Zone — 50-65% win
- Triple Confluence: Breaker Block + FVG + HTF Order Block — "probability is absurd"
"""
from typing import Dict, Any
import logging

logger = logging.getLogger("JARVIS_MasterConfluence")

class MasterConfluenceEngine:
    def score(self, context, regime, rr_ratio: float, ai_score: float, mtf_data: Dict[str, Any] = None) -> Dict[str, Any]:
        breakdown: Dict[str, float] = {}
        details: Dict[str, str] = {}
        try:
            reg = str(getattr(regime, "primary_regime", "RANGE"))
            reg = reg.upper() if isinstance(regime.primary_regime, str) else getattr(regime.primary_regime, "value", "RANGE").upper()
            st = getattr(context, "structure", None)
            liq = getattr(context, "liquidity", None)
            wyck = 0
            if "TREND_BULL" in reg and getattr(liq, "sweep_detected", False):
                wyck += 8
                details["wyckoff"] = "TREND_BULL + sweep (Wyckoff Spring)"
            elif "TREND_BEAR" in reg and getattr(liq, "sweep_detected", False):
                wyck += 8
                details["wyckoff"] = "TREND_BEAR + sweep (Wyckoff Upthrust)"
            elif "RANGE" in reg:
                wyck += 4
                details["wyckoff"] = "RANGE — Wyckoff consolidation"
            if getattr(st, "bos", False): wyck += 6
            if getattr(st, "choch", False): wyck += 4
            if getattr(st, "bias", "NEUTRAL") != "NEUTRAL": wyck += 2
        except Exception:
            wyck = 0
        wyck = min(20, wyck)
        breakdown["wyckoff_ict_fusion"] = wyck
        try:
            mo = getattr(context, "momentum", None)
            ts = float(getattr(mo, "trend_score", 0) or 0)
            adx = float(getattr(mo, "adx", 0) or 0)
            trend = 0
            if ts > 0 and adx >= 20: trend += 8
            elif ts > 0: trend += 4
            if adx >= 25: trend += 4
            elif adx >= 15: trend += 2
            if "TREND_BULL" in reg and ts >= 20: trend += 4
            elif "TREND_BEAR" in reg and ts <= -20: trend += 4
            if getattr(st, "bos", False) and abs(ts) >= 20: trend += 4
        except Exception:
            trend = 0
        trend = min(20, trend)
        breakdown["minervini_trend_template"] = trend
        try:
            import pandas as pd
            df = None
            if mtf_data and isinstance(mtf_data, dict):
                df = mtf_data.get("primary", None)
                if df is None:
                    for v in mtf_data.values():
                        if isinstance(v, pd.DataFrame) and not v.empty:
                            df = v
                            break
            vcp = 0
            if df is not None and len(df) >= 30:
                closes = df["close"].values[-30:]
                ranges = []
                for i in range(3):
                    seg = closes[i*10:(i+1)*10]
                    ranges.append(float(max(seg) - min(seg)))
                if len(ranges) == 3 and ranges[0] > 0:
                    if ranges[1] < ranges[0] * 0.85 and ranges[2] < ranges[1] * 0.85:
                        vcp += 12
                        details["vcp"] = f"VCP {ranges[0]:.2f}→{ranges[1]:.2f}→{ranges[2]:.2f}"
                    elif ranges[1] < ranges[0] and ranges[2] < ranges[1]:
                        vcp += 6
                        details["vcp"] = f"soft VCP {ranges[0]:.2f}→{ranges[1]:.2f}→{ranges[2]:.2f}"
                    if vcp > 0 and getattr(st, "bos", False): vcp += 4
                    if vcp > 0 and rr_ratio >= 2.0: vcp += 4
            vol = getattr(context, "volatility", None)
            if vcp == 0 and vol and str(getattr(vol, "state", "")) == "COMPRESSION":
                vcp += 6
                details["vcp"] = "COMPRESSION proxy for VCP"
        except Exception:
            vcp = 0
        vcp = min(20, vcp)
        breakdown["vcp"] = vcp
        try:
            sess = getattr(context, "session", None)
            hour = int(getattr(sess, "utc_hour", 12) or 12)
            is_prime = bool(getattr(sess, "is_prime_session", False))
            kill = 0
            if is_prime:
                kill += 8
                details["killzone"] = f"prime hour={hour}"
                if hour in (3, 10, 14): kill += 6
            liq = getattr(context, "liquidity", None)
            mo = getattr(context, "momentum", None)
            disp = False
            if mo and float(getattr(mo, "adx", 0) or 0) >= 25 and getattr(st, "bos", False):
                disp = True
            if getattr(liq, "sweep_detected", False) and disp:
                kill += 6
        except Exception:
            kill = 0
        kill = min(20, kill)
        breakdown["ict_killzone_amd"] = kill
        try:
            triple = 0
            has_fvg = False
            has_ob = False
            has_breaker = False
            if st:
                fvgs = getattr(st, "fair_value_gaps", []) or []
                if len(fvgs) > 0: has_fvg = True; triple += 7
                obs = getattr(st, "order_blocks", []) or []
                if len(obs) > 0: has_ob = True; triple += 7
                if getattr(st, "bos", False) and getattr(st, "choch", False): has_breaker = True; triple += 6
                elif getattr(st, "bos", False): triple += 3
            mtf_align = getattr(context, "mtf_alignment", {}) or {}
            bullish = sum(1 for v in mtf_align.values() if v == "BULLISH")
            bearish = sum(1 for v in mtf_align.values() if v == "BEARISH")
            if max(bullish, bearish) >= 3 and (has_fvg or has_ob): triple += 4
            if has_fvg and has_ob and has_breaker: triple = 20
        except Exception:
            triple = 0
        triple = min(20, triple)
        breakdown["triple_confluence"] = triple
        total = sum(breakdown.values())
        if total >= 75: tier, boost = "ELITE", 0.05
        elif total >= 60: tier, boost = "HIGH", 0.03
        elif total >= 45: tier, boost = "MODERATE", 0.01
        elif total >= 30: tier, boost = "LOW", 0.00
        else: tier, boost = "WEAK", 0.00
        return {"breakdown": breakdown, "total": total, "tier": tier, "prob_boost": boost, "details": details}
