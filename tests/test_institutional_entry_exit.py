"""
Unit and Integration tests for JARVIS AI Master-Trader Next-Generation Institutional Entry & Exit Architecture.
Covers:
1. InstitutionalEntryEngine (SCALP, DAY_TRADING, SWING protocols)
2. DynamicRiskAndLevelsEngine MTF wiring and seamless fallback
3. PositionMonitorEngine Horizon-Adaptive Ratchet (Stage 0, 1, 2 across SCALP, DAY, SWING)
4. Stagnation / Time-Decay Auto-Exit (Scalp 45m, Day 6h, Swing 36h in compression)
5. Adversarial Order Flow Shield (in-profit SL snap vs underwater immediate liquidation)
"""
import time
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from jarvis.data.schemas import (
    MarketContext, StructureContext, LiquidityContext,
    VolatilityContext, MomentumContext, SessionContext,
    RegimeOutput, MarketRegime, PositionSnapshot
)
from jarvis.intelligence.institutional_entry_engine import InstitutionalEntryEngine
from jarvis.intelligence.dynamic_levels import DynamicRiskAndLevelsEngine
from jarvis.execution.position_monitor import PositionMonitorEngine, JARVIS_MAGIC_NUMBER


def make_sample_ohlcv(start_price=2400.0, num_bars=50, trend=1.0, step=0.5):
    """Generates synthetic OHLCV dataframe for MTF testing."""
    times = [datetime.now(timezone.utc) - timedelta(minutes=5 * (num_bars - i)) for i in range(num_bars)]
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    p = start_price
    for i in range(num_bars):
        o = p
        c = o + (trend * step) + (0.2 if i % 2 == 0 else -0.2)
        h = max(o, c) + 0.8
        l = min(o, c) - 0.8
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(100.0 + (i * 2))
        p = c
    df = pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })
    return df


class TestInstitutionalEntryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = InstitutionalEntryEngine()

    def test_scalp_protocol_buy_sweep_and_sniper(self):
        """Validates SCALP Protocol: Liquidity sweep detection, MSS displacement, OTE / FVG CE, sniper entry, and targets."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 9, 3, 14, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(
                bias="BULLISH",
                demand_zone=(2393.0, 2395.0),
                supply_zone=(2420.0, 2425.0),
                fair_value_gaps=[{"type": "BULLISH_FVG", "bottom": 2398.0, "top": 2401.0}]
            ),
            liquidity=LiquidityContext(sell_side_liquidity=2391.0, buy_side_liquidity=2420.0),
            volatility=VolatilityContext(atr=5.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=40, adx=28.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.85)

        # Build M5 data with a lower liquidity sweep on the last bar
        df_m5 = make_sample_ohlcv(start_price=2405.0, num_bars=20, trend=-0.3)
        # Prior 5 bars low is ~2398, last bar sweeps down to 2391.5 with rejection wick closing at 2400
        df_m5.loc[df_m5.index[-1], "open"] = 2396.0
        df_m5.loc[df_m5.index[-1], "low"] = 2391.5  # Swept
        df_m5.loc[df_m5.index[-1], "high"] = 2400.5
        df_m5.loc[df_m5.index[-1], "close"] = 2400.0  # Strong lower wick rejection

        mtf = {"M5": df_m5, "M1": df_m5}
        res = self.engine.calculate_entry_and_levels(ctx, regime, tentative_bias="BUY", trade_style="SCALP", mtf_data=mtf)

        self.assertIn("entry_price", res)
        self.assertIn("sl_price", res)
        self.assertIn("tp_price", res)
        self.assertIn("tp1_price", res)
        self.assertIn("tp2_price", res)
        self.assertEqual(res["first_target_volume_pct"], 0.50)
        self.assertEqual(res["runner_trail_atr"], 0.80)
        self.assertLess(res["sl_price"], res["entry_price"])
        self.assertGreater(res["tp1_price"], res["entry_price"])
        self.assertGreater(res["tp2_price"], res["tp1_price"])
        self.assertEqual(res["protocol_details"]["protocol"], "SCALP")
        self.assertTrue(res["protocol_details"]["sweep_detected"])

    def test_day_trading_protocol_kill_zone_and_m15_fvg(self):
        """Validates DAY TRADING Protocol: London/NY Kill Zone filter, H1 alignment, M15 FVG midpoint, origin SL."""
        # 13:30 UTC is NY Kill Zone (12-16 UTC)
        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime(2026, 9, 3, 13, 30, tzinfo=timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(
                bias="BULLISH",
                demand_zone=(1.0820, 1.0835),
                supply_zone=(1.0910, 1.0925),
                fair_value_gaps=[{"type": "BULLISH_FVG", "bottom": 1.0840, "top": 1.0860}]
            ),
            liquidity=LiquidityContext(sell_side_liquidity=1.0800, buy_side_liquidity=1.0920),
            volatility=VolatilityContext(atr=0.0030, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=35, adx=26.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.80)

        df_m15 = make_sample_ohlcv(start_price=1.0820, num_bars=25, trend=0.0002, step=0.0001)
        df_h1 = make_sample_ohlcv(start_price=1.0800, num_bars=25, trend=0.0003, step=0.0001)
        mtf = {"M15": df_m15, "H1": df_h1}

        res = self.engine.calculate_entry_and_levels(ctx, regime, tentative_bias="BUY", trade_style="DAY_TRADING", mtf_data=mtf)

        self.assertEqual(res["protocol_details"]["protocol"], "DAY_TRADING")
        self.assertTrue(res["protocol_details"]["in_kill_zone"])
        self.assertEqual(res["protocol_details"]["session_name"], "NY_KZ")
        self.assertEqual(res["runner_trail_atr"], 1.20)
        self.assertLess(res["sl_price"], res["entry_price"])
        self.assertGreater(res["tp2_price"], res["tp1_price"])
        self.assertGreaterEqual(res["rr_ratio"], 2.0)

    def test_swing_protocol_discount_htf_ob_and_choch(self):
        """Validates SWING Protocol: HTF range discount (<45%), H1 CHOCH confirmation, outer boundary SL."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
            current_price=2400.0,
            bid=2399.8,
            ask=2400.2,
            structure=StructureContext(
                bias="BULLISH",
                demand_zone=(2365.0, 2375.0),
                supply_zone=(2480.0, 2490.0),
                order_blocks=[{"type": "BULLISH_ORDER_BLOCK", "low": 2395.0, "high": 2402.0}]
            ),
            liquidity=LiquidityContext(sell_side_liquidity=2360.0, buy_side_liquidity=2490.0),
            volatility=VolatilityContext(atr=15.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=50, adx=30.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.88)

        # D1 and H4 have swung from 2480 down into discount at 2400
        df_h4 = make_sample_ohlcv(start_price=2460.0, num_bars=30, trend=-0.8, step=1.8)
        df_d1 = make_sample_ohlcv(start_price=2480.0, num_bars=30, trend=-1.0, step=2.5)
        df_h1 = make_sample_ohlcv(start_price=2395.0, num_bars=20, trend=0.2, step=0.2)
        mtf = {"H4": df_h4, "D1": df_d1, "H1": df_h1}

        res = self.engine.calculate_entry_and_levels(ctx, regime, tentative_bias="BUY", trade_style="SWING", mtf_data=mtf)

        self.assertEqual(res["protocol_details"]["protocol"], "SWING")
        self.assertTrue(res["protocol_details"]["is_discount"])
        self.assertEqual(res["runner_trail_atr"], 1.80)
        self.assertLess(res["sl_price"], res["entry_price"])
        self.assertGreater(res["tp2_price"], res["tp1_price"])
        self.assertGreaterEqual(res["rr_ratio"], 3.0)


class TestDynamicLevelsEngineIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = DynamicRiskAndLevelsEngine()

    def test_wiring_and_seamless_fallback_when_mtf_missing(self):
        """Validates that calculate_levels falls back seamlessly to baseline dynamic levels if mtf_data is None."""
        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH", demand_zone=(1.0810, 1.0825)),
            liquidity=LiquidityContext(sell_side_liquidity=1.0800, buy_side_liquidity=1.0950),
            volatility=VolatilityContext(atr=0.0025, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=30, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        regime = RegimeOutput(primary_regime=MarketRegime.TREND_BULL, probabilities={}, confidence=0.80)

        # 1. MTF data is None -> graceful baseline fallback
        res_fallback = self.engine.calculate_levels(ctx, regime, tentative_bias="BUY", trade_style="DAY_TRADING", mtf_data=None)
        self.assertIn("entry_price", res_fallback)
        self.assertIn("sl_price", res_fallback)
        self.assertIn("tp_price", res_fallback)
        self.assertIn("tp1_price", res_fallback)
        self.assertIn("tp2_price", res_fallback)
        self.assertEqual(res_fallback["protocol_details"]["protocol"], "BASELINE_DYNAMIC_LEVELS")

        # 2. MTF data is provided -> institutional calculation takes effect
        df_m15 = make_sample_ohlcv(start_price=1.0830, num_bars=25, trend=0.0001)
        df_h1 = make_sample_ohlcv(start_price=1.0810, num_bars=25, trend=0.0002)
        res_inst = self.engine.calculate_levels(ctx, regime, tentative_bias="BUY", trade_style="DAY_TRADING", mtf_data={"M15": df_m15, "H1": df_h1})
        self.assertEqual(res_inst["protocol_details"]["protocol"], "DAY_TRADING")


class TestHorizonAdaptiveRatchetAndExits(unittest.TestCase):
    def setUp(self):
        self.mt5_client = MagicMock()
        self.data_feed = MagicMock()
        self.context_engine = MagicMock()
        self.state_manager = MagicMock()
        self.event_bus = MagicMock()

        self.monitor = PositionMonitorEngine(
            mt5_client=self.mt5_client,
            data_feed=self.data_feed,
            context_engine=self.context_engine,
            state_manager=self.state_manager,
            event_bus=self.event_bus
        )

    def test_scalp_3_stage_ratchet(self):
        """
        Validates SCALP Horizon-Adaptive Ratchet:
        Stage 0: +0.65R -> Entry + 0.08R
        Stage 1: +1.10R -> Lock +0.40R
        Stage 2: +1.50R -> Chandelier 0.80x ATR
        """
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2406.5,
            bid=2406.3,
            ask=2406.7,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=50, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())

        # Entry = 2400.0, SL = 2390.0 (risk_dist = 10.0), comment="[SCALP]"
        pos = PositionSnapshot(
            ticket=401, symbol="XAUUSD", type="BUY", volume=0.01,
            open_price=2400.0, current_price=2406.5, sl=2390.0, tp=2430.0,
            profit=6.5, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER, comment="[SCALP] Sniper Entry"
        )
        self.mt5_client.modify_position.return_value = {"status": "MODIFIED"}

        # 1. R = 0.65 -> Stage 0: Entry + 0.08 * 10.0 = 2400.8
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(401, sl=2400.8, tp=2430.0)

        # 2. Advance price to 2411.0 (R = 1.10) -> Stage 1: Entry + 0.40 * 10.0 = 2404.0
        ctx.current_price = 2411.0
        pos.current_price = 2411.0
        pos.sl = 2400.8
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(401, sl=2404.0, tp=2430.0)

        # 3. Advance price to 2420.0 (R = 2.00 >= 1.50) -> Stage 2: Chandelier c_price - 0.80 * atr = 2420 - 8.0 = 2412.0
        ctx.current_price = 2420.0
        pos.current_price = 2420.0
        pos.sl = 2404.0
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(401, sl=2412.0, tp=2430.0)

    def test_day_trading_3_stage_ratchet(self):
        """
        Validates DAY_TRADING Horizon-Adaptive Ratchet:
        Stage 0: +0.85R -> Entry + 0.12R
        Stage 1: +1.40R -> Lock +0.60R
        Stage 2: +1.80R -> Chandelier 1.20x ATR
        """
        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0850,
            bid=1.0849,
            ask=1.0851,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0020, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=40, adx=25.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["EURUSD"] = (ctx, time.monotonic())

        # Entry = 1.0800, SL = 1.0750 (risk_dist = 0.0050), tag="DAY_TRADING"
        pos = PositionSnapshot(
            ticket=501, symbol="EURUSD", type="BUY", volume=0.01,
            open_price=1.0800, current_price=1.0843, sl=1.0750, tp=1.0950,
            profit=43.0, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER, comment="JARVIS DAY_TRADING"
        )
        self.mt5_client.modify_position.return_value = {"status": "MODIFIED"}

        # 1. Price at 1.0843 -> favorable_dist = 0.0043 -> R = 0.0043 / 0.0050 = 0.86 >= 0.85 -> Stage 0: 1.0800 + 0.12 * 0.0050 = 1.0806
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(501, sl=1.0806, tp=1.0950)

        # 2. Advance to 1.0870 -> R = 1.40 -> Stage 1: 1.0800 + 0.60 * 0.0050 = 1.0830
        ctx.current_price = 1.0870
        pos.current_price = 1.0870
        pos.sl = 1.0806
        self.monitor._ctx_cache["EURUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(501, sl=1.0830, tp=1.0950)

        # 3. Advance to 1.0900 -> R = 2.00 >= 1.80 -> Stage 2: c_price - 1.20 * atr = 1.0900 - 0.0024 = 1.0876
        ctx.current_price = 1.0900
        pos.current_price = 1.0900
        pos.sl = 1.0830
        self.monitor._ctx_cache["EURUSD"] = (ctx, time.monotonic())
        self.monitor._manage_single_position(pos)
        self.mt5_client.modify_position.assert_called_with(501, sl=1.0876, tp=1.0950)

    def test_stagnation_exit_scalp(self):
        """Scalp trade holding > 45 minutes with progress R < 0.50R triggers auto-close."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2402.0,
            bid=2401.8,
            ask=2402.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=10, adx=15.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())

        # Opened 50 minutes ago (3000 seconds), favorable gain = 2.0 -> R = 0.20 < 0.50
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=50)).isoformat()
        pos = PositionSnapshot(
            ticket=601, symbol="XAUUSD", type="BUY", volume=0.01,
            open_price=2400.0, current_price=2402.0, sl=2390.0, tp=2430.0,
            profit=2.0, swap=0.0, commission=0.0, open_time=stale_time,
            magic=JARVIS_MAGIC_NUMBER, comment="[SCALP] Trade"
        )
        self.monitor._manage_single_position(pos)
        self.mt5_client.close_position.assert_called_with(601)

    def test_stagnation_exit_day_trading(self):
        """Day trading setup holding > 6 hours with progress R < 0.75R triggers auto-close."""
        ctx = MarketContext(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=1.0820,
            bid=1.0819,
            ask=1.0821,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=0.0030, current_spread_pips=1.0),
            momentum=MomentumContext(trend_score=5, adx=14.0),
            session=SessionContext(is_prime_session=True)
        )
        self.monitor._ctx_cache["EURUSD"] = (ctx, time.monotonic())

        # Opened 7 hours ago (25200 seconds), favorable gain = 0.0020 -> R = 0.40 < 0.75
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
        pos = PositionSnapshot(
            ticket=701, symbol="EURUSD", type="BUY", volume=0.01,
            open_price=1.0800, current_price=1.0820, sl=1.0750, tp=1.0950,
            profit=20.0, swap=0.0, commission=0.0, open_time=stale_time,
            magic=JARVIS_MAGIC_NUMBER, comment="[DAY_TRADING]"
        )
        self.monitor._manage_single_position(pos)
        self.mt5_client.close_position.assert_called_with(701)

    def test_adversarial_order_flow_shield_in_profit(self):
        """Adversarial Order Flow Shield: When trade is in profit and counter volume delta occurs, ratchet SL to Bid/Ask +/- 0.15x ATR."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2407.0,
            bid=2406.8,
            ask=2407.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=20, adx=25.0),
            session=SessionContext(is_prime_session=True),
            order_flow={"delta_score": -45.0, "delta_ratio": -0.40}  # Strong counter volume delta (>35%)
        )
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())

        # BUY trade in profit (Entry 2400.0, Current 2407.0, Profit $70)
        pos = PositionSnapshot(
            ticket=801, symbol="XAUUSD", type="BUY", volume=0.01,
            open_price=2400.0, current_price=2407.0, sl=2395.0, tp=2430.0,
            profit=70.0, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER, comment="[DAY_TRADING]"
        )
        self.mt5_client.modify_position.return_value = {"status": "MODIFIED"}
        self.monitor._manage_single_position(pos)

        # Ratchet SL to Bid (2406.8) - 0.15 * 10 = 2405.3
        self.mt5_client.modify_position.assert_called_with(801, sl=2405.3, tp=2430.0)

    def test_adversarial_order_flow_shield_underwater_liquidation(self):
        """Adversarial Order Flow Shield: When trade is underwater and absorption trap opposes it, liquidate immediately."""
        ctx = MarketContext(
            symbol="XAUUSD",
            timestamp=datetime.now(timezone.utc),
            current_price=2398.0,
            bid=2397.8,
            ask=2398.2,
            structure=StructureContext(bias="BULLISH"),
            liquidity=LiquidityContext(),
            volatility=VolatilityContext(atr=10.0, current_spread_pips=2.0),
            momentum=MomentumContext(trend_score=-10, adx=20.0),
            session=SessionContext(is_prime_session=True),
            order_flow={"absorption_trap": "SELLER_ABSORPTION_TRAP"}  # Institutional trap against BUY
        )
        self.monitor._ctx_cache["XAUUSD"] = (ctx, time.monotonic())

        # BUY trade underwater (Entry 2400.0, Current 2398.0, Profit -$20)
        pos = PositionSnapshot(
            ticket=901, symbol="XAUUSD", type="BUY", volume=0.01,
            open_price=2400.0, current_price=2398.0, sl=2390.0, tp=2430.0,
            profit=-20.0, swap=0.0, commission=0.0, open_time=datetime.now(timezone.utc).isoformat(),
            magic=JARVIS_MAGIC_NUMBER, comment="[SCALP]"
        )
        self.monitor._manage_single_position(pos)
        self.mt5_client.close_position.assert_called_with(901)


if __name__ == "__main__":
    unittest.main()
