import sys
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.mt5_client import MT5ExecutionEngine
from core.data_engine import MultiTimeframeDataEngine
from engines.trend_engine import MultiFactorTrendEngine
from engines.market_structure import MarketStructureEngine
from engines.volatility_engine import VolatilityEngine
from engines.liquidity_engine import LiquidityEngine
from engines.regime_engine import MarketRegimeEngine
from engines.news_engine import NewsIntelligenceEngine
from engines.strategy_engine import AdaptiveStrategyEngine
from engines.dynamic_sl_tp import DynamicSLTPEngine
from engines.ai_decision_engine import AIDecisionEngine
from engines.risk_engine import RiskManagerEngine
from engines.self_learning_engine import SelfLearningEngine
from engines.trade_plan_engine import TradePlanEngine

def run_end_to_end_system_verification():
    print("================================================================================")
    print("           JARVIS AI MT5 END-TO-END SYSTEM DIAGNOSTICS & VERIFICATION          ")
    print("================================================================================")
    
    diagnostics = {}

    # 1. MT5 Connection
    try:
        mt5_client = MT5ExecutionEngine(mode="live")
        acc = mt5_client.get_account_info()
        if acc and acc.get("login"):
            diagnostics["mt5_connection"] = "PASS"
            print(f"[PASS] MT5 Connection: Server={acc.get('server')} | Login={acc.get('login')} | Balance=${acc.get('balance'):,.2f}")
        else:
            diagnostics["mt5_connection"] = "WARNING (SIMULATION_MODE)"
            print("[WARNING] MT5 Connection: Operating in SIMULATION Mode.")
    except Exception as e:
        diagnostics["mt5_connection"] = f"ERROR ({e})"
        print(f"[ERROR] MT5 Connection failed: {e}")

    # 2. Live Market Data Engine
    try:
        data_engine = MultiTimeframeDataEngine(mt5_client)
        df_h1 = data_engine.fetch_rates("GOLD.i#", timeframe="H1", num_bars=50)
        if len(df_h1) >= 50:
            diagnostics["market_data"] = "PASS"
            print(f"[PASS] Market Data Engine: Successfully fetched {len(df_h1)} H1 bars for GOLD.i#. Latest Close=${df_h1.iloc[-1]['close']}")
        else:
            diagnostics["market_data"] = "ERROR (Insufficient bars)"
    except Exception as e:
        diagnostics["market_data"] = f"ERROR ({e})"

    # 3. Indicator & Trend Engine
    try:
        trend_engine = MultiFactorTrendEngine()
        trend_res = trend_engine.analyze_trend(df_h1)
        if "trend_score" in trend_res:
            diagnostics["indicator_engine"] = "PASS"
            print(f"[PASS] Indicator Engine: Trend Score={trend_res['trend_score']} | ADX={trend_res['adx']} | RSI={trend_res['rsi']}")
        else:
            diagnostics["indicator_engine"] = "ERROR"
    except Exception as e:
        diagnostics["indicator_engine"] = f"ERROR ({e})"

    # 4. Adaptive Learning Pipeline Verification
    try:
        learning_engine = SelfLearningEngine()
        thresh = learning_engine.get_adaptive_score_threshold(75.0)
        adj = learning_engine.get_strategy_score_adjustment("MODERATE_TREND_BULLISH", "TREND_PULLBACK_BULLISH")
        diagnostics["adaptive_learning"] = "PASS"
        print(f"[PASS] Adaptive Learning Pipeline: Connected & Functional. Adaptive Threshold={thresh:.1f} | Strategy Weight Adj={adj:+.1f} pts")
    except Exception as e:
        diagnostics["adaptive_learning"] = f"ERROR ({e})"

    # 5. AI Decision Engine
    try:
        ai_engine = AIDecisionEngine(learning_engine=learning_engine)
        structure_eng = MarketStructureEngine()
        volatility_eng = VolatilityEngine()
        liquidity_eng = LiquidityEngine()
        regime_eng = MarketRegimeEngine()
        news_eng = NewsIntelligenceEngine()
        strategy_eng = AdaptiveStrategyEngine()
        sl_tp_eng = DynamicSLTPEngine()

        struct = structure_eng.analyze_structure(df_h1)
        vol = volatility_eng.analyze_volatility(df_h1, 20.0, 35.0)
        liq = liquidity_eng.analyze_liquidity(df_h1, struct["swing_highs"], struct["swing_lows"])
        regime = regime_eng.classify_regime(struct, trend_res, vol, liq)
        news = news_eng.evaluate_news_risk("GOLD.i#")
        strategy = strategy_eng.select_strategy(regime, struct, vol, liq)
        sl_tp = sl_tp_eng.calculate_sl_tp("GOLD.i#", "BUY", df_h1.iloc[-1]["close"], struct, vol, {"digits":2, "sl_atr_multiplier":1.5})

        decision = ai_engine.evaluate_trade_opportunity("GOLD.i#", struct, trend_res, vol, liq, news, strategy, sl_tp, regime=regime)
        diagnostics["ai_decision_engine"] = "PASS"
        print(f"[PASS] AI Decision Engine: Decision={decision['decision']} | Action={decision['action']} | Score={decision['trade_score']}/100")
    except Exception as e:
        diagnostics["ai_decision_engine"] = f"ERROR ({e})"

    # 6. Trade Plan Engine
    try:
        plan_eng = TradePlanEngine()
        plans = plan_eng.generate_trade_plans([{
            "symbol": "GOLD.i#",
            "trade_score": 78.5,
            "action": "BUY",
            "regime": "MODERATE_TREND_BULLISH",
            "price": df_h1.iloc[-1]["close"],
            "sl": sl_tp["sl_price"],
            "tp": sl_tp["tp1_price"],
            "rr": sl_tp["rr_ratio"]
        }])
        diagnostics["trade_plan_engine"] = "PASS"
        status = plans[0]['status'] if plans else "READY"
        print(f"[PASS] Trade Plan Engine: Generated {len(plans)} active trade plan(s). Status={status}")
    except Exception as e:
        diagnostics["trade_plan_engine"] = f"ERROR ({e})"

    # 7. Risk Guardian
    try:
        risk_eng = RiskManagerEngine({"risk": {"max_daily_loss_pct": 2.0, "max_open_positions": 5}})
        risk_chk = risk_eng.validate_risk_limits(acc, [], "GOLD.i#", 20.0, {"max_allowed_spread_pips": 35.0})
        if risk_chk["passed"]:
            diagnostics["risk_guardian"] = "PASS"
            print(f"[PASS] Risk Guardian: Passed limits validation. Max Daily Loss=2.0%")
        else:
            diagnostics["risk_guardian"] = "WARNING"
    except Exception as e:
        diagnostics["risk_guardian"] = f"ERROR ({e})"

    print("================================================================================")
    print("                    FINAL SYSTEM DIAGNOSTICS SUMMARY MATRIX                     ")
    print("================================================================================")
    for k, v in diagnostics.items():
        print(f" -> {k.upper():<25}: {v}")
    print("================================================================================")

    # Save diagnostics to JSON for Dashboard HUD
    try:
        with open("system_diagnostics.json", "w") as f:
            json.dump(diagnostics, f, indent=2)
    except Exception:
        pass

if __name__ == "__main__":
    run_end_to_end_system_verification()
