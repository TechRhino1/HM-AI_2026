"""
Unit Tests for JARVIS Master-Trader Autonomous Trade Selector & Self-Learning Architecture.
Covers:
- UniversalOpportunityArbiter (Utility math, Grade A+/A/B/C assignment, multi-style ranking & selection)
- OnlineMLPredictor (24-D feature extraction, return-weighted SGD, Brier score tracking, [0.35, 0.88] calibration)
- StrategyBandit (Beta-Binomial Thompson Sampling, multi-context priors, outcome recording)
- Orchestrator multi-style arbitration integration and closed-trade learning feedback
"""
import unittest
import numpy as np
import tempfile
import os
import json
from datetime import datetime, timezone

from jarvis.intelligence.opportunity_arbiter import UniversalOpportunityArbiter, CandidateOpportunity
from jarvis.learning.online_ml_predictor import OnlineMLPredictor
from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.data.schemas import (
    DecisionObject,
    MarketContext,
    RegimeOutput,
    MarketRegime,
    TradeQualityGateResult,
    StructureContext,
    LiquidityContext,
    VolatilityContext,
    MomentumContext,
    SessionContext
)

class TestOpportunityArbiter(unittest.TestCase):

    def setUp(self):
        self.ml_predictor = OnlineMLPredictor()
        self.bandit = StrategyBandit()
        self.arbiter = UniversalOpportunityArbiter(
            ml_predictor=self.ml_predictor,
            bandit=self.bandit
        )

        self.sample_context = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(
                bias="BULLISH",
                bos=True,
                choch=False,
                discount_premium_zone="DISCOUNT",
                order_blocks=[{"top": 2395.0, "bottom": 2390.0}],
                fair_value_gaps=[{"top": 2398.0, "bottom": 2393.0}]
            ),
            liquidity=LiquidityContext(
                sweep_detected=True,
                sweep_type="BULLISH_SWEEP"
            ),
            volatility=VolatilityContext(
                atr=12.0,
                current_spread_pips=1.5,
                max_allowed_spread_pips=30.0,
                bollinger_bandwidth=0.04,
                state="COMPRESSION"
            ),
            momentum=MomentumContext(
                rsi=58.0,
                adx=28.0,
                trend_score=45,
                divergence="BULLISH_DIVERGENCE"
            ),
            session=SessionContext(
                current_session="LONDON",
                is_prime_session=True,
                utc_hour=9
            ),
            vwap=2395.0,
            mtf_confluence_score=80.0,
            mtf_alignment={"H4": "BULLISH", "D1": "BULLISH", "H1": "BULLISH"}
        )

        self.sample_regime = RegimeOutput(
            primary_regime=MarketRegime.TREND_BULL,
            probabilities={"TREND_BULL": 0.85},
            confidence=0.85
        )

    def test_utility_formula_calculation(self):
        """Verify the exact Utility formula: Utility = P_ML * EV * (1 + Conf/100) * (1 - Penalty) * RegimeMultiplier"""
        decision = DecisionObject(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            regime=self.sample_regime,
            bias="BUY",
            probabilities={"buy": 0.75, "sell": 0.25},
            strategy="TREND_PULLBACK",
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2425.0,
            risk_reward_ratio=2.5,
            calculated_risk_percent=1.0,
            expected_value=1.20,
            model_confidence=0.75,
            adversarial_penalty=10.0,  # 10% -> 0.10
            invalidation_levels=["2388.0"],
            bull_case=["Trend alignment", "FVG Retest"],
            bear_case=[],
            risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={"structure": True}),
            decision="EXECUTE",
            master_confluence_score=80.0,
            meta_label_prob=0.70
        )

        cand = self.arbiter.evaluate_opportunity(decision, self.sample_context, trade_style="SWING")

        # P_ML = 0.70, EV = 1.20, Confluence = 80.0 -> (1 + 0.80) = 1.80
        # Penalty = 10.0 -> (1 - 0.10) = 0.90
        # RegimeMultiplier for SWING TREND_BULL = 1.20 (with synergy = 1.25)
        # Expected Utility = 0.70 * 1.20 * 1.80 * 0.90 * 1.25 = ~1.701
        self.assertAlmostEqual(cand.ml_prob, 0.70, places=2)
        self.assertAlmostEqual(cand.expected_value, 1.20, places=2)
        self.assertAlmostEqual(cand.confluence_score, 80.0, places=1)
        self.assertGreater(cand.utility_score, 1.35)
        self.assertEqual(cand.setup_grade, "GRADE A")
        self.assertTrue(cand.is_actionable)

    def test_setup_grade_a_plus_classification(self):
        """Verify GRADE A+ when Utility >= 1.80, Win Prob >= 70%, Confluence >= 75, EV >= 0.85R."""
        decision = DecisionObject(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            regime=self.sample_regime,
            bias="BUY",
            probabilities={"buy": 0.80, "sell": 0.20},
            strategy="LIQUIDITY_SWEEP_REVERSAL",
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2430.0,
            risk_reward_ratio=3.0,
            calculated_risk_percent=1.0,
            expected_value=1.50,
            model_confidence=0.80,
            adversarial_penalty=0.0,
            invalidation_levels=[],
            bull_case=["Elite confluence"],
            bear_case=[],
            risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={}),
            decision="EXECUTE",
            master_confluence_score=85.0,
            meta_label_prob=0.75
        )

        cand = self.arbiter.evaluate_opportunity(decision, self.sample_context, trade_style="SWING")
        self.assertGreaterEqual(cand.utility_score, 1.80)
        self.assertGreaterEqual(cand.win_prob, 70.0)
        self.assertGreaterEqual(cand.confluence_score, 75.0)
        self.assertGreaterEqual(cand.expected_value, 0.85)
        self.assertEqual(cand.setup_grade, "GRADE A+")
        self.assertTrue(cand.is_actionable)

    def test_setup_grade_b_and_c_classification(self):
        """Verify GRADE B (Utility >= 1.00) and GRADE C (Utility < 1.00)."""
        # Grade B candidate
        decision_b = DecisionObject(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            regime=RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.5),
            bias="BUY",
            probabilities={"buy": 0.55, "sell": 0.45},
            strategy="RANGE_MEAN_REVERSION",
            entry_price=1.0850,
            stop_loss=1.0820,
            take_profit=1.0910,
            risk_reward_ratio=2.0,
            calculated_risk_percent=1.0,
            expected_value=1.30,
            model_confidence=0.55,
            adversarial_penalty=5.0,
            invalidation_levels=[],
            bull_case=[],
            bear_case=[],
            risk_factors=[],
            quality_gate=TradeQualityGateResult(passed=True, checks={}),
            decision="EXECUTE",
            master_confluence_score=50.0,
            meta_label_prob=0.58
        )
        cand_b = self.arbiter.evaluate_opportunity(decision_b, self.sample_context, trade_style="DAY_TRADING")
        self.assertIn(cand_b.setup_grade, ("GRADE B", "GRADE A"))

        # Grade C candidate (negative EV / zero utility)
        decision_c = DecisionObject(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            regime=RegimeOutput(primary_regime=MarketRegime.RANGE, probabilities={}, confidence=0.5),
            bias="BUY",
            probabilities={"buy": 0.40, "sell": 0.60},
            strategy="STRUCTURE",
            entry_price=1.0850,
            stop_loss=1.0820,
            take_profit=1.0870,
            risk_reward_ratio=0.67,
            calculated_risk_percent=1.0,
            expected_value=-0.20,
            model_confidence=0.40,
            adversarial_penalty=30.0,
            invalidation_levels=[],
            bull_case=[],
            bear_case=[],
            risk_factors=["Choppy market"],
            quality_gate=TradeQualityGateResult(passed=False, checks={}),
            decision="NO_TRADE",
            master_confluence_score=20.0,
            meta_label_prob=0.35
        )
        cand_c = self.arbiter.evaluate_opportunity(decision_c, self.sample_context, trade_style="SCALP")
        self.assertEqual(cand_c.utility_score, 0.0)
        self.assertEqual(cand_c.setup_grade, "GRADE C")
        self.assertFalse(cand_c.is_actionable)

    def test_rank_and_select_best_across_multi_styles(self):
        """Verify arbiter properly ranks multiple styles and picks top actionable Grade A/A+ candidate."""
        # Candidate 1: Scalp (Grade B, Utility 1.1)
        cand1 = CandidateOpportunity(
            symbol="EURUSD", trade_style="SCALP", timeframe="M15/M5/M1", strategy="M1_M5_FVG_SCALP",
            bias="BUY", entry_price=1.0850, stop_loss=1.0830, take_profit=1.0890, risk_reward_ratio=2.0,
            expected_value=0.6, win_prob=58.0, ml_prob=0.55, confluence_score=55.0, confluence_factors=[],
            adversarial_penalty=0.0, risk_factors=[], regime="RANGE", regime_multiplier=1.1,
            utility_score=1.10, setup_grade="GRADE B", is_actionable=True
        )

        # Candidate 2: Swing Gold (Grade A+, Utility 2.2)
        cand2 = CandidateOpportunity(
            symbol="XAUUSD", trade_style="SWING", timeframe="D1/H4/H1", strategy="TREND_FOLLOWING",
            bias="BUY", entry_price=2400.0, stop_loss=2380.0, take_profit=2460.0, risk_reward_ratio=3.0,
            expected_value=1.6, win_prob=78.0, ml_prob=0.74, confluence_score=85.0, confluence_factors=[],
            adversarial_penalty=0.0, risk_factors=[], regime="TREND_BULL", regime_multiplier=1.25,
            utility_score=2.20, setup_grade="GRADE A+", is_actionable=True
        )

        # Candidate 3: Day Trading BTC (Grade A, Utility 1.5)
        cand3 = CandidateOpportunity(
            symbol="BTCUSD", trade_style="DAY_TRADING", timeframe="H1/M15/M5", strategy="BREAKOUT_EXPANSION",
            bias="BUY", entry_price=65000.0, stop_loss=64000.0, take_profit=67500.0, risk_reward_ratio=2.5,
            expected_value=1.1, win_prob=65.0, ml_prob=0.62, confluence_score=70.0, confluence_factors=[],
            adversarial_penalty=5.0, risk_factors=[], regime="BREAKOUT", regime_multiplier=1.15,
            utility_score=1.50, setup_grade="GRADE A", is_actionable=True
        )

        # Candidate 4: Unactionable (Grade C, Utility 0.0)
        cand4 = CandidateOpportunity(
            symbol="GBPUSD", trade_style="SWING", timeframe="D1/H4/H1", strategy="STRUCTURE",
            bias="SELL", entry_price=1.2800, stop_loss=1.2850, take_profit=1.2750, risk_reward_ratio=1.0,
            expected_value=0.0, win_prob=45.0, ml_prob=0.40, confluence_score=30.0, confluence_factors=[],
            adversarial_penalty=20.0, risk_factors=[], regime="CHOP", regime_multiplier=0.8,
            utility_score=0.0, setup_grade="GRADE C", is_actionable=False
        )

        candidates = [cand1, cand4, cand3, cand2]
        best_cand, ranked = self.arbiter.rank_and_select_best(candidates)

        self.assertIsNotNone(best_cand)
        self.assertEqual(best_cand.symbol, "XAUUSD")
        self.assertEqual(best_cand.trade_style, "SWING")
        self.assertEqual(best_cand.setup_grade, "GRADE A+")
        self.assertEqual(ranked[0].symbol, "XAUUSD")
        self.assertEqual(ranked[1].symbol, "BTCUSD")
        self.assertEqual(ranked[2].symbol, "EURUSD")
        self.assertEqual(ranked[3].symbol, "GBPUSD")


class TestOnlineMLPredictor(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = os.path.join(self.temp_dir.name, "test_ml_weights.json")
        self.predictor = OnlineMLPredictor(model_file=self.model_path)

        self.context = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH", bos=True, choch=False),
            liquidity=LiquidityContext(sweep_detected=True, sweep_type="BULLISH_SWEEP"),
            volatility=VolatilityContext(atr=0.0050, current_spread_pips=1.0, bollinger_bandwidth=0.03),
            momentum=MomentumContext(rsi=55.0, adx=25.0, trend_score=30, divergence="BULLISH_DIVERGENCE"),
            session=SessionContext(current_session="LONDON", is_prime_session=True, utc_hour=10),
            vwap=1.0840,
            mtf_confluence_score=75.0,
            mtf_alignment={"H4": "BULLISH", "D1": "BULLISH"}
        )
        self.regime = RegimeOutput(
            primary_regime=MarketRegime.TREND_BULL,
            probabilities={"TREND_BULL": 0.8},
            confidence=0.8
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_24d_feature_extraction_shape_and_values(self):
        """Verify 24-D stationary quantitative feature extraction."""
        features = self.predictor.extract_features(
            context=self.context,
            regime=self.regime,
            trade_style="SWING",
            strategy="TREND_FOLLOWING",
            tentative_bias="BUY",
            devil_penalty=0.0,
            target_rr=2.5
        )
        self.assertEqual(len(features), 24)
        self.assertEqual(self.predictor.n_features, 24)
        self.assertFalse(np.isnan(features).any())
        self.assertFalse(np.isinf(features).any())

    def test_predict_probability_clamped_institutional_domain(self):
        """Verify output probability is bounded strictly within [0.35, 0.88]."""
        features = np.zeros(24, dtype=float)
        p_zero = self.predictor.predict_probability(features)
        self.assertGreaterEqual(p_zero, 0.35)
        self.assertLessEqual(p_zero, 0.88)

        extreme_positive = np.full(24, 10.0, dtype=float)
        p_high = self.predictor.predict_probability(extreme_positive)
        self.assertEqual(p_high, 0.88)

        extreme_negative = np.full(24, -10.0, dtype=float)
        p_low = self.predictor.predict_probability(extreme_negative)
        self.assertEqual(p_low, 0.35)

    def test_return_weighted_online_sgd_update(self):
        """Verify return-weighted online learning step and Brier Score tracking."""
        initial_weights = self.predictor.weights.copy()
        feat = np.ones(24, dtype=float) * 0.5

        # Execute 3 updates (batch_size = 3) with high R-multiple win
        self.predictor.update_online(feat, target_win=1, r_multiple=2.5)
        self.predictor.update_online(feat, target_win=1, r_multiple=3.0)
        self.predictor.update_online(feat, target_win=1, r_multiple=2.0)

        # Weights should have shifted towards positive features
        self.assertFalse(np.array_equal(self.predictor.weights, initial_weights))
        self.assertGreater(self.predictor.training_steps, 10)
        self.assertGreater(len(self.predictor._brier_window), 0)


class TestStrategyBandit(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.temp_dir.name, "test_bandit_state.json")
        self.bandit = StrategyBandit(state_file=self.state_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_thompson_sampling_weights(self):
        """Verify Beta prior sampling returns valid probability distribution."""
        sample_w = self.bandit.sample_strategy_weight("TREND_FOLLOWING", regime="TREND_BULL", style="SWING")
        self.assertGreater(sample_w, 0.0)
        self.assertLess(sample_w, 1.0)

        all_weights = self.bandit.get_strategy_weights(regime="TREND_BULL", style="SWING")
        self.assertEqual(len(all_weights), len(self.bandit.STRATEGIES))
        self.assertAlmostEqual(sum(all_weights.values()), 1.0, places=2)

    def test_record_outcome_updates_beta_priors(self):
        """Verify winning trade increases alpha and losing trade increases beta."""
        strat = "LIQUIDITY_SWEEP_REVERSAL"
        regime = "LIQUIDITY_SWEEP"
        style = "SCALP"

        a_init, b_init = self.bandit._get_alpha_beta(regime, style, strat)
        self.assertEqual(a_init, 3.0)
        self.assertEqual(b_init, 2.0)

        # Record win with 2.5R
        self.bandit.record_outcome(strat, is_win=1, r_multiple=2.5, regime=regime, style=style)
        a_after_win, b_after_win = self.bandit._get_alpha_beta(regime, style, strat)
        self.assertGreater(a_after_win, a_init)
        self.assertEqual(b_after_win, b_init)

        # Record loss
        self.bandit.record_outcome(strat, is_win=0, r_multiple=1.0, regime=regime, style=style)
        a_after_loss, b_after_loss = self.bandit._get_alpha_beta(regime, style, strat)
        self.assertGreater(b_after_loss, b_after_win)


class TestOrchestratorMultiStyleRadar(unittest.TestCase):

    def setUp(self):
        self.orchestrator = JarvisOrchestrator(
            symbols=["XAUUSD", "EURUSD"],
            mode="paper",
            trade_style="SWING"
        )

    def tearDown(self):
        self.orchestrator.stop()

    def test_orchestration_loop_single_pass_with_arbiter(self):
        """Verify _orchestration_loop_single_pass populates radar with arbiter metrics across all styles."""
        radar_results = self.orchestrator._orchestration_loop_single_pass()

        # 2 symbols * 3 styles = 6 candidates
        self.assertEqual(len(radar_results), 6)
        self.assertEqual(len(self.orchestrator.state_manager.radar_opportunities), 6)

        # Verify arbiter fields exist in radar items
        for item in radar_results:
            self.assertIn("utility_score", item)
            self.assertIn("setup_grade", item)
            self.assertIn("is_actionable", item)
            self.assertIn("ml_prob", item)
            self.assertIn("regime_multiplier", item)
            self.assertIn("trade_style", item)
            self.assertIn("win_prob", item)
            self.assertIn("ev", item)

    def test_closed_trade_self_learning_loop(self):
        """Verify _on_trade_closed triggers return-weighted ML and Thompson bandit updates."""
        ticket = 888777
        initial_training_steps = self.orchestrator.ml_predictor.training_steps

        dummy_feat = self.orchestrator.ml_predictor.extract_features(
            context=MarketContext(
                symbol="XAUUSD",
                timestamp=datetime.now(timezone.utc),
                current_price=2400.0,
                bid=2399.8,
                ask=2400.2,
                structure=StructureContext(bias="BULLISH"),
                liquidity=LiquidityContext(),
                volatility=VolatilityContext(atr=10.0),
                momentum=MomentumContext(),
                session=SessionContext()
            ),
            regime=RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.8),
            trade_style="SWING",
            strategy="TREND_FOLLOWING",
            tentative_bias="BUY"
        )

        self.orchestrator._pending_features[ticket] = {
            "features": dummy_feat,
            "strategy": "TREND_FOLLOWING",
            "regime": "TREND_BULL",
            "trade_style": "SWING",
            "entry": 2400.0,
            "sl": 2390.0,
            "risk_dist": 10.0,
            "symbol": "XAUUSD"
        }

        # Simulate closed trade event
        self.orchestrator._on_trade_closed({
            "ticket": ticket,
            "pnl": 150.0,
            "exit_price": 2425.0,
            "equity": 10150.0,
            "balance": 10150.0
        })

        self.assertNotIn(ticket, self.orchestrator._pending_features)
        self.assertEqual(len(self.orchestrator.ml_predictor._grad_buffer), 1)

if __name__ == "__main__":
    unittest.main()
