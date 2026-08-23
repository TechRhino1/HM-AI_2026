import unittest
from datetime import datetime, timezone
from jarvis.intelligence.regime_engine import MarketRegimeClassifier
from jarvis.data.schemas import (
    MarketContext, StructureContext, LiquidityContext, VolatilityContext,
    MomentumContext, SessionContext, MarketRegime
)

class TestRegimeEngine(unittest.TestCase):
    def setUp(self):
        self.regime_engine = MarketRegimeClassifier()

    def test_strong_bullish_regime(self):
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", bos=True, choch=False),
            liquidity=LiquidityContext(sweep_detected=False),
            volatility=VolatilityContext(atr=10.0, state="NORMAL"),
            momentum=MomentumContext(trend_score=85.0, adx=32.0),
            session=SessionContext(is_prime_session=True)
        )

        res = self.regime_engine.classify_regime(ctx)
        self.assertEqual(res.primary_regime, MarketRegime.TREND_BULL)
        self.assertGreaterEqual(res.confidence, 0.70)

    def test_volatility_shock_regime(self):
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(bias="BULLISH", bos=False),
            liquidity=LiquidityContext(sweep_detected=False),
            volatility=VolatilityContext(atr=50.0, state="EXTREME"),
            momentum=MomentumContext(trend_score=50.0, adx=15.0),
            session=SessionContext(is_prime_session=True)
        )

        res = self.regime_engine.classify_regime(ctx)
        self.assertIn(res.primary_regime, [MarketRegime.HIGH_VOLATILITY, MarketRegime.EVENT_RISK, MarketRegime.BREAKOUT])

if __name__ == "__main__":
    unittest.main()
