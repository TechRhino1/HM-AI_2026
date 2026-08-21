import os
import json
from typing import Dict, Any, List
from strategies.scalping_strategy import HighFrequencyScalpingEngine
from engines.orderflow_engine import InstitutionalVolumeOrderFlowEngine
from engines.amd_phase_engine import WyckoffAMDPhaseEngine

class MultiSymbolScreenerEngine:
    def __init__(
        self,
        mt5_client: Any,
        data_engine: Any,
        structure_engine: Any,
        trend_engine: Any,
        volatility_engine: Any,
        liquidity_engine: Any,
        regime_engine: Any,
        news_engine: Any,
        strategy_engine: Any,
        sl_tp_engine: Any,
        ai_decision_engine: Any,
        profiles: Dict[str, Any],
        logger: Any = None
    ):
        self.mt5_client = mt5_client
        self.data_engine = data_engine
        self.structure_engine = structure_engine
        self.trend_engine = trend_engine
        self.volatility_engine = volatility_engine
        self.liquidity_engine = liquidity_engine
        self.regime_engine = regime_engine
        self.news_engine = news_engine
        self.strategy_engine = strategy_engine
        self.sl_tp_engine = sl_tp_engine
        self.ai_decision_engine = ai_decision_engine
        self.orderflow_engine = InstitutionalVolumeOrderFlowEngine(logger=logger)
        self.amd_engine = WyckoffAMDPhaseEngine(logger=logger)
        self.profiles = profiles
        self.logger = logger
        self.scalp_engine = HighFrequencyScalpingEngine()

    def scan_all_opportunities(self, symbols: List[str]) -> List[Dict[str, Any]]:
        opportunities = []

        for symbol in symbols:
            try:
                resolved_symbol = self.mt5_client.resolve_symbol_name(symbol)
                sym_info = self.mt5_client.get_symbol_info(resolved_symbol)
                if not sym_info:
                    continue

                profile = self.profiles.get(resolved_symbol, self.profiles.get(symbol, {
                    "digits": 2 if ("XAU" in resolved_symbol or "BTC" in resolved_symbol or "GOLD" in resolved_symbol) else 5,
                    "max_allowed_spread_pips": 35.0,
                    "sl_atr_multiplier": 1.5,
                    "tp_atr_multiplier": 3.0
                }))

                mtf_data = self.data_engine.fetch_multi_timeframe_data(resolved_symbol)
                primary_df = mtf_data["primary"]
                macro_df = mtf_data["macro"]

                df_m5 = self.data_engine.fetch_rates(resolved_symbol, timeframe="M5", num_bars=60)

                macro_trend = self.trend_engine.analyze_trend(macro_df)
                htf_bias = macro_trend.get("classification", "NEUTRAL").replace("STRONG_", "").replace("MODERATE_", "")

                structure = self.structure_engine.analyze_structure(primary_df)
                trend = self.trend_engine.analyze_trend(primary_df, htf_bias=htf_bias)
                volatility = self.volatility_engine.analyze_volatility(primary_df, current_spread_pips=sym_info["spread_pips"], max_allowed_spread=profile.get("max_allowed_spread_pips", 35.0))
                liquidity = self.liquidity_engine.analyze_liquidity(primary_df, structure.get("swing_highs", []), structure.get("swing_lows", []))
                vol_profile = self.orderflow_engine.calculate_volume_profile(primary_df)
                order_flow = self.orderflow_engine.analyze_order_flow_imbalance(primary_df)

                # ICT / Wyckoff Accumulation-Manipulation-Distribution (AMD) Phase Intelligence
                amd_info = self.amd_engine.analyze_amd_phase(primary_df, structure, trend, volatility, orderflow=order_flow)

                scalp_info = self.scalp_engine.analyze_scalp_setup(df_m5, primary_df, structure, volatility)

                regime = self.regime_engine.classify_regime(structure, trend, volatility, liquidity)
                news = self.news_engine.evaluate_news_risk(resolved_symbol)
                strategy = self.strategy_engine.select_strategy(regime, structure, volatility, liquidity, scalp_info=scalp_info, amd_info=amd_info)

                current_price = sym_info["ask"] if strategy.get("recommended_action") == "BUY" else sym_info["bid"]
                sl_tp = self.sl_tp_engine.calculate_sl_tp(resolved_symbol, strategy.get("recommended_action"), current_price, structure, volatility, profile, regime=regime.get("regime", "STRONG_TREND_BULLISH"))

                decision = self.ai_decision_engine.evaluate_trade_opportunity(
                    resolved_symbol,
                    structure,
                    trend,
                    volatility,
                    liquidity,
                    news,
                    strategy,
                    sl_tp,
                    regime=regime,
                    orderflow=order_flow,
                    volume_profile=vol_profile
                )

                opportunities.append({
                    "symbol": resolved_symbol,
                    "raw_symbol": symbol,
                    "regime": regime.get("regime"),
                    "confidence": regime.get("confidence"),
                    "amd_phase": amd_info.get("phase"),
                    "amd_detail": amd_info.get("phase_detail"),
                    "target_pool": amd_info.get("target_pool"),
                    "strategy": strategy.get("strategy"),
                    "action": strategy.get("recommended_action"),
                    "decision": decision.get("decision"),
                    "trade_score": decision.get("trade_score"),
                    "ml_win_probability": decision.get("ml_win_probability", 0.65),
                    "price": current_price,
                    "sl": sl_tp.get("sl_price"),
                    "tp": sl_tp.get("tp1_price"),
                    "rr": sl_tp.get("rr_ratio"),
                    "spread": sym_info["spread_pips"],
                    "reasons": decision.get("reasons", []),
                    "reasons_not_to_trade": decision.get("reasons_not_to_trade", [])
                })
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error scanning opportunity for {symbol}: {e}")

        try:
            with open("opportunities.json", "w") as f:
                json.dump(opportunities, f, indent=2)
            
            # Generate Trade Plans synchronized with account equity & AI signals
            from engines.trade_plan_engine import TradePlanEngine
            acc_info = self.mt5_client.get_account_info()
            bal = acc_info.get("balance", 996.07)
            plan_eng = TradePlanEngine()
            plan_eng.generate_trade_plans(opportunities, account_balance=bal)
        except Exception:
            pass

        return opportunities
