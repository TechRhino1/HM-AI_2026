import unittest
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.backtesting.engine import BacktestEngine
from jarvis.intelligence.strategy_selector import StrategySelector
from jarvis.market.data_feed import TF_MAP, DataFeedEngine
from jarvis.data.schemas import (
    MarketContext, StructureContext, LiquidityContext, VolatilityContext,
    MomentumContext, SessionContext, RegimeOutput, MarketRegime,
    AnalystReport, AnalystRole, DevilAdvocateReport
)

class TestApexMasterTraderOptimization(unittest.TestCase):
    def setUp(self):
        from jarvis.intelligence.self_learning import SelfLearningEngine
        from jarvis.intelligence.realtime_optimizer import RealtimeOptimizer
        self.decision_engine = DecisionEngine(
            self_learning=SelfLearningEngine(db_path=":memory:"),
            realtime_optimizer=RealtimeOptimizer(db_path=":memory:")
        )
        self.strategy_selector = StrategySelector()

    def test_decision_engine_no_forced_bias_fallback_defaults_to_hold(self):
        """1. In _compute_bias_and_levels, weak signals default to tentative_bias = 'HOLD'."""
        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="NEUTRAL", bos=False, choch=False),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=5.0, adx=15.0),  # weak momentum |trend_score| < 20
            session=SessionContext(current_session="LONDON", is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.7)
        # Only 1 analyst report
        analyst_reports = {
            "STRUCTURE": AnalystReport(role=AnalystRole.STRUCTURE, symbol="EURUSD", bias="BULLISH", confidence=0.6, score=60.0, evidence=[])
        }

        bias, entry, sl, tp, risk_dist, rr, target_p, target_vol = self.decision_engine._compute_bias_and_levels(
            ctx, regime, analyst_reports
        )
        self.assertEqual(bias, "HOLD", "Weak consensus without 3 analyst votes or strong structure/momentum must yield tentative_bias='HOLD'")

    def test_decision_engine_strong_consensus_triggers_bias(self):
        """1. With >=3 analyst votes or strong structural BOS with |trend_score| >= 20, tentative_bias is set."""
        ctx_bos = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH", bos=True, choch=False),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=25.0, adx=26.0),  # strong BOS with trend_score >= 20
            session=SessionContext(current_session="LONDON", is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.8)
        bias_bos, _, _, _, _, _, _, _ = self.decision_engine._compute_bias_and_levels(ctx_bos, regime, {})
        self.assertEqual(bias_bos, "BUY")

        # 3 Analyst votes
        analyst_reports_3 = {
            "STRUCTURE": AnalystReport(role=AnalystRole.STRUCTURE, symbol="EURUSD", bias="BEARISH", confidence=0.8, score=80.0, evidence=[]),
            "MOMENTUM": AnalystReport(role=AnalystRole.MOMENTUM, symbol="EURUSD", bias="BEARISH", confidence=0.8, score=80.0, evidence=[]),
            "LIQUIDITY": AnalystReport(role=AnalystRole.LIQUIDITY, symbol="EURUSD", bias="BEARISH", confidence=0.8, score=80.0, evidence=[])
        }
        ctx_plain = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="NEUTRAL"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=-5.0, adx=15.0),
            session=SessionContext(is_prime_session=True)
        )
        bias_3, _, _, _, _, _, _, _ = self.decision_engine._compute_bias_and_levels(ctx_plain, regime, analyst_reports_3)
        self.assertEqual(bias_3, "SELL")

    def test_decision_engine_quality_gate_thresholds_and_strict_discount_premium(self):
        """1. Quality gate thresholds: win_p, min_score, and strict Discount/Premium rule on Forex."""
        ctx_fx_prem = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH", discount_premium_zone="PREMIUM", choch=True, choch_type="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=50.0, adx=25.0),  # trend_score 50 < 65 extreme momentum hurdle
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)
        devil = DevilAdvocateReport(symbol="EURUSD", counter_bias="BEARISH", penalty_score=5.0, threats_detected=[], invalidation_risk_coefficient=1.0)
        
        # BUY in PREMIUM with trend_score=50 (<65) must fail Premium/Discount Alignment on Forex
        dec = self.decision_engine.evaluate(ctx_fx_prem, regime, {}, devil, account_balance=10000.0)
        self.assertFalse(dec.quality_gate.checks.get("Premium/Discount Alignment", True))

        # Check gate thresholds for Forex
        gate_fx = self.decision_engine._apply_quality_gate(
            context=ctx_fx_prem, regime=regime, devil_report=devil, ai_score=77.0, rr_ratio=2.0,
            ev=10.0, final_win_p=0.60, spread=1.0, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.60, risk_dist=0.0020, planned_risk_dollars=50.0
        )
        self.assertFalse(gate_fx.checks["AI Multi-Score Gate"], "Forex min_score=78.0 must fail score=77.0")
        self.assertFalse(gate_fx.checks["Calibrated Win Prob >= 50%"], "Forex required_win_p=0.62 must fail win_p=0.60")

        # Check gate thresholds for Gold
        ctx_gold = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=1.2),
            momentum=MomentumContext(trend_score=40.0, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        gate_gold = self.decision_engine._apply_quality_gate(
            context=ctx_gold, regime=regime, devil_report=devil, ai_score=76.5, rr_ratio=2.0,
            ev=10.0, final_win_p=0.60, spread=1.2, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.60, risk_dist=10.0, planned_risk_dollars=50.0
        )
        self.assertTrue(gate_gold.checks["AI Multi-Score Gate"], "Gold min_score=76.0 should pass score=76.5")
        self.assertTrue(gate_gold.checks["Calibrated Win Prob >= 50%"], "Gold required_win_p=0.60 should pass win_p=0.60")

    def test_strategy_selector_eliminates_breakout_expansion_on_forex(self):
        """3. StrategySelector completely eliminates BREAKOUT_EXPANSION on Forex majors."""
        ctx_fx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH", bos=True),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=60.0, adx=35.0),
            session=SessionContext(is_prime_session=True)
        )
        for regime_type in [MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY, MarketRegime.TREND_BULL, MarketRegime.RANGE]:
            regime = RegimeOutput(primary_regime=regime_type, probabilities={}, confidence=0.9)
            probs = self.strategy_selector.select_strategy_probabilities(regime, context=ctx_fx, account_equity=10000.0)
            self.assertEqual(probs.get("BREAKOUT_EXPANSION", 0.0), 0.0, f"BREAKOUT_EXPANSION must be 0.0 on Forex for regime {regime_type}")

    def test_data_feed_m10_support(self):
        """4. DataFeedEngine supports M10 timeframe in TF_MAP and realistic rates generation."""
        self.assertIn("M10", TF_MAP)
        df_feed = DataFeedEngine()
        rates_m10 = df_feed._generate_realistic_rates("EURUSD", "M10", 50)
        self.assertEqual(len(rates_m10), 50)
        self.assertIn("close", rates_m10.columns)

    def test_backtest_engine_profit_protection_stages(self):
        """2. BacktestEngine multi-tier profit protection parameters."""
        engine = BacktestEngine(initial_balance=10000.0)
        # Create a simple synthetic upward trend DataFrame
        dates = pd.date_range("2026-01-01", periods=100, freq="1h")
        prices = np.linspace(1.0800, 1.0950, 100)
        df_h1 = pd.DataFrame({
            "time": dates,
            "open": prices,
            "high": prices + 0.0010,
            "low": prices - 0.0005,
            "close": prices + 0.0005,
            "volume": [1000.0] * 100,
            "atr": [0.0015] * 100
        })
        res = engine.run_backtest(df_h1, symbol="EURUSD", spread_pips=1.0)
        self.assertIn("metrics", res)
        self.assertIn("trades", res)

if __name__ == "__main__":
    unittest.main()
