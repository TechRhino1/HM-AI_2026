import unittest
from datetime import datetime, timezone
from jarvis.risk.risk_engine import RiskEngine
from jarvis.data.schemas import (
    DecisionObject,
    AccountSnapshot,
    PositionSnapshot,
    RegimeOutput,
    MarketRegime,
    TradeQualityGateResult
)

class TestRiskEngineJ3(unittest.TestCase):
    def setUp(self):
        self.risk_engine = RiskEngine(
            max_daily_loss_pct=4.0,
            max_drawdown_pct=10.0,
            max_open_positions=2,
            max_symbol_positions=1,
            max_risk_per_trade_pct=0.5,
            is_backtest=True
        )

        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={"TREND_BULL": 0.8}, confidence=0.85)
        self.valid_decision = DecisionObject(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            bias="BUY",
            probabilities={"buy": 0.75, "sell": 0.15, "no_trade": 0.10},
            strategy="TREND_PULLBACK",
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2425.0,
            risk_reward_ratio=2.5,
            calculated_risk_percent=0.5,
            expected_value=45.0,
            model_confidence=0.85,
            adversarial_penalty=8.0,
            invalidation_levels=["Close below 2390.0"],
            bull_case=["H1 Bullish structure"],
            bear_case=[],
            risk_factors=["Minor volatility"],
            quality_gate=TradeQualityGateResult(passed=True, checks={"Regime": True}),
            decision="EXECUTE",
            execution_authorized=True
        )

        self.account = AccountSnapshot(
            login=12345,
            server="XM-Live",
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            free_margin=10000.0,
            margin_level=0.0,
            leverage=100
        )

    def test_risk_authorization_success(self):
        sym_info = {"trade_contract_size": 100, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        res = self.risk_engine.authorize_execution(self.valid_decision, self.account, [], sym_info)
        self.assertTrue(res["authorized"])
        self.assertGreater(res["lots"], 0.0)

    def test_risk_rejection_on_excessive_spread(self):
        sym_info = {"trade_contract_size": 100, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        res = self.risk_engine.authorize_execution(
            self.valid_decision, self.account, [], sym_info, current_spread_pips=50.0, max_allowed_spread_pips=35.0
        )
        self.assertFalse(res["authorized"])
        self.assertTrue(any("Spread" in r for r in res["reasons"]))

    def test_risk_rejection_on_max_open_positions(self):
        sym_info = {"trade_contract_size": 100, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}
        existing_pos = [
            PositionSnapshot(ticket=1, symbol="EURUSD", type="BUY", volume=0.1, open_price=1.08, current_price=1.08, sl=1.07, tp=1.10, profit=10, swap=0, commission=0, open_time=datetime.now(), magic=888),
            PositionSnapshot(ticket=2, symbol="GBPUSD", type="BUY", volume=0.1, open_price=1.27, current_price=1.27, sl=1.26, tp=1.29, profit=10, swap=0, commission=0, open_time=datetime.now(), magic=888),
        ]
        res = self.risk_engine.authorize_execution(self.valid_decision, self.account, existing_pos, sym_info)
        self.assertFalse(res["authorized"])
        self.assertTrue(any("Max Concurrent Positions" in r for r in res["reasons"]))

if __name__ == "__main__":
    unittest.main()
