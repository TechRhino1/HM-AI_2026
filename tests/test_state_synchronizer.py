import unittest
from jarvis.execution.mt5_client import MT5Client
from jarvis.execution.state_synchronizer import MT5StateSynchronizer
from jarvis.application.state_manager import StateManager
from jarvis.application.event_bus import EventBus

class TestStateSynchronizer(unittest.TestCase):
    def setUp(self):
        self.state_mgr = StateManager()
        self.event_bus = EventBus()
        self.mt5_client = MT5Client(mode="paper")
        self.synchronizer = MT5StateSynchronizer(
            mt5_client=self.mt5_client,
            state_manager=self.state_mgr,
            event_bus=self.event_bus
        )

    def test_sync_pass(self):
        result = self.synchronizer.sync_once()
        self.assertTrue(result["success"])
        self.assertGreater(result["login"], 0)
        self.assertGreater(result["equity"], 0)

        # Check state manager updated
        snap = self.state_mgr.get_state_snapshot()
        self.assertIsNotNone(snap["account"])
        self.assertEqual(snap["services"]["STATE_SYNC"], "ONLINE")

    def test_event_bus_reconciliation(self):
        events_received = []
        self.event_bus.subscribe("POSITION_OPENED", lambda payload: events_received.append(payload))

        # Manually invoke event
        self.event_bus.publish_sync("POSITION_OPENED", {"ticket": 123456})
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0]["ticket"], 123456)

if __name__ == "__main__":
    unittest.main()
