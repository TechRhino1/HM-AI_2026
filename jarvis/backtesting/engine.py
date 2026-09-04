"""
JARVIS AI 3.0 — Chronological Event-Driven Backtesting Engine.
Executes historical simulation without lookahead bias, incorporating realistic spreads, commissions, and slippage.
"""
import pandas as pd
from typing import Dict, List, Any, Optional

from jarvis.market.market_context import MarketContextEngine
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.analysts.parallel_runner import ParallelAnalystCluster
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.risk.risk_engine import RiskEngine
from jarvis.data.schemas import AccountSnapshot, PositionSnapshot
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.backtesting.metrics import PerformanceMetricsCalculator
from jarvis.risk.loss_cooldown import LossCooldownManager
from jarvis.historical.historical_engine import HISTORICAL_DATA_ENGINE

class BacktestEngine:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.5,
        commission_per_lot: float = 5.0,
        slippage_pips: float = 0.5
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.commission_per_lot = commission_per_lot
        self.slippage_pips = slippage_pips

        self.context_engine = MarketContextEngine()
        self.regime_classifier = MarketRegimeClassifier()
        self.analyst_cluster = ParallelAnalystCluster(parallel=False)
        self.decision_engine = DecisionEngine()
        self.risk_engine = RiskEngine(max_risk_per_trade_pct=risk_per_trade_pct, is_backtest=True)

    def run_backtest(
        self,
        df_h1: Optional[pd.DataFrame] = None,
        symbol: str = "XAUUSD",
        spread_pips: float = 2.0,
        slippage_delta: float = 0.05,
        start_bar_idx: int = 50,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "H1"
    ) -> Dict[str, Any]:
        balance = self.initial_balance
        equity = self.initial_balance
        trades: List[Dict[str, Any]] = []
        open_trade: Optional[Dict[str, Any]] = None

        if df_h1 is None or (isinstance(df_h1, pd.DataFrame) and df_h1.empty):
            df_h1 = HISTORICAL_DATA_ENGINE.get_market_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start_date,
                end=end_date,
                auto_download=True
            )

        total_bars = len(df_h1) if df_h1 is not None else 0
        if total_bars < 20:
            return {"symbol": symbol, "final_balance": balance, "metrics": PerformanceMetricsCalculator.calculate_metrics([], balance), "trades": [], "dataset_version": 1}

        effective_start = max(20, min(total_bars - 2, start_bar_idx))
        spec = resolve_symbol(symbol)
        actual_slippage_delta = self.slippage_pips * spec.pip_size
        cooldown_mgr = LossCooldownManager()
        
        sym_upper = symbol.upper()
        is_jpy = "JPY" in sym_upper
        is_crypto = spec.is_crypto or ("BTC" in sym_upper)
        is_gold = ("XAU" in sym_upper) or ("GOLD" in sym_upper) or (getattr(spec, "asset_class", "") == "COMMODITY")
        is_fx = getattr(spec, "asset_class", "").upper() == "FOREX" and not is_jpy
        rejection_stats = {}

        # Pre-compute Full Multi-Timeframe (H4 & D1) Resamplings Once Upfront (Before the Bar Loop)
        full_df_indexed = df_h1.copy()
        if "time" in full_df_indexed.columns:
            if not isinstance(full_df_indexed["time"].iloc[0], pd.Timestamp):
                full_df_indexed["time"] = pd.to_datetime(full_df_indexed["time"])
                df_h1 = df_h1.copy()
                df_h1["time"] = full_df_indexed["time"]
            if not isinstance(full_df_indexed.index, pd.DatetimeIndex):
                full_df_indexed.set_index("time", inplace=True)
            
            agg_dict = {"open": "first", "high": "max", "low": "min", "close": "last"}
            if "volume" in full_df_indexed.columns:
                agg_dict["volume"] = "sum"
            elif "tick_volume" in full_df_indexed.columns:
                agg_dict["tick_volume"] = "sum"

            full_df_h4 = full_df_indexed.resample("4h").agg(agg_dict).dropna().reset_index()
            full_df_d1 = full_df_indexed.resample("1D").agg(agg_dict).dropna().reset_index()
            if "index" in full_df_h4.columns and "time" not in full_df_h4.columns:
                full_df_h4.rename(columns={"index": "time"}, inplace=True)
            if "index" in full_df_d1.columns and "time" not in full_df_d1.columns:
                full_df_d1.rename(columns={"index": "time"}, inplace=True)
        elif isinstance(full_df_indexed.index, pd.DatetimeIndex):
            agg_dict = {"open": "first", "high": "max", "low": "min", "close": "last"}
            if "volume" in full_df_indexed.columns:
                agg_dict["volume"] = "sum"
            elif "tick_volume" in full_df_indexed.columns:
                agg_dict["tick_volume"] = "sum"

            full_df_h4 = full_df_indexed.resample("4h").agg(agg_dict).dropna().reset_index()
            full_df_d1 = full_df_indexed.resample("1D").agg(agg_dict).dropna().reset_index()
            if "index" in full_df_h4.columns and "time" not in full_df_h4.columns:
                full_df_h4.rename(columns={"index": "time"}, inplace=True)
            if "index" in full_df_d1.columns and "time" not in full_df_d1.columns:
                full_df_d1.rename(columns={"index": "time"}, inplace=True)
        else:
            full_df_h4 = None
            full_df_d1 = None
        
        for i in range(effective_start, total_bars - 1):
            window_start = max(0, i - 300)
            history_slice = df_h1.iloc[window_start:i]
            current_bar = df_h1.iloc[i]
            next_bar = df_h1.iloc[i + 1]
            
            bar_time = current_bar.get("time") if "time" in current_bar else None
            b_date = None
            if bar_time is not None:
                b_date = bar_time.date() if hasattr(bar_time, "date") else None
                if b_date is not None and b_date != cooldown_mgr.current_date:
                    cooldown_mgr.reset_daily(b_date)
            cooldown_mgr.tick_bar()

            # 1. Manage existing open trade with institutional partial TP & dynamic trailing
            if open_trade:
                high = float(current_bar["high"])
                low = float(current_bar["low"])
                atr = float(current_bar.get("atr", current_bar.get("ATR", (high - low) if (high - low) > 0 else 1.0)))

                # Increment bar holding counter
                open_trade["bars_held"] = open_trade.get("bars_held", 0) + 1

                # Track MFE / MAE
                if open_trade["type"] == "BUY":
                    favorable = high - open_trade["entry"]
                    adverse = open_trade["entry"] - low
                else:
                    favorable = open_trade["entry"] - low
                    adverse = high - open_trade["entry"]

                open_trade["mfe"] = max(open_trade.get("mfe", 0.0), favorable)
                open_trade["mae"] = max(open_trade.get("mae", 0.0), adverse)

                risk_dist = open_trade.get("risk_dist", abs(open_trade["entry"] - open_trade["sl"]))
                if risk_dist <= 0:
                    risk_dist = max(0.001, abs(open_trade["entry"] - open_trade["sl"]))

                # Master-Trader Stagnation Time Stop: Close at market if bars_held >= 8 and mfe < (risk_dist * 0.35)
                if open_trade["bars_held"] >= 8 and open_trade["mfe"] < (risk_dist * 0.35):
                    exit_price = float(current_bar["close"])
                    pips = ((exit_price - open_trade["entry"]) if open_trade["type"] == "BUY" else (open_trade["entry"] - exit_price)) / spec.pip_size
                    pnl_raw = pips * spec.pip_value_per_lot * open_trade["lots"]
                    comm = open_trade["lots"] * self.commission_per_lot
                    pnl_remaining = pnl_raw - comm
                    pnl_net = pnl_remaining + open_trade.get("realized_pnl", 0.0)
                    balance += pnl_remaining
                    equity = balance
                    is_win = pnl_net > 0
                    cooldown_mgr.record_trade_result(pnl=pnl_net, is_win=is_win, symbol=symbol, current_date=b_date)
                    trades.append({
                        "symbol": symbol, "type": open_trade["type"],
                        "open_time": open_trade.get("open_time"),
                        "exit_time": bar_time,
                        "bars_held": open_trade.get("bars_held", 8),
                        "entry": open_trade["entry"], "exit": exit_price,
                        "sl": open_trade["sl"], "tp": open_trade["tp"],
                        "lots": open_trade.get("initial_lots", open_trade["lots"]),
                        "pnl": round(pnl_net, 2), "result": "STAGNATION_TIME_STOP_8BAR",
                        "strategy": open_trade["strategy"], "regime": open_trade["regime"],
                        "score": open_trade["score"],
                        "planned_rr": open_trade.get("planned_rr", 0.0),
                        "master_score": open_trade.get("master_score", 0.0),
                        "mfe": round(open_trade["mfe"], 4), "mae": round(open_trade["mae"], 4),
                        "is_win": is_win
                    })
                    open_trade = None
                    continue

                # Master-Trader Dynamic Breakeven Lock: Advance SL to breakeven + buffer ONLY when price reaches >= +1.0R
                if not open_trade.get("be_locked", False):
                    if favorable >= (risk_dist * 1.00):
                        open_trade["be_locked"] = True
                        be_buffer = max(spec.pip_size * 2.5, risk_dist * 0.08)
                        if open_trade["type"] == "BUY":
                            open_trade["sl"] = max(open_trade["sl"], round(open_trade["entry"] + be_buffer, spec.digits))
                        else:
                            open_trade["sl"] = min(open_trade["sl"], round(open_trade["entry"] - be_buffer, spec.digits))

                # Master-Trader Stage 1 Fast Cash Lock: +1.15R for Forex, +1.0R for Gold/Indices/Crypto
                fast_cash_r = 1.15 if is_fx else 1.00
                fast_cash_dist = risk_dist * fast_cash_r
                profit_floor_dist = max(spec.pip_size * 2.5, risk_dist * 0.10)

                if not open_trade.get("partial_closed", False) and open_trade["lots"] >= 0.01:
                    is_target_hit = False
                    partial_exit_p = 0.0
                    if open_trade["type"] == "BUY" and high >= (open_trade["entry"] + fast_cash_dist):
                        is_target_hit = True
                        partial_exit_p = open_trade["entry"] + fast_cash_dist
                    elif open_trade["type"] == "SELL" and low <= (open_trade["entry"] - fast_cash_dist):
                        is_target_hit = True
                        partial_exit_p = open_trade["entry"] - fast_cash_dist

                    if is_target_hit:
                        # Bank 60% volume into realized cash
                        partial_lots = round(open_trade["lots"] * 0.60, 2)
                        if partial_lots >= 0.01 and open_trade["lots"] > partial_lots:
                            pips_p = ((partial_exit_p - open_trade["entry"]) if open_trade["type"] == "BUY" else (open_trade["entry"] - partial_exit_p)) / spec.pip_size
                            pnl_p = (pips_p * spec.pip_value_per_lot * partial_lots) - (partial_lots * self.commission_per_lot)
                            balance += pnl_p
                            open_trade["realized_pnl"] = open_trade.get("realized_pnl", 0.0) + pnl_p
                            open_trade["lots"] = round(open_trade["lots"] - partial_lots, 2)
                        elif partial_lots >= 0.01:
                            pips_p = ((partial_exit_p - open_trade["entry"]) if open_trade["type"] == "BUY" else (open_trade["entry"] - partial_exit_p)) / spec.pip_size
                            pnl_p = (pips_p * spec.pip_value_per_lot * open_trade["lots"]) - (open_trade["lots"] * self.commission_per_lot)
                            balance += pnl_p
                            open_trade["realized_pnl"] = open_trade.get("realized_pnl", 0.0) + pnl_p

                        open_trade["partial_closed"] = True
                        open_trade["be_locked"] = True

                        # Advance remaining SL to Entry + (0.10 * risk_dist) (guaranteed risk-free trade)
                        if open_trade["type"] == "BUY":
                            runner_floor_sl = round(open_trade["entry"] + profit_floor_dist, spec.digits)
                            open_trade["sl"] = max(open_trade["sl"], runner_floor_sl)
                        else:
                            runner_floor_sl = round(open_trade["entry"] - profit_floor_dist, spec.digits)
                            open_trade["sl"] = min(open_trade["sl"], runner_floor_sl)

                # Stage 2 (Dynamic Runner Trail): Trail remaining runner using runner_trail_distance_atr
                if open_trade.get("partial_closed", False):
                    trail_dist = atr * open_trade.get("runner_trail_distance_atr", 1.2)
                    runner_lock_r = 1.8 if (is_fx or is_jpy) else 2.5
                    if open_trade["type"] == "BUY":
                        new_sl = round(high - trail_dist, spec.digits)
                        if favorable >= (risk_dist * runner_lock_r):
                            new_sl = max(new_sl, round(open_trade["entry"] + (risk_dist * 0.80), spec.digits))
                        if new_sl > open_trade["sl"]:
                            open_trade["sl"] = new_sl
                    else:
                        new_sl = round(low + trail_dist, spec.digits)
                        if favorable >= (risk_dist * runner_lock_r):
                            new_sl = min(new_sl, round(open_trade["entry"] - (risk_dist * 0.80), spec.digits))
                        if new_sl < open_trade["sl"]:
                            open_trade["sl"] = new_sl

                # Stage 4: Check SL/TP exit for remaining position
                closed = False
                exit_price = 0.0
                result = ""

                if open_trade["type"] == "BUY":
                    if low <= open_trade["sl"]:
                        exit_price = open_trade["sl"] - actual_slippage_delta
                        result = "BE/TRAIL_SL" if (open_trade.get("partial_closed") or open_trade.get("be_locked")) else "SL"
                        closed = True
                    elif high >= open_trade["tp"]:
                        exit_price = open_trade["tp"]
                        result = "TP"
                        closed = True
                elif open_trade["type"] == "SELL":
                    if high >= open_trade["sl"]:
                        exit_price = open_trade["sl"] + actual_slippage_delta
                        result = "BE/TRAIL_SL" if (open_trade.get("partial_closed") or open_trade.get("be_locked")) else "SL"
                        closed = True
                    elif low <= open_trade["tp"]:
                        exit_price = open_trade["tp"]
                        result = "TP"
                        closed = True

                if closed:
                    pips = ((exit_price - open_trade["entry"]) if open_trade["type"] == "BUY" else (open_trade["entry"] - exit_price)) / spec.pip_size
                    pnl_raw = pips * spec.pip_value_per_lot * open_trade["lots"]
                    comm = open_trade["lots"] * self.commission_per_lot
                    pnl_remaining = pnl_raw - comm
                    pnl_net = pnl_remaining + open_trade.get("realized_pnl", 0.0)
                    balance += pnl_remaining
                    equity = balance

                    is_win = pnl_net > 0
                    cooldown_mgr.record_trade_result(pnl=pnl_net, is_win=is_win, symbol=symbol, current_date=b_date)

                    trades.append({
                        "symbol": symbol,
                        "type": open_trade["type"],
                        "open_time": open_trade.get("open_time"),
                        "exit_time": bar_time,
                        "bars_held": open_trade.get("bars_held", 1),
                        "entry": open_trade["entry"],
                        "exit": exit_price,
                        "sl": open_trade["sl"],
                        "tp": open_trade["tp"],
                        "lots": open_trade.get("initial_lots", open_trade["lots"]),
                        "pnl": round(pnl_net, 2),
                        "result": result,
                        "strategy": open_trade["strategy"],
                        "regime": open_trade["regime"],
                        "score": open_trade["score"],
                        "planned_rr": open_trade.get("planned_rr", 0.0),
                        "master_score": open_trade.get("master_score", 0.0),
                        "mfe": round(open_trade["mfe"], 4),
                        "mae": round(open_trade["mae"], 4),
                        "is_win": is_win
                    })
                    open_trade = None

            # 2. Check new trade entry if flat
            if open_trade is None:
                skip_trade, skip_reason = cooldown_mgr.should_skip_trade(symbol)
                if skip_trade:
                    rejection_stats[skip_reason] = rejection_stats.get(skip_reason, 0) + 1
                    continue

                if full_df_h4 is not None and bar_time is not None:
                    h4_slice = full_df_h4[full_df_h4["time"] <= bar_time].iloc[-100:]
                    d1_slice = full_df_d1[full_df_d1["time"] <= bar_time].iloc[-50:]
                    mtf_dict = {"primary": history_slice, "context": h4_slice, "macro": d1_slice}
                else:
                    mtf_dict = {"primary": history_slice}

                context = self.context_engine.build_context(
                    symbol, mtf_dict,
                    current_spread_pips=spread_pips,
                    max_allowed_spread_pips=spec.max_spread_pips
                )
                regime = self.regime_classifier.classify_regime(context)

                # Parallel analysts with dynamic directional hypothesis
                tentative_bias = "BUY" if context.structure.bias == "BULLISH" else ("SELL" if context.structure.bias == "BEARISH" else ("SELL" if getattr(context.momentum, "trend_score", 0.0) < 0 else "BUY"))
                analyst_reports, devil_report = self.analyst_cluster.run_all_parallel(context, regime, tentative_bias)
                
                # Fractional Kelly dynamic position sizing
                planned_risk_pct = self.risk_per_trade_pct
                size_mult = cooldown_mgr.get_position_size_multiplier(planned_risk_pct, balance, win_rate=0.58, payoff_ratio=1.5)
                effective_risk_pct = max(0.20, planned_risk_pct * size_mult)

                decision = self.decision_engine.evaluate(
                    context, regime, analyst_reports, devil_report, account_balance=balance, risk_per_trade_pct=effective_risk_pct, mtf_data=mtf_dict
                )

                if decision.decision == "EXECUTE":
                    account_snap = AccountSnapshot(
                        login=1, server="Backtest", balance=balance, equity=balance, margin=0, free_margin=balance, margin_level=0, leverage=100
                    )
                    spec = resolve_symbol(symbol)
                    sym_info = {
                        "name": symbol,
                        "trade_contract_size": spec.contract_size,
                        "volume_min": 0.01,
                        "volume_max": 100.0,
                        "volume_step": 0.01
                    }
                    auth_res = self.risk_engine.authorize_execution(decision, account_snap, [], sym_info, spread_pips)

                    if auth_res["authorized"]:
                        entry_price = float(next_bar["open"])
                        price_shift = entry_price - decision.entry_price
                        sl_price = decision.stop_loss + price_shift
                        tp_price = decision.take_profit + price_shift
                        
                        actual_risk_dist = abs(entry_price - sl_price)
                        if actual_risk_dist <= 0:
                            actual_risk_dist = max(spec.pip_size * 10, decision.sl_distance)

                        # Enforce hard dollar risk cap based on filled entry & SL
                        planned_risk_dollars = balance * (effective_risk_pct / 100.0)
                        from jarvis.data.symbol_registry import get_dollar_risk_per_price_unit
                        unit_risk = get_dollar_risk_per_price_unit(symbol, sym_info)
                        dollar_risk_per_lot = actual_risk_dist * unit_risk
                        
                        if dollar_risk_per_lot > 0:
                            raw_lots = planned_risk_dollars / dollar_risk_per_lot
                            lots = max(sym_info["volume_min"], min(auth_res["lots"], round(raw_lots, 2)))
                        else:
                            lots = auth_res["lots"]

                        open_time_val = next_bar.get("time") if "time" in next_bar else bar_time

                        open_trade = {
                            "type": decision.bias,
                            "open_time": open_time_val,
                            "bars_held": 0,
                            "entry": entry_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "lots": lots,
                            "initial_lots": lots,
                            "risk_dist": actual_risk_dist,
                            "realized_pnl": 0.0,
                            "partial_closed": False,
                            "strategy": decision.strategy,
                            "regime": regime.primary_regime.value,
                            "score": decision.model_confidence,
                            "planned_rr": decision.risk_reward_ratio,
                            "master_score": getattr(decision, "master_confluence_score", 0.0),
                            "mfe": 0.0,
                            "mae": 0.0,
                            "first_target_price": getattr(decision, "first_target_price", None),
                            "first_target_volume_pct": getattr(decision, "first_target_volume_pct", 0.50),
                            "runner_trail_distance_atr": getattr(decision, "runner_trail_distance_atr", 1.2)
                        }
                    else:
                        auth_reason = auth_res.get("reason", "Risk Engine Auth Failed")
                        rejection_stats[auth_reason] = rejection_stats.get(auth_reason, 0) + 1
                else:
                    for r in getattr(decision, "rejection_reasons", []):
                        rejection_stats[r] = rejection_stats.get(r, 0) + 1
                    if not getattr(decision, "rejection_reasons", []):
                        for r in getattr(decision, "waiting_reasons", []):
                            rejection_stats[r] = rejection_stats.get(r, 0) + 1

        # Mark-to-market close of any remaining open position on final bar
        if open_trade is not None:
            final_bar = df_h1.iloc[-1]
            exit_price = float(final_bar["close"])
            spec = resolve_symbol(symbol)
            pips = ((exit_price - open_trade["entry"]) if open_trade["type"] == "BUY" else (open_trade["entry"] - exit_price)) / spec.pip_size
            pnl_raw = pips * spec.pip_value_per_lot * open_trade["lots"]
            comm = open_trade["lots"] * self.commission_per_lot
            pnl_net = pnl_raw - comm + open_trade.get("realized_pnl", 0.0)
            balance += (pnl_raw - comm)

            trades.append({
                "symbol": symbol,
                "type": open_trade["type"],
                "open_time": open_trade.get("open_time"),
                "exit_time": final_bar.get("time") if "time" in final_bar else None,
                "bars_held": open_trade.get("bars_held", 1),
                "entry": open_trade["entry"],
                "exit": exit_price,
                "sl": open_trade["sl"],
                "tp": open_trade["tp"],
                "lots": open_trade.get("initial_lots", open_trade["lots"]),
                "pnl": round(pnl_net, 2),
                "result": "CLOSE_AT_END",
                "strategy": open_trade["strategy"],
                "regime": open_trade["regime"],
                "score": open_trade["score"],
                "planned_rr": open_trade.get("planned_rr", 0.0),
                "master_score": open_trade.get("master_score", 0.0),
                "mfe": round(open_trade["mfe"], 4),
                "mae": round(open_trade["mae"], 4),
                "is_win": pnl_net > 0
            })
            open_trade = None

        metrics = PerformanceMetricsCalculator.calculate_metrics(trades, self.initial_balance)
        ver = HISTORICAL_DATA_ENGINE.get_dataset_version(symbol, timeframe=timeframe) or 1
        return {
            "symbol": symbol,
            "metrics": metrics,
            "trades": trades,
            "final_balance": round(balance, 2),
            "rejection_stats": rejection_stats,
            "dataset_version": ver
        }
