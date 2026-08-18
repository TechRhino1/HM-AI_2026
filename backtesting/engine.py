import pandas as pd
from typing import Dict, Any, List
from engines.market_structure import MarketStructureEngine
from engines.trend_engine import MultiFactorTrendEngine
from engines.volatility_engine import VolatilityEngine
from engines.liquidity_engine import LiquidityEngine
from engines.regime_engine import MarketRegimeEngine
from engines.strategy_engine import AdaptiveStrategyEngine
from engines.dynamic_sl_tp import DynamicSLTPEngine
from engines.ai_decision_engine import AIDecisionEngine
from backtesting.metrics import PerformanceMetricsCalculator

class BacktestEngine:
    def __init__(self, initial_balance: float = 10000.0, risk_pct: float = 0.5):
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.structure_engine = MarketStructureEngine()
        self.trend_engine = MultiFactorTrendEngine()
        self.volatility_engine = VolatilityEngine()
        self.liquidity_engine = LiquidityEngine()
        self.regime_engine = MarketRegimeEngine()
        self.strategy_engine = AdaptiveStrategyEngine()
        self.sl_tp_engine = DynamicSLTPEngine()
        self.ai_decision_engine = AIDecisionEngine()

    def run_backtest(self, df_h1: pd.DataFrame, symbol: str = "XAUUSD") -> Dict[str, Any]:
        balance = self.initial_balance
        trades = []
        in_trade = False
        trade_info = {}

        min_window = 60
        profile = {
            "digits": 2 if "XAU" in symbol else 5,
            "sl_atr_multiplier": 1.5,
            "tp_atr_multiplier": 3.0,
            "max_allowed_spread_pips": 35.0
        }

        news_info = {"news_status": "NEWS_RISK_LOW", "reasons_not_to_trade": []}

        for i in range(min_window, len(df_h1) - 1):
            window_df = df_h1.iloc[:i]
            current_bar = df_h1.iloc[i]
            next_bar = df_h1.iloc[i + 1]

            structure = self.structure_engine.analyze_structure(window_df)
            trend = self.trend_engine.analyze_trend(window_df)
            volatility = self.volatility_engine.analyze_volatility(window_df)
            liquidity = self.liquidity_engine.analyze_liquidity(window_df, structure.get("swing_highs", []), structure.get("swing_lows", []))

            regime = self.regime_engine.classify_regime(structure, trend, volatility, liquidity)
            strategy = self.strategy_engine.select_strategy(regime, structure, volatility, liquidity)

            sl_tp = self.sl_tp_engine.calculate_sl_tp(symbol, strategy.get("recommended_action"), current_bar["close"], structure, volatility, profile)
            decision = self.ai_decision_engine.evaluate_trade_opportunity(symbol, structure, trend, volatility, liquidity, news_info, strategy, sl_tp)

            # Check ongoing open trade
            if in_trade:
                high = current_bar["high"]
                low = current_bar["low"]

                if trade_info["type"] == "BUY":
                    if low <= trade_info["sl"]:
                        pnl = (trade_info["sl"] - trade_info["entry"]) * trade_info["lots"] * 100
                        trades.append({**trade_info, "exit": trade_info["sl"], "pnl": pnl, "result": "SL"})
                        balance += pnl
                        in_trade = False
                    elif high >= trade_info["tp"]:
                        pnl = (trade_info["tp"] - trade_info["entry"]) * trade_info["lots"] * 100
                        trades.append({**trade_info, "exit": trade_info["tp"], "pnl": pnl, "result": "TP"})
                        balance += pnl
                        in_trade = False

                elif trade_info["type"] == "SELL":
                    if high >= trade_info["sl"]:
                        pnl = (trade_info["entry"] - trade_info["sl"]) * trade_info["lots"] * 100
                        trades.append({**trade_info, "exit": trade_info["sl"], "pnl": pnl, "result": "SL"})
                        balance += pnl
                        in_trade = False
                    elif low <= trade_info["tp"]:
                        pnl = (trade_info["entry"] - trade_info["tp"]) * trade_info["lots"] * 100
                        trades.append({**trade_info, "exit": trade_info["tp"], "pnl": pnl, "result": "TP"})
                        balance += pnl
                        in_trade = False

            # Check new entry signal
            elif decision.get("decision") == "EXECUTE":
                action = decision.get("action")
                entry_price = next_bar["open"]
                sl = sl_tp.get("sl_price")
                tp = sl_tp.get("tp1_price")

                risk_amount = balance * (self.risk_pct / 100.0)
                risk_dist = abs(entry_price - sl)
                lots = round(risk_amount / (risk_dist * 100 + 1e-9), 2)
                lots = max(0.01, lots)

                in_trade = True
                trade_info = {
                    "type": action,
                    "entry": entry_price,
                    "sl": sl,
                    "tp": tp,
                    "lots": lots,
                    "regime": regime.get("regime"),
                    "score": decision.get("trade_score")
                }

        metrics = PerformanceMetricsCalculator.calculate_metrics(trades, self.initial_balance)
        return {
            "metrics": metrics,
            "trades": trades,
            "final_balance": round(balance, 2)
        }
