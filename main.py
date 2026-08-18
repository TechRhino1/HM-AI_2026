import os
import sys
import time
import json
import argparse
from typing import Dict, Any

from core.logger import SystemLogger
from core.mt5_client import MT5ExecutionEngine
from core.data_engine import MultiTimeframeDataEngine
from engines.market_structure import MarketStructureEngine
from engines.trend_engine import MultiFactorTrendEngine
from engines.volatility_engine import VolatilityEngine
from engines.liquidity_engine import LiquidityEngine
from engines.fvg_engine import FairValueGapEngine
from engines.regime_engine import MarketRegimeEngine
from engines.news_engine import NewsIntelligenceEngine
from engines.strategy_engine import AdaptiveStrategyEngine
from engines.dynamic_sl_tp import DynamicSLTPEngine
from engines.ai_decision_engine import AIDecisionEngine
from engines.risk_engine import RiskManagerEngine
from engines.trade_manager import TradeManagerEngine
from core.telegram_notifier import TelegramNotifier
from backtesting.engine import BacktestEngine
from ui.dashboard import TelemetryDashboard

def load_json_config(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return json.load(f)

from engines.screener_engine import MultiSymbolScreenerEngine
from engines.orderflow_engine import InstitutionalVolumeOrderFlowEngine

def run_telemetry_cycle(
    symbol: str,
    settings: Dict[str, Any],
    profiles: Dict[str, Any],
    mt5_client: MT5ExecutionEngine,
    data_engine: MultiTimeframeDataEngine,
    structure_engine: MarketStructureEngine,
    trend_engine: MultiFactorTrendEngine,
    volatility_engine: VolatilityEngine,
    liquidity_engine: LiquidityEngine,
    regime_engine: MarketRegimeEngine,
    news_engine: NewsIntelligenceEngine,
    orderflow_engine: InstitutionalVolumeOrderFlowEngine,
    strategy_engine: AdaptiveStrategyEngine,
    sl_tp_engine: DynamicSLTPEngine,
    ai_decision_engine: AIDecisionEngine,
    risk_engine: RiskManagerEngine,
    trade_manager: TradeManagerEngine,
    logger: SystemLogger
):
    # Multi-Symbol Opportunities Radar Scan (Scans & Ranks Forex, Gold, Crypto, Indices)
    screener = MultiSymbolScreenerEngine(
        mt5_client, data_engine, structure_engine, trend_engine, volatility_engine,
        liquidity_engine, regime_engine, news_engine, strategy_engine, sl_tp_engine,
        ai_decision_engine, profiles, logger
    )
    all_symbols = settings.get("trading", {}).get("allowed_symbols", ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"])
    opportunities = screener.scan_all_opportunities(all_symbols)

    resolved_symbol = mt5_client.resolve_symbol_name(symbol)
    account_info = mt5_client.get_account_info()

    # 1. Real-Time Omniscient Active Position Guardian (Monitors News, Volume Delta, Structure, Trailing SL)
    open_positions = mt5_client.get_open_positions()
    open_syms = set(p.get("symbol") for p in open_positions)
    open_syms.add(resolved_symbol)

    for sym_active in open_syms:
        try:
            mtf = data_engine.fetch_multi_timeframe_data(sym_active)
            p_df = mtf["primary"]
            s_info = structure_engine.analyze_structure(p_df)
            t_info = trend_engine.analyze_trend(p_df)
            v_info = volatility_engine.analyze_volatility(p_df)
            r_info = regime_engine.classify_regime(s_info, t_info, v_info, {})
            n_info = news_engine.evaluate_news_risk(sym_active)
            of_info = orderflow_engine.analyze_order_flow_imbalance(p_df)
            trade_manager.manage_active_positions(
                sym_active, r_info, s_info, v_info, news_info=n_info, orderflow_info=of_info
            )
        except Exception:
            pass

    # 2. Multi-Market Concurrent Trade Execution Pipeline
    # Iterates over ALL approved opportunities across Gold, Forex, Crypto, Indices
    approved_opps = [opp for opp in opportunities if opp.get("decision") == "APPROVED" and opp.get("action") in ["BUY", "SELL"]]
    
    # Sort approved opportunities by Trade Score descending
    approved_opps.sort(key=lambda x: x.get("trade_score", 0), reverse=True)

    max_allowed_positions = settings.get("risk", {}).get("max_open_positions", 2)
    for target_opp in approved_opps:
        if len(open_positions) >= max_allowed_positions:
            logger.info(f"Max active position capacity ({max_allowed_positions}) reached. Preserving margin for active trades.")
            break

        target_sym = target_opp.get("symbol")
        target_action = target_opp.get("action")
        target_sym_info = mt5_client.get_symbol_info(target_sym)

        if target_sym_info:
            target_profile = profiles.get(target_sym, profiles.get(target_opp.get("raw_symbol", ""), {"digits": 2 if ("XAU" in target_sym or "BTC" in target_sym or "GOLD" in target_sym) else 5, "max_allowed_spread_pips": 35.0}))
            risk_check = risk_engine.validate_risk_limits(account_info, open_positions, target_sym, target_sym_info.get("spread_pips", 0.0), target_profile)

            if risk_check["passed"]:
                t_price = target_sym_info["ask"] if target_action == "BUY" else target_sym_info["bid"]
                t_sl = target_opp.get("sl", t_price * 0.99)
                t_tp = target_opp.get("tp", t_price * 1.02)
                lots = risk_engine.calculate_position_size(
                    account_info=account_info,
                    symbol_info=target_sym_info,
                    sl_price=t_sl,
                    entry_price=t_price,
                    trade_score=target_opp.get("trade_score", 75.0),
                    win_probability=target_opp.get("ml_win_probability", 0.65),
                    regime=target_opp.get("regime", "NEUTRAL")
                )
                order_res = mt5_client.send_market_order(
                    symbol=target_sym,
                    order_type=target_action,
                    volume=lots,
                    sl_price=t_sl,
                    tp_price=t_tp,
                    comment=f"AI_{target_opp.get('strategy', 'MULTI')[:10]}"
                )
                if order_res and order_res.get("status") == "FILLED":
                    logger.info(f"MULTI-MARKET EXECUTION [{target_sym}] Ticket={order_res.get('ticket')} Type={target_action} Lots={lots} Price={t_price} Status=FILLED")
                    logger.log_execution(
                        ticket=order_res.get("ticket", 0),
                        symbol=target_sym,
                        order_type=target_action,
                        lots=lots,
                        price=order_res.get("price", t_price),
                        sl=t_sl,
                        tp=t_tp,
                        magic=mt5_client.magic_number,
                        status="FILLED",
                        comment=order_res.get("comment", "")
                    )
                    open_positions.append({"symbol": target_sym, "ticket": order_res.get("ticket")})
            else:
                logger.warning(f"RISK CHECK FAILED for {target_sym}: {risk_check.get('reasons')}")

def main():
    parser = argparse.ArgumentParser(description="Adaptive AI-Powered MT5 Automated Trading System")
    parser.add_argument("--mode", type=str, default="dry_run", choices=["dry_run", "live"], help="Execution mode (dry_run or live)")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Target trading symbol")
    parser.add_argument("--once", action="store_true", help="Run a single analysis sweep and exit")
    parser.add_argument("--backtest", action="store_true", help="Run historical backtest and exit")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings = load_json_config(os.path.join(base_dir, "config", "settings.json"))
    profiles = load_json_config(os.path.join(base_dir, "config", "symbol_profiles.json"))

    logger = SystemLogger(db_path=settings.get("logging", {}).get("db_path", "trades_log.db"))

    if args.backtest:
        logger.info(f"--- STARTING HISTORICAL BACKTEST FOR {args.symbol} ---")
        mt5_client = MT5ExecutionEngine(mode="dry_run", logger=logger)
        data_engine = MultiTimeframeDataEngine(mt5_client, logger)
        df_h1 = data_engine.fetch_rates(args.symbol, timeframe="H1", num_bars=500)
        
        bt = BacktestEngine(initial_balance=10000.0, risk_pct=0.5)
        res = bt.run_backtest(df_h1, symbol=args.symbol)
        
        logger.info("================================================================================")
        logger.info(f"                     BACKTEST RESULTS SUMMARY ({args.symbol})                  ")
        logger.info("================================================================================")
        for k, v in res["metrics"].items():
            logger.info(f"  {k}: {v}")
        logger.info(f"  Final Balance: ${res['final_balance']:,.2f}")
        logger.info("================================================================================")
        return

    mt5_client = MT5ExecutionEngine(
        magic_number=settings.get("trading", {}).get("magic_number", 888999),
        mode=args.mode,
        logger=logger
    )

    data_engine = MultiTimeframeDataEngine(mt5_client, logger)
    structure_engine = MarketStructureEngine()
    trend_engine = MultiFactorTrendEngine()
    volatility_engine = VolatilityEngine()
    liquidity_engine = LiquidityEngine()
    regime_engine = MarketRegimeEngine()
    news_cfg = settings.get("news", {})
    news_engine = NewsIntelligenceEngine(
        enabled=news_cfg.get("enabled", True),
        elevate_threshold_on_news_offline=news_cfg.get("elevate_threshold_on_news_offline", False),
        api_url=news_cfg.get("api_url", ""),
        buffer_before_mins=news_cfg.get("news_buffer_minutes_before", 30),
        buffer_after_mins=news_cfg.get("news_buffer_minutes_after", 30),
        logger=logger
    )
    orderflow_engine = InstitutionalVolumeOrderFlowEngine(logger=logger)
    strategy_engine = AdaptiveStrategyEngine()
    sl_tp_engine = DynamicSLTPEngine()
    ai_decision_engine = AIDecisionEngine(
        min_trade_score=settings.get("risk", {}).get("min_trade_score", 80.0),
        high_risk_trade_score=settings.get("risk", {}).get("high_risk_trade_score", 88.0)
    )
    risk_engine = RiskManagerEngine(settings, logger)
    trade_manager = TradeManagerEngine(mt5_client, logger)

    if args.once:
        run_telemetry_cycle(args.symbol, settings, profiles, mt5_client, data_engine, structure_engine, trend_engine, volatility_engine, liquidity_engine, regime_engine, news_engine, orderflow_engine, strategy_engine, sl_tp_engine, ai_decision_engine, risk_engine, trade_manager, logger)
        mt5_client.shutdown()
        return

    logger.info(f"Starting continuous telemetry loop for {args.symbol} in {args.mode.upper()} mode... Press Ctrl+C to terminate.")
    try:
        while True:
            run_telemetry_cycle(args.symbol, settings, profiles, mt5_client, data_engine, structure_engine, trend_engine, volatility_engine, liquidity_engine, regime_engine, news_engine, orderflow_engine, strategy_engine, sl_tp_engine, ai_decision_engine, risk_engine, trade_manager, logger)
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("System loop terminated by user.")
    finally:
        mt5_client.shutdown()

if __name__ == "__main__":
    main()
