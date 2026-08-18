import unittest
from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.data.schemas import DecisionObject

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.orchestrator = JarvisOrchestrator(mode="paper")

    def tearDown(self):
        self.orchestrator.stop()

    def test_end_to_end_cycle(self):
        res = self.orchestrator.run_cycle_for_symbol("XAUUSD")
        self.assertIn("symbol", res)
        self.assertEqual(res["symbol"], "XAUUSD")
        
        decision = res["decision"]
        self.assertIsInstance(decision, DecisionObject)
        self.assertIn(decision.decision, ["EXECUTE", "WAIT", "NO_TRADE", "REJECT"])
        self.assertIsNotNone(decision.expected_value)
        self.assertIsNotNone(decision.quality_gate)
        self.assertTrue(len(decision.invalidation_levels) > 0)

if __name__ == "__main__":
    unittest.main()
