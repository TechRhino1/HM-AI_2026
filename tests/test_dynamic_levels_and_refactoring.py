"""
Unit tests for JARVIS AI Master-Trader Dynamic Refactoring (Tasks 1 through 5).
Validates:
1. DynamicRiskAndLevelsEngine (purely structural, volatility-adaptive SL/TP and scale-out plans)
2. DecisionEngine dynamic quality gates (Kelly win prob, dynamic score hurdle, RSI exhaustion, Gold sweep check)
3. StrategySelector Bayesian weighting (sweep detection, volume delta, ADX slope)
4. BacktestEngine consumption of dynamic scale-out plans
5. LiquidityEngine & MarketStructureEngine displacement validation (candle body >= 45%)
"""
import unittest
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from jarvis.intelligence.dynamic_levels import DynamicRiskAndLevelsEngine
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.intelligence.strategy_selector import StrategySelector
from jarvis.backtesting.engine import BacktestEngine
from jarvis.market.liquidity import LiquidityEngine
from jarvis.market.market_structure import MarketStructureEngine
from jarvis.data.schemas import (
    MarketContext, StructureContext, LiquidityContext, VolatilityContext,
    MomentumContext, SessionContext, RegimeOutput, MarketRegime,
    AnalystReport, AnalystRole, DevilAdvocateReport, DecisionObject
)
from jarvis.intelligence.self_learning import SelfLearningEngine


class TestDynamicLevelsAndRefactoring(unittest.TestCase):
    def setUp(self):
        self.levels_engine = DynamicRiskAndLevelsEngine()
        self.decision_engine = DecisionEngine(
            self_learning=SelfLearningEngine(db_path=":memory:"),
            dynamic_levels_engine=self.levels_engine
        )
        self.strategy_selector = StrategySelector()
        self.liquidity_engine = LiquidityEngine()
        self.structure_engine = MarketStructureEngine()

    def test_dynamic_levels_structural_sl_and_tp_buy(self):
        """Task 1: Dynamic structural SL and liquidity-anchored TP for BUY."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(
                bias="BULLISH",
                demand_zone=(2392.0, 2394.0),
                supply_zone=(2430.0, 2435.0),
                order_blocks=[{"type": "BULLISH_ORDER_BLOCK", "low": 2393.0, "high": 2396.0}],
                fair_value_gaps=[{"type": "BEARISH_FVG", "bottom": 2415.0, "top": 2418.0}]
            ),
            liquidity=LiquidityContext(buy_side_liquidity=2435.0, sell_side_liquidity=2390.0),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0, state="NORMAL"),
            momentum=MomentumContext(trend_score=60.0, adx=30.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)

        levels = self.levels_engine.calculate_levels(ctx, regime, tentative_bias="BUY")

        self.assertEqual(levels["bias"], "BUY")
        self.assertAlmostEqual(levels["entry_price"], 2400.2, places=2)
        # SL should be anchored below 2394 (demand zone / OB) with dynamic buffer
        self.assertLess(levels["sl_price"], 2394.0)
        self.assertGreater(levels["risk_dist"], 5.0)
        # TP should target opposing structure offering >= 1.5R
        self.assertGreaterEqual(levels["rr_ratio"], 1.5)
        self.assertGreater(levels["tp_price"], levels["entry_price"])
        # First target should be structural resistance / FVG or 1.0R
        self.assertIsNotNone(levels["first_target_price"])
        self.assertLess(levels["first_target_price"], levels["tp_price"])

    def test_dynamic_levels_scale_out_and_runner_trailing_states(self):
        """Task 1: Scale-out volume pct and runner trailing distance in EXPANSION vs COMPRESSION."""
        ctx_exp = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0020, current_spread_pips=1.0, state="EXPANSION"),
            momentum=MomentumContext(trend_score=50.0, adx=32.0),
            session=SessionContext(is_prime_session=True),
            order_flow={"delta_score": 40.0}
        )
        reg_trend = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)
        levels_exp = self.levels_engine.calculate_levels(ctx_exp, reg_trend, tentative_bias="BUY")

        # In strong expansion with positive volume delta: first_target_volume_pct = 0.35, runner_trail = 1.4 ATR
        self.assertEqual(levels_exp["first_target_volume_pct"], 0.35)
        self.assertAlmostEqual(levels_exp["runner_trail_distance_atr"], 1.40, places=2)

        ctx_comp = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="NEUTRAL"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0010, current_spread_pips=1.0, state="COMPRESSION"),
            momentum=MomentumContext(trend_score=0.0, adx=12.0),
            session=SessionContext(is_prime_session=True)
        )
        reg_range = RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.80)
        levels_comp = self.levels_engine.calculate_levels(ctx_comp, reg_range, tentative_bias="BUY")

        # In range / compression: first_target_volume_pct = 0.65, runner_trail = 1.0 ATR
        self.assertEqual(levels_comp["first_target_volume_pct"], 0.65)
        self.assertAlmostEqual(levels_comp["runner_trail_distance_atr"], 1.00, places=2)

    def test_decision_engine_dynamic_rsi_exhaustion_bounds(self):
        """Task 2: Dynamic RSI exhaustion bounds based on ADX (70 +- 10 * TrendPower)."""
        ctx_high_adx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=80.0, adx=45.0, rsi=76.0),  # TrendPower = 1.0 -> RSI bound expands to 80.0
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)
        devil = DevilAdvocateReport(symbol="EURUSD", counter_bias="BEARISH", penalty_score=5.0, invalidation_risk_coefficient=1.0)

        # In high ADX trend, RSI=76 is NOT exhausted because bound is 80
        gate_high = self.decision_engine._apply_quality_gate(
            context=ctx_high_adx, regime=regime, devil_report=devil, ai_score=80.0,
            rr_ratio=2.2, ev=10.0, final_win_p=0.65, spread=1.0, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.65
        )
        self.assertTrue(gate_high.checks["Trend Not Exhausted"])

        # In low ADX non-expansion (RANGE regime, ADX=20), TrendPower = 0.0 -> RSI bound is 70.0. RSI=74 should be marked exhausted
        regime_range = RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.85)
        ctx_low_adx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=15.0, adx=20.0, rsi=74.0),
            session=SessionContext(is_prime_session=True)
        )
        gate_low = self.decision_engine._apply_quality_gate(
            context=ctx_low_adx, regime=regime_range, devil_report=devil, ai_score=80.0,
            rr_ratio=2.2, ev=10.0, final_win_p=0.65, spread=1.0, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.65
        )
        self.assertFalse(gate_low.checks["Trend Not Exhausted"])

    def test_decision_engine_gold_trend_following_confirmation(self):
        """Task 2: Gold (XAUUSD) requires sweep confirmation, discount/premium pullback, or strong momentum expansion for TREND_FOLLOWING."""
        # Scenario A: Gold buying at PREMIUM without liquidity sweep, BOS, or strong expansion -> should fail Gold Trend Following gate
        ctx_gold_prem = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2420.0,
            bid=2419.8,
            ask=2420.2,
            structure=StructureContext(bias="BULLISH", discount_premium_zone="PREMIUM"),
            liquidity=LiquidityContext(sweep_detected=False),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=1.5),
            momentum=MomentumContext(trend_score=10.0, adx=15.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)
        devil = DevilAdvocateReport(symbol="XAUUSD", counter_bias="BEARISH", penalty_score=5.0, invalidation_risk_coefficient=1.0)

        gate_fail = self.decision_engine._apply_quality_gate(
            context=ctx_gold_prem, regime=regime, devil_report=devil, ai_score=80.0,
            rr_ratio=2.5, ev=20.0, final_win_p=0.65, spread=1.5, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.65, strategy="TREND_FOLLOWING"
        )
        self.assertFalse(gate_fail.checks["Gold Trend Following Alignment"])

        # Scenario B: Gold with liquidity sweep detected -> passes
        ctx_gold_sweep = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", discount_premium_zone="PREMIUM"),
            liquidity=LiquidityContext(sweep_detected=True, sweep_type="BULLISH_SWEEP"),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=1.5),
            momentum=MomentumContext(trend_score=10.0, adx=15.0),
            session=SessionContext(is_prime_session=True)
        )
        gate_pass = self.decision_engine._apply_quality_gate(
            context=ctx_gold_sweep, regime=regime, devil_report=devil, ai_score=80.0,
            rr_ratio=2.5, ev=20.0, final_win_p=0.65, spread=1.5, premium_discount_valid=True,
            account_balance=10000.0, tentative_bias="BUY", calibrated_win_p=0.65, strategy="TREND_FOLLOWING"
        )
        self.assertTrue(gate_pass.checks["Gold Trend Following Alignment"])

    def test_strategy_selector_bayesian_sweep_and_volume_delta(self):
        """Task 3: StrategySelector Bayesian weights updated by sweep detection and volume delta."""
        ctx_sweep = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="NEUTRAL"),
            liquidity=LiquidityContext(sweep_detected=True, sweep_magnitude=2.0),
            volatility=VolatilityContext(atr=0.0015, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=-10.0, adx=18.0, slope=-0.1),
            session=SessionContext(is_prime_session=True)
        )
        reg_range = RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.80)
        probs = self.strategy_selector.select_strategy_probabilities(reg_range, context=ctx_sweep, account_equity=10000.0)

        # Liquidity sweep reversal should receive dominant Bayesian probability weight
        self.assertGreater(probs.get("LIQUIDITY_SWEEP_REVERSAL", 0.0), 0.30)
        self.assertEqual(probs.get("BREAKOUT_EXPANSION", 0.0), 0.0)  # Always 0 on Forex

    def test_backtesting_engine_consumes_dynamic_scale_out_plan(self):
        """Task 4: BacktestEngine runs with dynamic scale-out plan and runner trailing."""
        engine = BacktestEngine(initial_balance=10000.0)
        dates = pd.date_range("2026-01-01", periods=60, freq="1h")
        prices = np.linspace(2400.0, 2450.0, 60)
        df_h1 = pd.DataFrame({
            "time": dates,
            "open": prices,
            "high": prices + 5.0,
            "low": prices - 2.0,
            "close": prices + 3.0,
            "volume": [5000.0] * 60,
            "atr": [8.0] * 60
        })
        res = engine.run_backtest(df_h1, symbol="XAUUSD", spread_pips=2.0)
        self.assertIn("metrics", res)
        self.assertIn("trades", res)

    def test_liquidity_and_structure_displacement_validation(self):
        """Task 5: Liquidity sweep and Order Block displacement validation (body >= 45%)."""
        # Create DataFrame with clear swing points
        # 10 candles establishing a swing low at candle 5 (low = 100.0)
        highs = [105, 104, 103, 102, 102, 101, 103, 104, 105, 106, 107, 106, 105, 104, 103, 102, 101, 102, 103, 104]
        lows =  [101, 100,  99,  98,  98,  95,  97,  99, 100, 101, 102, 101, 100,  99,  98,  97,  96,  97,  98,  99]
        opens = [104, 102, 100,  99,  99,  98, 100, 101, 103, 104, 105, 104, 103, 102, 101, 100,  99, 100, 101, 102]
        closes =[102, 101,  99,  98,  98,  97, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101, 100, 101, 102, 103]

        # Add sweep candle at end that pokes below recent low 96 (low=94), closes back at 99 (open=95, close=99)
        # Body = 4.0, Range = (100 - 94) = 6.0 -> Body % = 4/6 = 66.7% >= 45% (Valid displacement)
        highs.append(100.0)
        lows.append(94.0)
        opens.append(95.0)
        closes.append(99.0)

        df = pd.DataFrame({
            "high": highs,
            "low": lows,
            "open": opens,
            "close": closes,
            "volume": [1000.0] * len(highs)
        })

        liq_ctx = self.liquidity_engine.analyze_liquidity(df, pivot_window=3)
        self.assertTrue(liq_ctx.sweep_detected)
        self.assertEqual(liq_ctx.sweep_type, "BULLISH_SWEEP")

        # Now test weak displacement candle (doji wick poke): open=97.0, close=97.1, low=94.0, high=100.0
        # Body = 0.1, Range = 6.0 -> Body % = 1.6% < 45% -> should NOT confirm sweep
        df.loc[df.index[-1], "open"] = 97.0
        df.loc[df.index[-1], "close"] = 97.1
        liq_ctx_doji = self.liquidity_engine.analyze_liquidity(df, pivot_window=3)
        self.assertFalse(liq_ctx_doji.sweep_detected)

    def test_calculate_manual_trade_levels(self):
        """Validates calculate_manual_trade_levels for AI-assisted manual orders."""
        levels_buy = self.levels_engine.calculate_manual_trade_levels("XAUUSD", "BUY", current_price=2400.0)
        self.assertIn("sl", levels_buy)
        self.assertIn("tp", levels_buy)
        self.assertIn("tp1", levels_buy)
        self.assertIn("tp2", levels_buy)
        self.assertIn("risk_dist", levels_buy)
        self.assertIn("rr", levels_buy)
        self.assertLess(levels_buy["sl"], 2400.0)
        self.assertGreater(levels_buy["tp"], 2400.0)
        self.assertGreater(levels_buy["tp1"], 2400.0)
        self.assertGreater(levels_buy["tp2"], 2400.0)
        self.assertGreater(levels_buy["risk_dist"], 0.0)

        levels_sell = self.levels_engine.calculate_manual_trade_levels("EURUSD", "SELL", current_price=1.0850)
        self.assertGreater(levels_sell["sl"], 1.0850)
        self.assertLess(levels_sell["tp"], 1.0850)
        self.assertLess(levels_sell["tp1"], 1.0850)
        self.assertLess(levels_sell["tp2"], 1.0850)
        self.assertGreater(levels_sell["risk_dist"], 0.0)


if __name__ == "__main__":
    unittest.main()
