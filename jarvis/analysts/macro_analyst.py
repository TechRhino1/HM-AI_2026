"""
JARVIS AI 3.0 — Macroeconomic Event & Directional Shock Analyst Agent.
Features:
- Live Macro News Shock Directional Prediction (USD Bullish/Bearish impact on Gold, FX, Crypto)
- High-Impact Economic Event Blackout Window Management
- Session-Aware Macro Liquidity Bias
"""
import time
from typing import Dict, Any, List, Optional
from jarvis.data.schemas import MarketContext, RegimeOutput, AnalystReport, AnalystRole
from jarvis.analysts.base_analyst import BaseAnalyst

class MacroAnalyst(BaseAnalyst):
    def __init__(self, news_calendar: Optional[List[Dict[str, Any]]] = None):
        super().__init__(AnalystRole.MACRO)
        self.news_calendar = news_calendar or []

    def analyze(self, context: MarketContext, regime: RegimeOutput) -> AnalystReport:
        t0 = time.perf_counter()
        evidence = []
        risk_factors = []

        score = 65.0
        bias = "NEUTRAL"
        sym = context.symbol.upper()

        # 1. Trading Session Liquidity Assessment
        session = context.session
        if session.is_prime_session:
            score += 15.0
            evidence.append(f"Institutional Prime Session Active ({session.current_session}).")
        else:
            evidence.append(f"Off-hours / Asian liquidity session ({session.current_session}).")
            if session.current_session == "ASIAN":
                risk_factors.append("Asian session low volume; high risk of false breakouts.")
                score -= 10.0

        # 2. Real-Time Macro News Directional Shock Scoring
        if not self.news_calendar:
            try:
                from jarvis.market.news import GLOBAL_NEWS_ENGINE
                active_news = GLOBAL_NEWS_ENGINE.get_news_calendar()
            except Exception:
                active_news = []
        else:
            active_news = self.news_calendar

        usd_bull_shock = False
        usd_bear_shock = False

        for item in active_news:
            curr = item.get("currency", "")
            impact = item.get("impact", "")
            actual_str = str(item.get("actual", ""))
            fcst_str = str(item.get("forecast", ""))

            if curr == "USD" and impact == "HIGH":
                try:
                    act = float(actual_str.replace("%", "").replace("K", "").replace("M", "").strip())
                    fcst = float(fcst_str.replace("%", "").replace("K", "").replace("M", "").strip())
                    if act > fcst:
                        usd_bull_shock = True
                        evidence.append(f"Macro Shock: Stronger USD Event ({item.get('event')} {actual_str} vs {fcst_str} fcst).")
                    elif act < fcst:
                        usd_bear_shock = True
                        evidence.append(f"Macro Shock: Weaker USD Event ({item.get('event')} {actual_str} vs {fcst_str} fcst).")
                except Exception:
                    usd_bull_shock = True
                    evidence.append(f"Macro Shock: Hawkish USD Policy Bias detected ({item.get('event')}).")

        # 3. Directional Bias Mapping for Target Asset
        if any(k in sym for k in ["XAU", "GOLD", "EUR", "GBP", "BTC"]):
            if usd_bull_shock:
                # Strong USD puts heavy downward pressure on Gold & Foreign Currencies
                bias = "BEARISH"
                score += 20.0
                evidence.append(f"Macro Directional Forecast: Strong USD yield pressure triggers institutional SELL bias on {sym}.")
            elif usd_bear_shock:
                bias = "BULLISH"
                score += 20.0
                evidence.append(f"Macro Directional Forecast: Weak USD sentiment triggers institutional BUY impulse on {sym}.")
        elif "USDJPY" in sym or "USDCAD" in sym:
            if usd_bull_shock:
                bias = "BULLISH"
                score += 20.0
                evidence.append(f"Macro Directional Forecast: Strong USD rally triggers BUY bias on {sym}.")
            elif usd_bear_shock:
                bias = "BEARISH"
                score += 20.0
                evidence.append(f"Macro Directional Forecast: Weaker USD triggers SELL bias on {sym}.")

        # 3b. Fallback: No macro shock — align with structure bias
        # "No news is good news" — absence of macro headwinds supports trend continuation.
        if bias == "NEUTRAL" and not usd_bull_shock and not usd_bear_shock:
            structure_bias = context.structure.bias
            if structure_bias in ("BULLISH", "BEARISH"):
                bias = structure_bias
                evidence.append(f"Macro: No active macro headwinds — aligning with {structure_bias} structure bias.")

        # 4. Check regime event risk / blackout window
        if regime.primary_regime.value == "EVENT_RISK":
            score = 30.0
            risk_factors.append("High-impact economic event active — wide spreads and slippage expected.")

        final_score = min(100.0, max(0.0, score))
        confidence = min(0.95, max(0.40, final_score / 100.0))
        elapsed = (time.perf_counter() - t0) * 1000.0

        return AnalystReport(
            role=self.role,
            symbol=context.symbol,
            bias=bias,
            score=round(final_score, 1),
            confidence=round(confidence, 2),
            evidence=evidence,
            risk_factors=risk_factors,
            execution_time_ms=round(elapsed, 2),
            metadata={"session": session.current_session, "is_prime": session.is_prime_session, "usd_bull_shock": usd_bull_shock}
        )
