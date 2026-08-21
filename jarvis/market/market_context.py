"""
JARVIS AI 3.0 — Multi-Timeframe Market Context Synthesizer.
Orchestrates Market Structure, Liquidity, Volatility, Momentum, and Session intelligence across multiple timeframes.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import pandas as pd

from jarvis.data.schemas import MarketContext
from jarvis.market.market_structure import MarketStructureEngine
from jarvis.market.liquidity import LiquidityEngine
from jarvis.market.volatility import VolatilityEngine
from jarvis.market.momentum import MomentumEngine
from jarvis.market.sessions import SessionEngine

class MarketContextEngine:
    def __init__(
        self,
        structure_engine: Optional[MarketStructureEngine] = None,
        liquidity_engine: Optional[LiquidityEngine] = None,
        volatility_engine: Optional[VolatilityEngine] = None,
        momentum_engine: Optional[MomentumEngine] = None
    ):
        self.structure_engine = structure_engine or MarketStructureEngine()
        self.liquidity_engine = liquidity_engine or LiquidityEngine()
        self.volatility_engine = volatility_engine or VolatilityEngine()
        self.momentum_engine = momentum_engine or MomentumEngine()

    def build_context(
        self,
        symbol: str,
        mtf_data: Dict[str, pd.DataFrame],
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0
    ) -> MarketContext:
        """
        Synthesizes multi-timeframe market data (D1, H4, H1, M15, M5) into a unified MarketContext object.
        """
        # Primary timeframe is H1, Setup is M15, Timing is M5, Context is H4, Macro is D1
        df_primary = mtf_data.get("primary", mtf_data.get("H1", pd.DataFrame()))
        df_macro = mtf_data.get("macro", mtf_data.get("D1", pd.DataFrame()))
        df_context = mtf_data.get("context", mtf_data.get("H4", pd.DataFrame()))
        df_setup = mtf_data.get("setup", mtf_data.get("M15", pd.DataFrame()))
        df_timing = mtf_data.get("timing", mtf_data.get("M5", pd.DataFrame()))

        if df_primary.empty:
            df_primary = list(mtf_data.values())[0] if mtf_data else pd.DataFrame()

        from jarvis.data.symbol_registry import resolve as _resolve_sym
        _spec = _resolve_sym(symbol)
        
        latest_close = float(df_primary["close"].iloc[-1]) if not df_primary.empty else 0.0
        bid = latest_close
        ask = latest_close + (current_spread_pips * _spec.pip_size)

        # 1. Structural Analysis (Primary & Setup timeframes)
        structure_primary = self.structure_engine.analyze_structure(df_primary)
        
        # 2. Liquidity & Sweep Analysis
        liquidity = self.liquidity_engine.analyze_liquidity(df_primary)

        # 3. Volatility & Spread Feasibility
        volatility = self.volatility_engine.analyze_volatility(
            df_primary,
            current_spread_pips=current_spread_pips,
            max_allowed_spread_pips=max_allowed_spread_pips
        )

        # 4. Multi-Factor Momentum Analysis
        momentum = self.momentum_engine.analyze_momentum(df_primary)

        # 5. Session Timing Context
        session = SessionEngine.get_current_session()

        # 6. Multi-Timeframe Alignment Matrix & Top-Down Weighted Score
        mtf_alignment = {}
        if not df_macro.empty:
            mtf_alignment["D1"] = self.structure_engine.analyze_structure(df_macro).bias
        if not df_context.empty:
            mtf_alignment["H4"] = self.structure_engine.analyze_structure(df_context).bias
        mtf_alignment["H1"] = structure_primary.bias
        if not df_setup.empty:
            mtf_alignment["M15"] = self.structure_engine.analyze_structure(df_setup).bias
        if not df_timing.empty:
            mtf_alignment["M5"] = self.structure_engine.analyze_structure(df_timing).bias

        # Top-down narrative weighting: D1 (40%), H4 (30%), H1 (20%), M15 (10%)
        def _score_bias(b: str) -> float:
            return 1.0 if b == "BULLISH" else (-1.0 if b == "BEARISH" else 0.0)

        weighted_score = (
            _score_bias(mtf_alignment.get("D1", "NEUTRAL")) * 0.40 +
            _score_bias(mtf_alignment.get("H4", "NEUTRAL")) * 0.30 +
            _score_bias(mtf_alignment.get("H1", "NEUTRAL")) * 0.20 +
            _score_bias(mtf_alignment.get("M15", "NEUTRAL")) * 0.10
        )
        mtf_confluence_pct = round(weighted_score * 100.0, 1)

        # 7. VWAP Calculation
        vwap = 0.0
        if not df_primary.empty and "volume" in df_primary.columns and "high" in df_primary.columns:
            typical_price = (df_primary["high"] + df_primary["low"] + df_primary["close"]) / 3
            vol = df_primary["volume"]
            if vol.sum() > 0:
                vwap_series = (typical_price * vol).cumsum() / vol.cumsum()
                vwap = float(vwap_series.iloc[-1]) if not vwap_series.isna().all() else 0.0

        # 8. Context Quality Score
        quality = 0.0
        available_tfs = sum(1 for d in [df_macro, df_context, df_primary, df_setup, df_timing] if not d.empty)
        quality += (available_tfs / 5.0) * 50.0
        if not df_primary.empty and len(df_primary) >= 50:
            quality += 30.0
        if not df_context.empty and len(df_context) >= 20:
            quality += 20.0
        context_quality = min(100.0, quality)

        return MarketContext(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            current_price=latest_close,
            bid=bid,
            ask=ask,
            vwap=round(vwap, 4),
            context_quality=round(context_quality, 1),
            structure=structure_primary,
            liquidity=liquidity,
            volatility=volatility,
            momentum=momentum,
            session=session,
            trend_score=mtf_confluence_pct,
            mtf_alignment=mtf_alignment
        )
