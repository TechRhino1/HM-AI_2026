import unittest
from engines.risk_engine import RiskManagerEngine

class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        settings = {
            "risk": {
                "max_risk_per_trade_pct": 0.5,
                "max_daily_loss_pct": 2.0,
                "max_open_positions": 3,
                "max_symbol_exposure_count": 1
            }
        }
        self.risk_manager = RiskManagerEngine(settings)

    def test_position_sizing_forex(self):
        account_info = {"equity": 10000.0}
        symbol_info = {
            "trade_contract_size": 100000,
            "trade_tick_value": 1.0,
            "trade_tick_size": 0.00001,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01
        }
        entry = 1.0850
        sl = 1.0830  # 20 pips risk
        # Risk amount = $10,000 * 0.5% = $50
        # Risk per lot = 0.0020 * 100,000 = $200
        # Lots = 50 / 200 = 0.25 lots
        lots = self.risk_manager.calculate_position_size(account_info, symbol_info, sl, entry)
        self.assertEqual(lots, 0.25)

    def test_daily_drawdown_limit(self):
        self.risk_manager.daily_starting_equity = 10000.0
        account_info = {"equity": 9750.0, "balance": 10000.0}  # 2.5% loss > 2.0% limit
        res = self.risk_manager.validate_risk_limits(account_info, [], "EURUSD", 1.5, {"max_allowed_spread_pips": 5.0})
        self.assertFalse(res["passed"])
        self.assertTrue(any("Max Daily Loss" in r for r in res["reasons"]))

    def test_max_open_positions(self):
        account_info = {"equity": 10000.0, "balance": 10000.0}
        positions = [{"symbol": "EURUSD"}, {"symbol": "GBPUSD"}, {"symbol": "XAUUSD"}]
        res = self.risk_manager.validate_risk_limits(account_info, positions, "USDJPY", 1.5, {"max_allowed_spread_pips": 5.0})
        self.assertFalse(res["passed"])

if __name__ == "__main__":
    unittest.main()
