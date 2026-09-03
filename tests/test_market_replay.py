"""
Unit tests for Market Replay Engine, Realistic Execution Simulator, and Anti-Lookahead safety.
"""
import unittest
import pandas as pd
import numpy as np

from jarvis.historical.replay_engine import MarketReplayEngine, RealisticExecutionSimulator


class TestMarketReplayEngine(unittest.TestCase):

    def setUp(self):
        dates = pd.date_range("2026-01-01", periods=60, freq="1h", tz="UTC")
        self.df = pd.DataFrame({
            "time": dates,
            "open": [100.0] * 60,
            "high": [105.0] * 60,
            "low": [95.0] * 60,
            "close": [101.0] * 60,
            "tick_volume": [500] * 60,
            "spread": [1.5] * 60,
            "real_volume": [0] * 60
        })

    def test_anti_lookahead_guarantee(self):
        sim = RealisticExecutionSimulator()
        engine = MarketReplayEngine(self.df, symbol="XAUUSD", timeframe="H1", simulator=sim)
        engine.reset(start_idx=25)

        max_history_seen = []

        def inspect_step(bar, history, simulator):
            # The length of history must strictly equal the current index + 1
            self.assertEqual(history.iloc[-1]["time"], bar["time"])
            max_history_seen.append(len(history))

        res = engine.run_replay(inspect_step, start_idx=25, max_bars=10)
        self.assertEqual(res["bars_processed"], 10)
        self.assertEqual(max_history_seen[0], 26)
        self.assertEqual(max_history_seen[-1], 35)

    def test_realistic_execution_simulator_sl_tp(self):
        sim = RealisticExecutionSimulator(initial_balance=10000.0, commission_per_lot=5.0)
        engine = MarketReplayEngine(self.df, symbol="XAUUSD", timeframe="H1", simulator=sim)
        engine.reset(start_idx=10)

        step_res = engine.step()
        self.assertIsNotNone(step_res)
        bar, _ = step_res

        # Open BUY order with SL at 94.0 (below current low 95.0) and TP at 104.0
        order = sim.open_order(
            symbol="XAUUSD",
            order_type="BUY",
            volume=0.1,
            current_bar=bar,
            sl=94.0,
            tp=104.0
        )
        self.assertEqual(order.ticket, 700001)
        self.assertIn(order.ticket, sim.positions)

        # Advance with a bar that hits TP (High = 106.0)
        tp_bar = pd.Series({
            "time": "2026-01-01 12:00:00+00:00",
            "open": 101.0,
            "high": 106.0,
            "low": 100.0,
            "close": 105.0,
            "tick_volume": 600,
            "spread": 1.5,
            "real_volume": 0
        })
        sim.update_bar(tp_bar, "XAUUSD")

        # Position should be closed at TP!
        self.assertNotIn(order.ticket, sim.positions)
        self.assertEqual(len(sim.closed_trades), 1)
        closed = sim.closed_trades[0]
        self.assertEqual(closed.status, "CLOSED")
        self.assertIn("TP_HIT", closed.comment)
        self.assertTrue(closed.pnl > 0)
        self.assertTrue(sim.balance > 10000.0 - 5.0)  # Profitable after commission


if __name__ == "__main__":
    unittest.main()
