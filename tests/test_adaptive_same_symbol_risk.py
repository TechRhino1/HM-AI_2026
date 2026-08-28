"""
Unit Test Suite for HM AI 4.0 Adaptive Same-Symbol Trade Risk Engine & Portfolio Heat.
Covers:
  - Base Soft Limit (1 trade) vs Hard Limit (2 trades)
  - 15-Point Adaptive Second-Trade Validation
  - Anti-Averaging Down Guard (Pyramiding vs Averaging Down)
  - Portfolio Heat Engine (0-100 scoring & tier enforcement)
  - Total Monetary Risk Budget enforcement
  - Currency Directional Concentration
  - Atomic Risk Reservation & Race Condition Safeguards
"""
import unittest
from datetime import datetime, timezone
from jarvis.risk.risk_engine import RiskEngine
from jarvis.risk.portfolio_heat import PortfolioHeatEngine, PortfolioHeatResult
from jarvis.risk.exposure import ExposureManager, BASE_MAX_TRADES_PER_SYMBOL, HARD_MAX_TRADES_PER_SYMBOL
from jarvis.data.schemas import (
    DecisionObject,
    AccountSnapshot,
    PositionSnapshot,
    MarketContext,
    StructureContext,
    LiquidityContext,
    VolatilityContext,
    MomentumContext,
    SessionContext,
    RegimeOutput,
    MarketRegime,
    TradeQualityGateResult
)

class TestAdaptiveSameSymbolRisk(unittest.TestCase):
    def setUp(self):
        self.risk_engine = RiskEngine(
            max_daily_loss_pct=4.0,
            max_drawdown_pct=10.0,
            max_open_positions=3,
            max_symbol_positions=2,
            max_risk_per_trade_pct=0.5,
            max_portfolio_risk_pct=2.5,
            is_backtest=True
        )

        self.account = AccountSnapshot(
            login=345841337,
            server="XM-Live",
            balance=10000.0,
            equity=10000.0,
            margin=200.0,
            free_margin=9800.0,
            margin_level=5000.0,
            leverage=100
        )

        regime = RegimeOutput(
            primary_regime=MarketRegime.TREND_BULL,
            probabilities={"TREND_BULL": 0.85},
            confidence=0.85
        )

        self.context = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", bos=True, choch=False),
            liquidity=LiquidityContext(sweep_detected=False),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=1.5),
            momentum=MomentumContext(trend_score=80.0, adx=30.0),
            session=SessionContext(current_session="LONDON", is_prime_session=True)
        )

        self.decision = DecisionObject(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            bias="BUY",
            probabilities={"buy": 0.85, "sell": 0.10, "no_trade": 0.05},
            strategy="TREND_PULLBACK",
            entry_price=2415.0,  # Structurally distinct from existing 2400.0 entry
            stop_loss=2405.0,
            take_profit=2440.0,
            risk_reward_ratio=2.5,
            calculated_risk_percent=0.5,
            expected_value=45.0,
            model_confidence=0.85,
            adversarial_penalty=6.0,
            invalidation_levels=["Close below 2405.0"],
            bull_case=["H1 Bullish structure"],
            bear_case=[],
            risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={"Regime": True}),
            decision="EXECUTE",
            execution_authorized=True
        )

        self.sym_info = {
            "trade_contract_size": 100.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01
        }

    def test_01_first_trade_authorization(self):
        """Test that first trade on a symbol passes with standard authorization."""
        res = self.risk_engine.authorize_execution(
            self.decision, self.account, [], self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertTrue(res["authorized"])
        self.assertFalse(res.get("is_second_trade", False))
        self.assertGreater(res["lots"], 0.0)

    def test_02_second_trade_pyramiding_on_winning_position(self):
        """Test that second trade on a WINNING position (+profit) with high conviction is approved."""
        existing_winning_pos = [
            PositionSnapshot(
                ticket=1001,
                symbol="XAUUSD",
                type="BUY",
                volume=0.05,
                open_price=2400.0,
                current_price=2415.0,
                sl=2402.0,  # SL in profit / breakeven
                tp=2450.0,
                profit=75.0,  # Winning position
                swap=0.0,
                commission=0.0,
                open_time=datetime.now(),
                magic=888999
            )
        ]

        res = self.risk_engine.authorize_execution(
            self.decision, self.account, existing_winning_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertTrue(res["authorized"])
        self.assertTrue(res.get("is_second_trade", False))
        self.assertGreater(res["lots"], 0.0)

    def test_03_anti_averaging_down_rejection_on_losing_position(self):
        """Test that adding to a LOSING position deeply in drawdown is REJECTED (softened: allows small -0.5% dips, blocks deep)."""
        existing_losing_pos = [
            PositionSnapshot(
                ticket=1002,
                symbol="XAUUSD",
                type="BUY",
                volume=0.05,
                open_price=2420.0,
                current_price=2410.0,
                sl=2395.0,
                tp=2450.0,
                profit=-75.0,  # Deeply losing (exceeds 0.5% equity = $50 threshold)
                swap=0.0,
                commission=0.0,
                open_time=datetime.now(),
                magic=888999
            )
        ]

        res = self.risk_engine.authorize_execution(
            self.decision, self.account, existing_losing_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("ANTI_AVERAGING_DOWN" in r for r in res["reasons"]))

    def test_04_hard_symbol_limit_rejection_on_two_existing_positions(self):
        """Test that a third position on the same symbol is unconditionally rejected by hard limit (2)."""
        existing_two_positions = [
            PositionSnapshot(ticket=1001, symbol="XAUUSD", type="BUY", volume=0.05, open_price=2400.0, current_price=2415.0, sl=2400.0, tp=2450.0, profit=75.0, swap=0, commission=0, open_time=datetime.now(), magic=888999),
            PositionSnapshot(ticket=1002, symbol="XAUUSD", type="BUY", volume=0.03, open_price=2410.0, current_price=2415.0, sl=2405.0, tp=2450.0, profit=25.0, swap=0, commission=0, open_time=datetime.now(), magic=888999),
        ]

        res = self.risk_engine.authorize_execution(
            self.decision, self.account, existing_two_positions, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("HARD_SYMBOL_LIMIT" in r for r in res["reasons"]))

    def test_05_portfolio_heat_engine_scoring_and_zones(self):
        """Test PortfolioHeatEngine score computation across Normal, Moderate, High, and Extreme zones."""
        heat_engine = PortfolioHeatEngine(max_portfolio_risk_pct=2.5, max_daily_loss_pct=4.0, max_open_positions=3)

        # 1. Normal state (low risk, no dd)
        res_normal = heat_engine.calculate_heat(self.account, [], open_monetary_risk_usd=50.0)
        self.assertEqual(res_normal.zone, "NORMAL")
        self.assertEqual(res_normal.risk_multiplier, 1.0)
        self.assertTrue(res_normal.allow_new_risk)

        # 2. Extreme heat state (high drawdown and heavy open positions)
        stressed_account = AccountSnapshot(
            login=123, server="XM", balance=10000.0, equity=9550.0,  # 4.5% DD > 4.0% limit
            margin=4200.0, free_margin=5350.0, margin_level=220.0, leverage=100
        )
        pos_stressed = [
            PositionSnapshot(ticket=1, symbol="EURUSD", type="BUY", volume=1.0, open_price=1.08, current_price=1.07, sl=1.06, tp=1.10, profit=-200, swap=0, commission=0, open_time=datetime.now(), magic=888),
            PositionSnapshot(ticket=2, symbol="GBPUSD", type="BUY", volume=1.0, open_price=1.28, current_price=1.27, sl=1.26, tp=1.30, profit=-200, swap=0, commission=0, open_time=datetime.now(), magic=888),
            PositionSnapshot(ticket=3, symbol="USDJPY", type="SELL", volume=1.0, open_price=155.0, current_price=156.0, sl=157.0, tp=152.0, profit=-200, swap=0, commission=0, open_time=datetime.now(), magic=888),
        ]
        res_extreme = heat_engine.calculate_heat(stressed_account, pos_stressed, open_monetary_risk_usd=300.0)
        self.assertEqual(res_extreme.zone, "EXTREME")
        self.assertEqual(res_extreme.risk_multiplier, 0.0)
        self.assertFalse(res_extreme.allow_new_risk)

    def test_06_portfolio_monetary_risk_budget_cap(self):
        """Test that exceeding the 2.5% portfolio risk budget blocks new trades."""
        # Setup positions carrying $260 open risk on $10,000 equity (2.6% > 2.5% max)
        heavy_risk_pos = [
            PositionSnapshot(ticket=1, symbol="EURUSD", type="BUY", volume=1.3, open_price=1.0850, current_price=1.0850, sl=1.0650, tp=1.1050, profit=0, swap=0, commission=0, open_time=datetime.now(), magic=888),
        ]

        res = self.risk_engine.authorize_execution(
            self.decision, self.account, heavy_risk_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("Portfolio Risk Budget" in r for r in res["reasons"]))

    def test_07_atomic_risk_reservation_and_release(self):
        """Test atomic risk reservation flow."""
        self.risk_engine.release_risk("XAUUSD")
        self.assertEqual(self.risk_engine.get_total_reserved_risk_usd(), 0.0)

        # Reserve $100
        reserved = self.risk_engine.reserve_risk("XAUUSD", 100.0, ttl_sec=10.0)
        self.assertTrue(reserved)
        self.assertEqual(self.risk_engine.get_total_reserved_risk_usd(), 100.0)

        # Commit/release
        self.risk_engine.commit_risk("XAUUSD")
        self.assertEqual(self.risk_engine.get_total_reserved_risk_usd(), 0.0)

    def test_08_low_probability_rejection(self):
        """Test Gate 1: Rejection when calibrated probability is below 60% for 2nd trade."""
        existing_pos = [
            PositionSnapshot(ticket=1001, symbol="XAUUSD", type="BUY", volume=0.05, open_price=2400.0, current_price=2415.0, sl=2402.0, tp=2450.0, profit=75.0, swap=0, commission=0, open_time=datetime.now(), magic=888999)
        ]
        low_p_decision = DecisionObject(
            symbol="XAUUSD", timestamp=datetime.now(timezone.utc), regime=self.decision.regime,
            bias="BUY", probabilities={"buy": 0.50}, strategy="TREND_PULLBACK",
            entry_price=2420.0, stop_loss=2410.0, take_profit=2440.0, risk_reward_ratio=2.0,
            calculated_risk_percent=0.5, expected_value=20.0, model_confidence=0.52, # < 0.60
            adversarial_penalty=5.0, invalidation_levels=[], bull_case=[], bear_case=[], risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={}), decision="EXECUTE", execution_authorized=True
        )
        res = self.risk_engine.authorize_execution(
            low_p_decision, self.account, existing_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("ADAPTIVE_GATE_1" in r for r in res["reasons"]))

    def test_09_negative_ev_rejection(self):
        """Test Gate 2: Rejection when expected value is non-positive."""
        existing_pos = [
            PositionSnapshot(ticket=1001, symbol="XAUUSD", type="BUY", volume=0.05, open_price=2400.0, current_price=2415.0, sl=2402.0, tp=2450.0, profit=75.0, swap=0, commission=0, open_time=datetime.now(), magic=888999)
        ]
        neg_ev_decision = DecisionObject(
            symbol="XAUUSD", timestamp=datetime.now(timezone.utc), regime=self.decision.regime,
            bias="BUY", probabilities={"buy": 0.85}, strategy="TREND_PULLBACK",
            entry_price=2420.0, stop_loss=2410.0, take_profit=2440.0, risk_reward_ratio=2.0,
            calculated_risk_percent=0.5, expected_value=-5.0, # <= 0.0
            model_confidence=0.85, adversarial_penalty=5.0, invalidation_levels=[], bull_case=[], bear_case=[], risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={}), decision="EXECUTE", execution_authorized=True
        )
        res = self.risk_engine.authorize_execution(
            neg_ev_decision, self.account, existing_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("ADAPTIVE_GATE_2" in r for r in res["reasons"]))

    def test_10_entry_geometry_rejection(self):
        """Test Gate 15: Rejection when new entry price is too close to existing entry price."""
        existing_pos = [
            PositionSnapshot(ticket=1001, symbol="XAUUSD", type="BUY", volume=0.05, open_price=2400.0, current_price=2401.0, sl=2390.0, tp=2430.0, profit=10.0, swap=0, commission=0, open_time=datetime.now(), magic=888999)
        ]
        close_entry_decision = DecisionObject(
            symbol="XAUUSD", timestamp=datetime.now(timezone.utc), regime=self.decision.regime,
            bias="BUY", probabilities={"buy": 0.85}, strategy="TREND_PULLBACK",
            entry_price=2400.5, # Only 0.5 points from 2400.0 (risk_dist is 10.0, requires >= 2.5)
            stop_loss=2390.5, take_profit=2430.0, risk_reward_ratio=2.0, calculated_risk_percent=0.5,
            expected_value=45.0, model_confidence=0.85, adversarial_penalty=5.0, invalidation_levels=[],
            bull_case=[], bear_case=[], risk_factors=[], quality_gate=TradeQualityGateResult(passed=True, checks={}),
            decision="EXECUTE", execution_authorized=True
        )
        res = self.risk_engine.authorize_execution(
            close_entry_decision, self.account, existing_pos, self.sym_info,
            current_spread_pips=1.5, max_allowed_spread_pips=35.0, context=self.context
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("ADAPTIVE_GATE_15" in r for r in res["reasons"]))

if __name__ == "__main__":
    unittest.main()
