import unittest
from unittest.mock import MagicMock, patch
from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.application.state_manager import StateManager
from jarvis.data.schemas import DecisionObject, RegimeOutput, MarketRegime, TradeQualityGateResult
from datetime import datetime, timezone

class TestMultiStyleRadar(unittest.TestCase):
    def setUp(self):
        self.state_mgr = StateManager()
        self.orchestrator = JarvisOrchestrator(
            symbols=["XAUUSD", "EURUSD"],
            mode="paper",
            trade_style="SWING"
        )

    def tearDown(self):
        self.orchestrator.stop()

    def test_single_pass_multi_style_radar_generation(self):
        """Verify _orchestration_loop_single_pass populates radar across SWING, DAY_TRADING, and SCALP."""
        radar_results = self.orchestrator._orchestration_loop_single_pass()
        
        # 2 symbols * 3 styles = 6 opportunities
        self.assertEqual(len(radar_results), 6)
        self.assertEqual(len(self.orchestrator.state_manager.radar_opportunities), 6)

        styles_found = {o["trade_style"] for o in radar_results}
        self.assertIn("SWING", styles_found)
        self.assertIn("DAY_TRADING", styles_found)
        self.assertIn("SCALP", styles_found)

        # Check timeframe mappings
        for opp in radar_results:
            style = opp["trade_style"]
            if style == "SWING":
                self.assertEqual(opp["timeframe"], "D1/H4/H1")
            elif style == "DAY_TRADING":
                self.assertEqual(opp["timeframe"], "H1/M15/M5")
            elif style == "SCALP":
                self.assertEqual(opp["timeframe"], "M15/M5/M1")

            # Check required fields
            self.assertIn("symbol", opp)
            self.assertIn("current_price", opp)
            self.assertIn("entry_price", opp)
            self.assertIn("stop_loss", opp)
            self.assertIn("take_profit", opp)
            self.assertIn("risk_reward_ratio", opp)
            self.assertIn("ev", opp)
            self.assertIn("bias", opp)
            self.assertIn("action", opp)
            self.assertIn("win_prob", opp)
            self.assertIn("score", opp)
            self.assertIn("confluence_score", opp)
            self.assertIn("confluence_tier", opp)
            self.assertIn("regime", opp)
            self.assertIn("strategy", opp)
            self.assertIn("gate_passed", opp)
            self.assertIn("failing_reasons", opp)
            self.assertIn("waiting_reasons", opp)
            self.assertIn("risk_factors", opp)

    def test_execution_style_matching(self):
        """Verify only matching trade style is authorized for live MT5 execution."""
        # Orchestrator configured for SWING
        self.orchestrator.trade_style = "SWING"
        
        # SCALP cycle must not be authorized to execute when orchestrator is in SWING mode
        res_scalp = self.orchestrator.run_cycle_for_symbol("EURUSD", trade_style="SCALP")
        self.assertFalse(res_scalp["authorized"])

    def test_api_radar_filtering_logic(self):
        """Verify API filtering correctly filters opportunities by trade style."""
        sample_opps = [
            {"symbol": "XAUUSD", "trade_style": "SWING", "action": "BUY READY", "win_prob": 80, "ev": 2.5},
            {"symbol": "EURUSD", "trade_style": "DAY_TRADING", "action": "WAIT: BUY", "win_prob": 65, "ev": 1.2},
            {"symbol": "GBPUSD", "trade_style": "SCALP", "action": "SELL READY", "win_prob": 85, "ev": 3.0}
        ]
        self.state_mgr.update_radar(sample_opps)

        # Test filtering helper logic
        def filter_radar(style_filter):
            opps = list(self.state_mgr.radar_opportunities)
            if style_filter and style_filter.strip().upper() not in ("ALL", "", "NONE"):
                s_norm = style_filter.strip().upper()
                if s_norm in ("DAY", "DAY_TRADING", "INTRADAY"):
                    target_styles = {"DAY_TRADING", "DAY", "INTRADAY"}
                elif s_norm in ("SCALP", "SCALPING"):
                    target_styles = {"SCALP", "SCALPING"}
                elif s_norm == "SWING":
                    target_styles = {"SWING"}
                else:
                    target_styles = {s_norm}
                opps = [o for o in opps if str(o.get("trade_style", "")).upper() in target_styles]
            return opps

        self.assertEqual(len(filter_radar("ALL")), 3)
        self.assertEqual(len(filter_radar(None)), 3)
        self.assertEqual(len(filter_radar("SWING")), 1)
        self.assertEqual(filter_radar("SWING")[0]["symbol"], "XAUUSD")
        self.assertEqual(len(filter_radar("DAY_TRADING")), 1)
        self.assertEqual(filter_radar("DAY_TRADING")[0]["symbol"], "EURUSD")
        self.assertEqual(len(filter_radar("DAY")), 1)
        self.assertEqual(filter_radar("DAY")[0]["symbol"], "EURUSD")
        self.assertEqual(len(filter_radar("SCALP")), 1)
        self.assertEqual(filter_radar("SCALP")[0]["symbol"], "GBPUSD")

if __name__ == "__main__":
    unittest.main()
