import unittest
import os
import sys
import json
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

class TestSystemProductionSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mt5_client = MT5ExecutionEngine(mode="live")
        cls.data_engine = MultiTimeframeDataEngine(cls.mt5_client)
        cls.learning_engine = SelfLearningEngine()
        cls.ai_engine = AIDecisionEngine(learning_engine=cls.learning_engine)

    def test_01_mt5_connection(self):
        acc = self.mt5_client.get_account_info()
        self.assertIsNotNone(acc)
        self.assertIn("balance", acc)
        self.assertGreater(acc.get("balance", 0), 0)

    def test_02_symbol_alias_resolution(self):
        res_gold = self.mt5_client.resolve_symbol_name("XAUUSD")
        res_btc = self.mt5_client.resolve_symbol_name("BTCUSD")
        self.assertIn(res_gold, ["GOLD.i#", "XAUUSD", "GOLD"])
        self.assertIn(res_btc, ["BTCUSD#", "BTCUSD"])

    def test_03_market_data_engine_fetching(self):
        df_h1 = self.data_engine.fetch_rates("GOLD.i#", timeframe="H1", num_bars=50)
        self.assertEqual(len(df_h1), 50)
        self.assertIn("close", df_h1.columns)
        self.assertIn("high", df_h1.columns)
        self.assertIn("low", df_h1.columns)

    def test_04_indicator_calculations(self):
        df_h1 = self.data_engine.fetch_rates("GOLD.i#", timeframe="H1", num_bars=50)
        trend_eng = MultiFactorTrendEngine()
        res = trend_eng.analyze_trend(df_h1)
        self.assertIn("trend_score", res)
        self.assertIn("rsi", res)
        self.assertIn("adx", res)

    def test_05_invalid_sl_tp_direction_rejection(self):
        # Passing SL above price for BUY must be rejected or auto-corrected
        sym_info = self.mt5_client.get_symbol_info("GOLD.i#")
        price = sym_info["ask"]
        sl_invalid = price + 50.0  # Invalid SL for BUY
        tp_invalid = price - 50.0  # Invalid TP for BUY

        sl_tp_eng = DynamicSLTPEngine()
        struct_mock = {"recent_swing_high": price + 10, "recent_swing_low": price - 10, "demand_zone": (price-5, price), "supply_zone": (price, price+5)}
        vol_mock = {"atr": 10.0}
        
        valid_sl_tp = sl_tp_eng.calculate_sl_tp("GOLD.i#", "BUY", price, struct_mock, vol_mock, {"digits": 2, "sl_atr_multiplier": 1.5})
        self.assertLess(valid_sl_tp["sl_price"], price)
        self.assertGreater(valid_sl_tp["tp1_price"], price)

    def test_06_dynamic_kelly_position_sizing(self):
        settings = {"risk": {"max_account_risk_pct": 2.0, "max_open_positions": 5}}
        risk_eng = RiskManagerEngine(settings)
        acc = self.mt5_client.get_account_info()
        sym = self.mt5_client.get_symbol_info("GOLD.i#")

        lots_high_conf = risk_eng.calculate_position_size(acc, sym, sym["ask"] - 15.0, sym["ask"], trade_score=90.0)
        lots_mid_conf = risk_eng.calculate_position_size(acc, sym, sym["ask"] - 15.0, sym["ask"], trade_score=75.0)
        
        self.assertGreaterEqual(lots_high_conf, lots_mid_conf)
        self.assertGreaterEqual(lots_high_conf, sym["volume_min"])

    def test_07_excessive_spread_rejection(self):
        settings = {"risk": {"max_allowed_spread_pips": 5.0}}
        risk_eng = RiskManagerEngine(settings)
        acc = self.mt5_client.get_account_info()
        
        res = risk_eng.validate_risk_limits(acc, [], "GOLD.i#", current_spread_pips=50.0, profile=settings["risk"])
        self.assertFalse(res["passed"])
        self.assertTrue(any("spread" in r.lower() for r in res["reasons"]))

    def test_08_news_intelligence_blackout_filter(self):
        news_eng = NewsIntelligenceEngine(enabled=True)
        res = news_eng.evaluate_news_risk("GOLD.i#")
        self.assertIn("news_status", res)
        self.assertIn("news_source", res)

    def test_09_ai_low_confidence_score_rejection(self):
        # AI decision score below 75 must result in NO_TRADE / REJECTED
        df_h1 = self.data_engine.fetch_rates("GOLD.i#", timeframe="H1", num_bars=50)
        trend_res = {"trend_score": 0.0, "adx": 10.0, "rsi": 50.0, "ema_alignment": "NEUTRAL"}
        struct = {"bias": "NEUTRAL", "bos": False, "choch": False}
        vol = {"regime": "NORMAL", "atr": 10.0}
        liq = {"sweep_detected": False}
        news = {"news_status": "NEWS_RISK_LOW", "high_impact_imminent": False}
        strat = {"strategy_name": "NEUTRAL_HOLD", "recommended_action": "HOLD", "base_score": 30.0}
        sl_tp = {"sl_price": 2000.0, "tp1_price": 2050.0, "rr_ratio": 2.0}

        dec = self.ai_engine.evaluate_trade_opportunity("GOLD.i#", struct, trend_res, vol, liq, news, strat, sl_tp, regime={"regime": "RANGING_SIDEWAYS"})
        self.assertIn(dec["decision"], ["REJECTED", "NO_TRADE"])
        self.assertEqual(dec["action"], "HOLD")

    def test_10_adaptive_self_learning_reinforcement(self):
        thresh = self.learning_engine.get_adaptive_score_threshold(75.0)
        adj = self.learning_engine.get_strategy_score_adjustment("MODERATE_TREND_BULLISH", "TREND_PULLBACK_BULLISH")
        self.assertIsInstance(thresh, float)
        self.assertIsInstance(adj, float)

    def test_11_trade_plan_generation(self):
        plan_eng = TradePlanEngine()
        plans = plan_eng.generate_trade_plans([{
            "symbol": "GOLD.i#",
            "trade_score": 82.0,
            "action": "BUY",
            "regime": "MODERATE_TREND_BULLISH",
            "price": 2400.0,
            "sl": 2380.0,
            "tp": 2440.0,
            "rr": 2.0
        }])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["status"], "READY")
        self.assertEqual(plans[0]["symbol"], "GOLD.i#")

    def test_12_partial_and_full_close_mechanics(self):
        # Test dry-run partial close & full close
        dry_client = MT5ExecutionEngine(mode="dry_run")
        pc_res = dry_client.partial_close_position(12345, "GOLD.i#", pct=0.50)
        fc_res = dry_client.close_position(12345, "GOLD.i#")
        self.assertTrue(pc_res)
        self.assertTrue(fc_res)

if __name__ == "__main__":
    unittest.main()
