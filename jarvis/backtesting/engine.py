"""
JARVIS AI 3.0 — Chronological Event-Driven Backtesting Engine.
Executes historical simulation without lookahead bias, incorporating realistic spreads, commissions, and slippage.
"""
import pandas as pd
from typing import Dict, List, Any

from jarvis.market.market_context import MarketContextEngine
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.analysts.parallel_runner import ParallelAnalystCluster
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.risk.risk_engine import RiskEngine
from jarvis.data.schemas import AccountSnapshot, PositionSnapshot
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
        self.analyst_cluster = ParallelAnalystCluster()
        self.decision_engine = DecisionEngine()
        self.risk_engine = RiskEngine(max_risk_per_trade_pct=risk_per_trade_pct)

    def run_backtest(
        self,
        df_h1: pd.DataFrame,
        symbol: str = "XAUUSD",
        spread_pips: float = 2.0
    ) -> Dict[str, Any]:
        balance = self.initial_balance
        equity = self.initial_balance
        trades: List[Dict[str, Any]] = []
        open_trade: Optional[Dict[str, Any]] = None

        min_window = 60
        point_multiplier = 100.0 if "XAU" in symbol else 100000.0

        for i in range(min_window, len(df_h1) - 1):
            history_slice = df_h1.iloc[:i]
            current_bar = df_h1.iloc[i]
            next_bar = df_h1.iloc[i + 1]

            # 1. Manage existing open trade
            if open_trade:
                high = float(current_bar["high"])
                low = float(current_bar["low"])

                # Track MFE / MAE
                if open_trade["type"] == "BUY":
                    favorable = high - open_trade["entry"]
                    adverse = open_trade["entry"] - low
                else:
                    favorable = open_trade["entry"] - low
                    adverse = high - open_trade["entry"]

                open_trade["mfe"] = max(open_trade.get("mfe", 0.0), favorable)
                open_trade["mae"] = max(open_trade.get("mae", 0.0), adverse)

                # Check SL/TP exit
                closed = False
                exit_price = 0.0
                result = ""

                if open_trade["type"] == "BUY":
                    if low <= open_trade["sl"]:
                        exit_price = open_trade["sl"] - (self.slippage_pips * (0.01 if "XAU" in symbol else 0.0001))
                        result = "SL"
                        closed = True
                    elif high >= open_trade["tp"]:
                        exit_price = open_trade["tp"]
                        result = "TP"
                        closed = True
                elif open_trade["type"] == "SELL":
                    if high >= open_trade["sl"]:
                        exit_price = open_trade["sl"] + (self.slippage_pips * (0.01 if "XAU" in symbol else 0.0001))
                        result = "SL"
                        closed = True
                    elif low <= open_trade["tp"]:
                        exit_price = open_trade["tp"]
                        result = "TP"
                        closed = True

                if closed:
                    pnl_raw = (exit_price - open_trade["entry"]) * open_trade["lots"] * point_multiplier if open_trade["type"] == "BUY" else (open_trade["entry"] - exit_price) * open_trade["lots"] * point_multiplier
                    comm = open_trade["lots"] * self.commission_per_lot
                    pnl_net = pnl_raw - comm
                    balance += pnl_net
                    equity = balance

                    trades.append({
                        "symbol": symbol,
                        "type": open_trade["type"],
                        "entry": open_trade["entry"],
                        "exit": exit_price,
                        "sl": open_trade["sl"],
                        "tp": open_trade["tp"],
                        "lots": open_trade["lots"],
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

                # Parallel analysts
                analyst_reports, devil_report = self.analyst_cluster.run_all_parallel(context, regime, "BUY")
                decision = self.decision_engine.evaluate(
                    context, regime, analyst_reports, devil_report, account_balance=balance, risk_per_trade_pct=self.risk_per_trade_pct
                )

                if decision.decision == "EXECUTE":
                    account_snap = AccountSnapshot(
                        login=1, server="Backtest", balance=balance, equity=balance, margin=0, free_margin=balance, margin_level=0, leverage=100
                    )
                    sym_info = {"trade_contract_size": 100 if "XAU" in symbol else 100000, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
                    auth_res = self.risk_engine.authorize_execution(decision, account_snap, [], sym_info, spread_pips)

                    if auth_res["authorized"]:
                        lots = auth_res["lots"]
                        entry_price = float(next_bar["open"])
                        open_trade = {
                            "type": decision.bias,
                            "entry": entry_price,
                            "sl": decision.stop_loss,
                            "tp": decision.take_profit,
                            "lots": lots,
                            "strategy": decision.strategy,
                            "regime": regime.primary_regime.value,
                            "score": decision.model_confidence,
                            "mfe": 0.0,
                            "mae": 0.0
                        }

        metrics = PerformanceMetricsCalculator.calculate_metrics(trades, self.initial_balance)
        return {
            "symbol": symbol,
            "metrics": metrics,
            "trades": trades,
            "final_balance": round(balance, 2)
        }
