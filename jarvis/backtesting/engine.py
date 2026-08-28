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
        df_h1: pd.DataFrame,
        symbol: str = "XAUUSD",
        spread_pips: float = 2.0,
        slippage_delta: float = 0.05,
        start_bar_idx: int = 50
    ) -> Dict[str, Any]:
        balance = self.initial_balance
        equity = self.initial_balance
        trades: List[Dict[str, Any]] = []
        open_trade: Optional[Dict[str, Any]] = None

        total_bars = len(df_h1)
        if total_bars < 20:
            return {"symbol": symbol, "final_balance": balance, "metrics": PerformanceMetricsCalculator.calculate_metrics([], balance), "trades": []}

        effective_start = max(20, min(total_bars - 2, start_bar_idx))
        spec = resolve_symbol(symbol)
        actual_slippage_delta = self.slippage_pips * spec.pip_size
        
        for i in range(effective_start, total_bars - 1):
            history_slice = df_h1.iloc[:i]
            current_bar = df_h1.iloc[i]
            next_bar = df_h1.iloc[i + 1]

            # 1. Manage existing open trade with institutional partial TP & dynamic trailing
            if open_trade:
                high = float(current_bar["high"])
                low = float(current_bar["low"])
                atr = float(current_bar.get("atr", current_bar.get("ATR", (high - low) if (high - low) > 0 else 1.0)))

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

                # A. Partial TP @ 1.5R with Breakeven Lock
                if not open_trade.get("partial_closed", False) and open_trade["lots"] > 0.01:
                    partial_trigger_dist = risk_dist * 1.5
                    if open_trade["type"] == "BUY" and favorable >= partial_trigger_dist:
                        partial_lots = round(open_trade["lots"] * 0.5, 2)
                        if partial_lots >= 0.01:
                            partial_exit_p = open_trade["entry"] + partial_trigger_dist
                            pips_p = (partial_exit_p - open_trade["entry"]) / spec.pip_size
                            pnl_p = (pips_p * spec.pip_value_per_lot * partial_lots) - (partial_lots * self.commission_per_lot)
                            balance += pnl_p
                            open_trade["realized_pnl"] = open_trade.get("realized_pnl", 0.0) + pnl_p
                            open_trade["lots"] = round(open_trade["lots"] - partial_lots, 2)
                            open_trade["partial_closed"] = True
                            # Move SL to Breakeven + small buffer
                            open_trade["sl"] = round(open_trade["entry"] + (risk_dist * 0.1), spec.digits)
                    elif open_trade["type"] == "SELL" and favorable >= partial_trigger_dist:
                        partial_lots = round(open_trade["lots"] * 0.5, 2)
                        if partial_lots >= 0.01:
                            partial_exit_p = open_trade["entry"] - partial_trigger_dist
                            pips_p = (open_trade["entry"] - partial_exit_p) / spec.pip_size
                            pnl_p = (pips_p * spec.pip_value_per_lot * partial_lots) - (partial_lots * self.commission_per_lot)
                            balance += pnl_p
                            open_trade["realized_pnl"] = open_trade.get("realized_pnl", 0.0) + pnl_p
                            open_trade["lots"] = round(open_trade["lots"] - partial_lots, 2)
                            open_trade["partial_closed"] = True
                            # Move SL to Breakeven - small buffer
                            open_trade["sl"] = round(open_trade["entry"] - (risk_dist * 0.1), spec.digits)

                # B. Dynamic ATR Trailing Stop on Remaining Position
                if open_trade.get("partial_closed", False):
                    trail_dist = max(risk_dist, atr * 1.5)
                    if open_trade["type"] == "BUY":
                        new_sl = round(high - trail_dist, spec.digits)
                        if new_sl > open_trade["sl"]:
                            open_trade["sl"] = new_sl
                    else:
                        new_sl = round(low + trail_dist, spec.digits)
                        if new_sl < open_trade["sl"]:
                            open_trade["sl"] = new_sl

                # C. Check SL/TP exit for remaining position
                closed = False
                exit_price = 0.0
                result = ""

                if open_trade["type"] == "BUY":
                    if low <= open_trade["sl"]:
                        exit_price = open_trade["sl"] - actual_slippage_delta
                        result = "BE/TRAIL_SL" if open_trade.get("partial_closed") else "SL"
                        closed = True
                    elif high >= open_trade["tp"]:
                        exit_price = open_trade["tp"]
                        result = "TP"
                        closed = True
                elif open_trade["type"] == "SELL":
                    if high >= open_trade["sl"]:
                        exit_price = open_trade["sl"] + actual_slippage_delta
                        result = "BE/TRAIL_SL" if open_trade.get("partial_closed") else "SL"
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

                    trades.append({
                        "symbol": symbol,
                        "type": open_trade["type"],
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
                        "mfe": round(open_trade["mfe"], 4),
                        "mae": round(open_trade["mae"], 4),
                        "is_win": pnl_net > 0
                    })
                    open_trade = None

            # 2. Check new trade entry if flat
            if open_trade is None:
                mtf_dict = {"primary": history_slice}
                context = self.context_engine.build_context(symbol, mtf_dict, current_spread_pips=spread_pips)
                regime = self.regime_classifier.classify_regime(context)

                # Parallel analysts with dynamic directional hypothesis
                tentative_bias = "BUY" if context.structure.bias == "BULLISH" else ("SELL" if context.structure.bias == "BEARISH" else ("SELL" if getattr(context.momentum, "trend_score", 0.0) < 0 else "BUY"))
                analyst_reports, devil_report = self.analyst_cluster.run_all_parallel(context, regime, tentative_bias)
                decision = self.decision_engine.evaluate(
                    context, regime, analyst_reports, devil_report, account_balance=balance, risk_per_trade_pct=self.risk_per_trade_pct
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
                        planned_risk_dollars = balance * (self.risk_per_trade_pct / 100.0)
                        from jarvis.data.symbol_registry import get_dollar_risk_per_price_unit
                        unit_risk = get_dollar_risk_per_price_unit(symbol, sym_info)
                        dollar_risk_per_lot = actual_risk_dist * unit_risk
                        
                        if dollar_risk_per_lot > 0:
                            raw_lots = planned_risk_dollars / dollar_risk_per_lot
                            lots = max(sym_info["volume_min"], min(auth_res["lots"], round(raw_lots, 2)))
                        else:
                            lots = auth_res["lots"]

                        open_trade = {
                            "type": decision.bias,
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
                            "mfe": 0.0,
                            "mae": 0.0
                        }

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
                "mfe": round(open_trade["mfe"], 4),
                "mae": round(open_trade["mae"], 4),
                "is_win": pnl_net > 0
            })
            open_trade = None

        metrics = PerformanceMetricsCalculator.calculate_metrics(trades, self.initial_balance)
        return {
            "symbol": symbol,
            "metrics": metrics,
            "trades": trades,
            "final_balance": round(balance, 2)
        }
