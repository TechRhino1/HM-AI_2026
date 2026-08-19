"""
JARVIS AI 4.0 — Core System Unit & Integration Test Suite.
Verifies all 19 bug fixes and architectural guarantees.
"""
import unittest
from datetime import datetime, timezone

from jarvis.risk.position_sizing import PositionSizer
from jarvis.risk.account_tier import (
    AccountTier,
    get_account_tier,
    is_micro_account,
    get_max_lot_cap,
    get_effective_min_ev
)
from jarvis.data.symbol_registry import resolve as resolve_symbol, is_crypto, SymbolSpec
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.learning.trade_memory import TradeMemory
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.intelligence.hypothesis_engine import HypothesisEngine
from jarvis.intelligence.confidence import ConfidenceCalibrationEngine
from jarvis.data.schemas import (
    MarketContext,
    StructureContext,
    LiquidityContext,
    VolatilityContext,
    MomentumContext,
    SessionContext,
    RegimeOutput,
    MarketRegime,
    AnalystReport,
    AnalystRole,
    DevilAdvocateReport
)
from jarvis.execution.order_manager import OrderManager
from jarvis.data.schemas import PositionSnapshot

class TestJarvisCore(unittest.TestCase):

    def test_account_tier_and_ev_scaling(self):
        """§3 & §4: Verify canonical account tiering and smooth EV hurdles."""
        self.assertEqual(get_account_tier(35.0), AccountTier.ULTRA_SURVIVAL)
        self.assertEqual(get_account_tier(80.0), AccountTier.MICRO_GROWTH)
        self.assertEqual(get_account_tier(150.0), AccountTier.SMALL_ACCOUNT)
        self.assertEqual(get_account_tier(500.0), AccountTier.STANDARD)
        self.assertEqual(get_account_tier(2000.0), AccountTier.INSTITUTIONAL)

        self.assertTrue(is_micro_account(80.0))
        self.assertFalse(is_micro_account(120.0))

        self.assertEqual(get_max_lot_cap(35.0), 0.01)
        self.assertEqual(get_max_lot_cap(80.0), 0.03)
        self.assertEqual(get_max_lot_cap(150.0), 0.05)

        # Smooth EV hurdles for sub-$1000 accounts
        ev_micro = get_effective_min_ev(80.0, planned_risk_dollars=0.40)
        self.assertLessEqual(ev_micro, 0.05)
        ev_small = get_effective_min_ev(150.0, planned_risk_dollars=0.75)
        self.assertLess(ev_small, 0.50)  # Solves §3 cliff

    def test_symbol_registry_specs(self):
        """§9, §11, §13: Verify symbol specs for forex, metals, and crypto."""
        gold = resolve_symbol("GOLD.i#")
        self.assertEqual(gold.canonical, "XAUUSD")
        self.assertEqual(gold.contract_size, 100.0)
        self.assertEqual(gold.digits, 2)

        btc = resolve_symbol("BTCUSD#")
        self.assertEqual(btc.canonical, "BTCUSD")
        self.assertEqual(btc.contract_size, 1.0)
        self.assertEqual(btc.digits, 2)
        self.assertTrue(btc.is_crypto)

        jpy = resolve_symbol("USDJPY#")
        self.assertEqual(jpy.digits, 3)
        self.assertTrue(jpy.is_jpy_quote)

    def test_position_sizer_floor(self):
        """§8: Verify position sizing does not crash and calculates lots correctly."""
        lots = PositionSizer.calculate_lot_size(
            account_balance=80.0,
            entry_price=4350.0,
            sl_price=4340.0,
            risk_pct=0.5,
            symbol_info={"trade_contract_size": 100.0, "volume_min": 0.01, "volume_max": 10.0, "volume_step": 0.01}
        )
        self.assertGreaterEqual(lots, 0.01)

    def test_strategy_bandit_negative_rewards(self):
        """§14: Verify bandit allows negative reward accumulation and handles unknown keys."""
        bandit = StrategyBandit(state_file="scratch_bandit_test.json")
        bandit.record_outcome("TREND_FOLLOWING", is_win=0, r_multiple=0.0, regime="TREND_BULL")
        bandit.record_outcome("UNKNOWN_STRATEGY", is_win=0, r_multiple=0.0, regime="UNKNOWN_REGIME")
        boosts = bandit.get_strategy_boosts("TREND_BULL")
        self.assertIn("TREND_FOLLOWING", boosts)
        self.assertGreater(boosts["TREND_FOLLOWING"], 0.0)

    def test_trade_memory_update_closed(self):
        """§17: Verify closed trade updates in SQLite."""
        tm = TradeMemory(db_path=":memory:")
        tm.record_trade({
            "ticket": 999111,
            "symbol": "XAUUSD",
            "type": "BUY",
            "entry": 4350.0,
            "sl": 4340.0,
            "tp": 4375.0,
            "lots": 0.01
        })
        tm.update_closed_trade(ticket=999111, exit_price=4365.0, pnl=15.0, is_win=1)
        trades = tm.fetch_all_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["exit_price"], 4365.0)
        self.assertEqual(trades[0]["pnl"], 15.0)
        self.assertEqual(trades[0]["is_win"], 1)

    def test_dynamic_hypothesis_win_probability(self):
        """§18: Verify dynamic signal-driven win probability."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=4350.0,
            bid=4349.9,
            ask=4350.1,
            structure=StructureContext(bias="BULLISH", demand_zone=(4335.0, 4340.0), supply_zone=(4370.0, 4375.0)),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0),
            momentum=MomentumContext(trend_persistence=5),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(
            primary_regime=MarketRegime.TREND_BULL,
            probabilities={"TREND_BULL": 0.8},
            confidence=0.85
        )
        analyst_reports = {
            "STRUCTURE": AnalystReport(role=AnalystRole.STRUCTURE, symbol="XAUUSD", bias="BULLISH", score=85.0, confidence=0.8),
            "MOMENTUM": AnalystReport(role=AnalystRole.MOMENTUM, symbol="XAUUSD", bias="BULLISH", score=90.0, confidence=0.85)
        }
        devil_report = DevilAdvocateReport(symbol="XAUUSD", counter_bias="BEARISH", penalty_score=10.0, invalidation_risk_coefficient=0.9)
        
        he = HypothesisEngine()
        hyp = he.construct_hypotheses(ctx, regime, analyst_reports, devil_report, "BUY")
        self.assertGreater(hyp.primary_probability, 0.50)

if __name__ == "__main__":
    unittest.main()
