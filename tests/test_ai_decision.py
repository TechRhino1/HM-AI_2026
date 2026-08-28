import unittest
from datetime import datetime, timezone
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.data.schemas import (
    MarketContext, StructureContext, LiquidityContext, VolatilityContext,
    MomentumContext, SessionContext, RegimeOutput, MarketRegime,
    AnalystReport, AnalystRole, DevilAdvocateReport
)

class TestAIDecisionEngine(unittest.TestCase):
    def setUp(self):
        from jarvis.intelligence.self_learning import SelfLearningEngine
        self.engine = DecisionEngine(self_learning=SelfLearningEngine(db_path=":memory:"))

    def test_high_quality_setup(self):
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", bos=True, choch=True, choch_type="BULLISH", demand_zone=(2390.0, 2392.0)),
            liquidity=LiquidityContext(sweep_detected=True, sweep_type="BULLISH_SWEEP"),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=1.5),
            momentum=MomentumContext(trend_score=80.0, adx=32.0),
            session=SessionContext(current_session="LONDON", is_prime_session=True)
        )
        regime = RegimeOutput(
            primary_regime=MarketRegime.TREND_BULL,
            probabilities={"TREND_BULL": 0.85},
            confidence=0.85
        )
        analyst_reports = {
            "STRUCTURE": AnalystReport(role=AnalystRole.STRUCTURE, symbol="XAUUSD", bias="BULLISH", confidence=0.85, score=85.0, evidence=["BOS confirmed"]),
            "MOMENTUM": AnalystReport(role=AnalystRole.MOMENTUM, symbol="XAUUSD", bias="BULLISH", confidence=0.80, score=80.0, evidence=["ADX 32"])
        }
        devil_report = DevilAdvocateReport(
            symbol="XAUUSD",
            counter_bias="BEARISH",
            penalty_score=10.0,
            invalidation_risk_coefficient=0.90,
            threats_detected=[]
        )

        res = self.engine.evaluate(ctx, regime, analyst_reports, devil_report, account_balance=10000.0)
        self.assertIn(res.decision, ["EXECUTE", "WAIT"])
        self.assertEqual(res.bias, "BUY")
        self.assertGreaterEqual(res.model_confidence, 0.50)

if __name__ == "__main__":
    unittest.main()
