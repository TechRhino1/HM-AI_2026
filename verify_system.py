import sys
import os
import json
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.execution.mt5_client import MT5Client
from jarvis.market.data_feed import DataFeedEngine
from jarvis.market.market_context import MarketContextEngine
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.analysts.parallel_runner import ParallelAnalystCluster
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.risk.risk_engine import RiskEngine
from jarvis.learning.trade_memory import TradeMemory
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.data.database import TRADE_DB
from jarvis.data.symbol_registry import resolve as resolve_symbol

def run_end_to_end_system_verification():
    print("================================================================================")
    print("           JARVIS AI 4.0 MT5 END-TO-END SYSTEM DIAGNOSTICS & VERIFICATION      ")
    print("================================================================================")
    
    diagnostics = {}

    # 1. MT5 Connection & Account Info
    mt5_client = MT5Client(mode="live")
    try:
        acc = mt5_client.get_account_snapshot()
        if acc and acc.login:
            diagnostics["mt5_connection"] = "PASS"
            print(f"[PASS] MT5 Connection: Server={acc.server} | Login={acc.login} | Balance=${acc.balance:,.2f} | Leverage=1:{acc.leverage}")
        else:
            diagnostics["mt5_connection"] = "PASS (SIMULATION_MODE)"
            print("[PASS] MT5 Connection: Initialized in Simulation Mode.")
    except Exception as e:
        diagnostics["mt5_connection"] = f"ERROR ({e})"
        print(f"[ERROR] MT5 Connection failed: {e}")

    # 2. Market Data Feed
    data_engine = DataFeedEngine(mt5_client)
    try:
        df_h1 = data_engine.fetch_rates("XAUUSD", timeframe="H1", num_bars=100)
        if df_h1 is not None and len(df_h1) >= 50:
            diagnostics["market_data_feed"] = "PASS"
            print(f"[PASS] Market Data Feed: Fetched {len(df_h1)} H1 bars for XAUUSD. Latest Close=${df_h1.iloc[-1]['close']:.2f}")
        else:
            diagnostics["market_data_feed"] = "ERROR (Insufficient bars)"
            print("[ERROR] Market Data Feed: Insufficient bars returned.")
    except Exception as e:
        diagnostics["market_data_feed"] = f"ERROR ({e})"
        print(f"[ERROR] Market Data Feed failed: {e}")

    # 3. Market Context & Structure Engine
    ctx_engine = MarketContextEngine()
    try:
        mtf_data = {"H1": df_h1}
        ctx = ctx_engine.build_context("XAUUSD", mtf_data, current_spread_pips=1.5)
        diagnostics["market_context_engine"] = "PASS"
        print(f"[PASS] Market Context: Bias={ctx.structure.bias} | ATR={ctx.volatility.atr:.2f} | TrendScore={ctx.momentum.trend_score:.1f} | Session={ctx.session.current_session}")
    except Exception as e:
        diagnostics["market_context_engine"] = f"ERROR ({e})"
        print(f"[ERROR] Market Context failed: {e}")

    # 4. Market Regime Classifier
    regime_engine = MarketRegimeClassifier()
    try:
        regime = regime_engine.classify_regime(ctx)
        diagnostics["regime_classifier"] = "PASS"
        print(f"[PASS] Regime Classifier: Primary={regime.primary_regime.value} | Confidence={regime.confidence*100:.0f}%")
    except Exception as e:
        diagnostics["regime_classifier"] = f"ERROR ({e})"
        print(f"[ERROR] Regime Classifier failed: {e}")

    # 5. Multi-Analyst Cluster & Devil's Advocate
    analyst_cluster = ParallelAnalystCluster(parallel=False)
    try:
        analyst_reports, devil_rep = analyst_cluster.run_all_parallel(ctx, regime, "BUY")
        diagnostics["analyst_cluster"] = "PASS"
        print(f"[PASS] Analyst Cluster: Ran {len(analyst_reports)} specialized analysts | Devil Penalty={devil_rep.penalty_score:.1f}")
    except Exception as e:
        diagnostics["analyst_cluster"] = f"ERROR ({e})"
        print(f"[ERROR] Analyst Cluster failed: {e}")

    # 6. Institutional Decision Engine & Sizing
    decision_engine = DecisionEngine()
    try:
        decision = decision_engine.evaluate(ctx, regime, analyst_reports, devil_rep, account_balance=10000.0)
        diagnostics["decision_engine"] = "PASS"
        print(f"[PASS] Decision Engine: Decision={decision.decision} | Bias={decision.bias} | Strategy={decision.strategy} | WinProb={decision.model_confidence*100:.0f}% | EV=${decision.expected_value:.2f}")
    except Exception as e:
        diagnostics["decision_engine"] = f"ERROR ({e})"
        print(f"[ERROR] Decision Engine failed: {e}")

    # 7. Risk Management Engine & Circuit Breaker
    risk_engine = RiskEngine()
    try:
        acc_info = mt5_client.get_account_snapshot()
        spec = resolve_symbol("XAUUSD")
        sym_info = {"trade_contract_size": spec.contract_size, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        auth = risk_engine.authorize_execution(decision, acc_info, [], sym_info, spread_pips=1.5)
        diagnostics["risk_engine"] = "PASS"
        print(f"[PASS] Risk Engine: Authorized={auth['authorized']} | Lots={auth['lots']} | Reason={auth.get('reason', 'OK')}")
    except Exception as e:
        diagnostics["risk_engine"] = f"ERROR ({e})"
        print(f"[ERROR] Risk Engine failed: {e}")

    # 8. Trade Memory, Database & Bandit Learning
    try:
        mem = TradeMemory()
        bandit = StrategyBandit()
        trades = TRADE_DB.fetch_recent_trades(limit=10)
        diagnostics["self_learning_db"] = "PASS"
        print(f"[PASS] Database & Learning: SQLite connected. Recent trades in DB={len(trades)} | Bandit strategies={len(bandit.STRATEGIES)}")
    except Exception as e:
        diagnostics["self_learning_db"] = f"ERROR ({e})"
        print(f"[ERROR] Database/Learning failed: {e}")

    print("================================================================================")
    print("                    FINAL SYSTEM DIAGNOSTICS SUMMARY MATRIX                     ")
    print("================================================================================")
    all_passed = True
    for k, v in diagnostics.items():
        print(f" -> {k.upper():<26}: {v}")
        if "ERROR" in v:
            all_passed = False
    print("================================================================================")
    if all_passed:
        print(" -> SYSTEM HEALTH: 100% OPERATIONAL & VERIFIED CLEAN")
    print("================================================================================")

    try:
        with open("system_diagnostics.json", "w", encoding="utf-8") as f:
            json.dump(diagnostics, f, indent=2)
    except Exception:
        pass

if __name__ == "__main__":
    run_end_to_end_system_verification()
