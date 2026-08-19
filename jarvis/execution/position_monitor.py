"""
JARVIS AI 4.0 — Continuous Position Monitor Engine.

A dedicated background thread that independently monitors and dynamically manages
EVERY open position (AI-opened and manually opened) at a 2-second resolution,
completely decoupled from the 15-60s orchestration scan cycle.

Management capabilities:
  - Emergency SL placement for manual trades with no SL or dangerously wide SL
  - 3-Stage micro breakeven + profit lock (Stages 1/2/3)
  - Structural S/R ratchet trailing (Higher-Low / Lower-High)
  - Regime-invalidation exit (regime flips against trade → tighten to 80% lock)
  - VWAP cross alert + optional tighten
  - Drawdown emergency brake (floating DD > 5% equity → all positions → breakeven)
  - Spread blowout protection (pauses modifications during extreme spread)
  - Momentum exhaustion exit (trend_score flip against trade)
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone

from jarvis.data.schemas import PositionSnapshot, MarketContext, AccountSnapshot
from jarvis.execution.mt5_client import MT5Client
from jarvis.application.state_manager import StateManager, GLOBAL_STATE
from jarvis.application.event_bus import EventBus, GLOBAL_EVENT_BUS
from jarvis.market.market_context import MarketContextEngine
from jarvis.market.data_feed import DataFeedEngine

logger = logging.getLogger("JARVIS_PositionMonitor")

# ─── Constants ─────────────────────────────────────────────────────────────────
MONITOR_INTERVAL_SEC      = 2.0    # Monitor loop tick rate
CONTEXT_CACHE_TTL_SEC     = 10.0   # Re-fetch market context every 10s per symbol
EMERGENCY_SL_ATR_MULT     = 2.0    # Auto-SL for manual trades: 2× ATR from entry
DANGEROUS_SL_ATR_MULT     = 3.0    # SL wider than 3× ATR → tighten to 2× ATR
MICRO_VOLUME_THRESH        = 0.03   # Volume <= this is treated as micro-position

# Profit lock thresholds (ATR multiples of profit_pips)
STAGE1_ATR_TRIGGER         = 1.0
STAGE1_BE_BUFFER           = 0.15
STAGE2_ATR_TRIGGER         = 1.6
STAGE2_PROFIT_LOCK         = 0.60
STAGE3_ATR_TRIGGER         = 2.0
STAGE3_PROFIT_LOCK_PCT     = 0.60
STD_ATR_TRIGGER            = 1.5
STD_BE_BUFFER              = 0.20
SR_ATR_BUFFER              = 0.20

# Regime invalidation triggers
REGIME_INVALIDATION_CONFIDENCE = 0.70   # Regime confidence required to act
FLOAT_DD_EMERGENCY_PCT         = 5.0    # % of equity — triggers emergency brake

# Magic number used by JARVIS AI orders (manual trades have different magic)
JARVIS_MAGIC_NUMBER        = 888999

# Spread blowout: pause modifications if spread > 2× typical
SPREAD_BLOWOUT_MULT        = 2.0


class PositionMonitorEngine:
    """
    Dedicated 2-second loop that manages all open positions independently of
    the main orchestration cycle. Covers both AI-placed and manual trades.
    """

    def __init__(
        self,
        mt5_client: MT5Client,
        data_feed: DataFeedEngine,
        context_engine: MarketContextEngine,
        state_manager: StateManager = GLOBAL_STATE,
        event_bus: EventBus = GLOBAL_EVENT_BUS,
    ):
        self.mt5_client     = mt5_client
        self.data_feed      = data_feed
        self.context_engine = context_engine
        self.state_manager  = state_manager
        self.event_bus      = event_bus

        self._running       = False
        self._thread: Optional[threading.Thread] = None

        # Per-symbol context cache  {symbol: (context, fetched_at)}
        self._ctx_cache: Dict[str, tuple] = {}
        self._ctx_lock = threading.Lock()

        # Per-ticket tracking: last action taken (to avoid log spam)
        self._last_action: Dict[int, str] = {}

    # ─── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop, daemon=True, name="position_monitor"
            )
            self._thread.start()
            logger.info("PositionMonitorEngine started (2s resolution).")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("PositionMonitorEngine stopped.")

    # ─── Main loop ─────────────────────────────────────────────────────────────

    def _monitor_loop(self):
        while self._running:
            start = time.monotonic()
            try:
                self._run_monitor_tick()
            except Exception as e:
                logger.error(f"PositionMonitor tick error: {e}", exc_info=True)
            elapsed = time.monotonic() - start
            sleep_time = max(0.0, MONITOR_INTERVAL_SEC - elapsed)
            time.sleep(sleep_time)

    def _run_monitor_tick(self):
        positions: List[PositionSnapshot] = self.state_manager.positions
        if not positions:
            return

        account: Optional[AccountSnapshot] = self.state_manager.account
        if account is None:
            return

        equity = account.equity
        balance = account.balance

        # ── Drawdown Emergency Brake ────────────────────────────────────────
        total_float_pnl = sum(p.profit for p in positions)
        float_dd_pct = abs(total_float_pnl / equity * 100) if (total_float_pnl < 0 and equity > 0) else 0.0
        emergency_brake = float_dd_pct >= FLOAT_DD_EMERGENCY_PCT

        if emergency_brake:
            logger.warning(
                f"🚨 EMERGENCY BRAKE: Floating DD={float_dd_pct:.1f}% exceeds {FLOAT_DD_EMERGENCY_PCT}% threshold. "
                f"Tightening ALL positions to breakeven."
            )

        # ── Per-position management ─────────────────────────────────────────
        for pos in positions:
            try:
                self._manage_single_position(pos, equity, balance, emergency_brake)
            except Exception as e:
                logger.error(f"Error managing position #{pos.ticket}: {e}", exc_info=True)

    # ─── Single-Position Logic ──────────────────────────────────────────────────

    def _manage_single_position(
        self,
        pos: PositionSnapshot,
        equity: float,
        balance: float,
        emergency_brake: bool,
    ):
        symbol  = pos.symbol
        is_manual = self._is_manual_trade(pos)
        regime  = self._get_cached_regime(symbol)

        # ── Fetch (or reuse cached) market context ──────────────────────────
        ctx = self._get_context(symbol)
        if ctx is None:
            logger.debug(f"No market context for {symbol} — skipping #{pos.ticket}")
            return

        c_price = ctx.current_price
        atr     = ctx.volatility.atr if ctx.volatility.atr > 0 else (c_price * 0.005)
        spread  = ctx.volatility.current_spread_pips

        # ── Spread blowout guard ────────────────────────────────────────────
        from jarvis.data.symbol_registry import resolve as _res
        try:
            spec = _res(symbol)
            typical_spread = spec.typical_spread_pips
        except Exception:
            typical_spread = 3.0
        if spread > (typical_spread * SPREAD_BLOWOUT_MULT):
            logger.warning(f"⚠️ Spread blowout {spread:.1f} pips on #{pos.ticket} — skipping modification.")
            return

        new_sl  = pos.sl
        new_tp  = pos.tp
        actions = []

        # ─────────────────────────────────────────────────────────────────────
        # EMERGENCY BRAKE: tighten everything to breakeven
        # ─────────────────────────────────────────────────────────────────────
        if emergency_brake:
            new_sl = self._emergency_breakeven(pos, c_price, atr, new_sl)
            if new_sl != pos.sl:
                actions.append(f"EMERGENCY_BRAKE→BE@{new_sl:.4f}")

        else:
            # ── 1. Manual trade: auto-set or tighten emergency SL ──────────
            if is_manual:
                new_sl, act = self._handle_manual_sl(pos, c_price, atr, new_sl)
                if act:
                    actions.append(act)

            # ── 2. Regime invalidation exit ────────────────────────────────
            new_sl, act = self._check_regime_invalidation(pos, ctx, regime, c_price, atr, new_sl)
            if act:
                actions.append(act)

            # ── 3. Core SL trailing (breakeven + profit lock + S/R ratchet) ──
            new_sl, sl_actions = self._trail_sl(pos, ctx, c_price, atr, new_sl, equity)
            actions.extend(sl_actions)

            # ── 4. VWAP cross awareness ────────────────────────────────────
            new_sl, act = self._check_vwap_cross(pos, ctx, c_price, atr, new_sl)
            if act:
                actions.append(act)

            # ── 5. Momentum exhaustion exit ───────────────────────────────
            new_sl, act = self._check_momentum_exhaustion(pos, ctx, c_price, atr, new_sl)
            if act:
                actions.append(act)

        # ── Apply modifications if anything changed ─────────────────────────
        sl_changed = abs(new_sl - pos.sl) > 0.0001
        tp_changed = abs(new_tp - pos.tp) > 0.0001

        if sl_changed or tp_changed:
            action_key = f"{new_sl:.4f}"
            if self._last_action.get(pos.ticket) != action_key:
                res = self.mt5_client.modify_position(pos.ticket, sl=new_sl, tp=new_tp)
                status = res.get("status") if res else "FAILED"
                if status == "MODIFIED" or (status == "FAILED" and "No changes" in str(res.get("reason", ""))):
                    self._last_action[pos.ticket] = action_key
                    log_tag = "[MANUAL]" if is_manual else "[AI]"
                    logger.info(
                        f"✅ {log_tag} #{pos.ticket} {pos.symbol} {pos.type} | "
                        f"SL: {pos.sl:.4f}→{new_sl:.4f} | "
                        f"Actions: {', '.join(actions)}"
                    )
                    self.event_bus.publish_sync("position_managed", {
                        "ticket": pos.ticket,
                        "symbol": symbol,
                        "is_manual": is_manual,
                        "old_sl": pos.sl,
                        "new_sl": new_sl,
                        "old_tp": pos.tp,
                        "new_tp": new_tp,
                        "actions": actions,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    logger.warning(f"⚠️ Modify failed for #{pos.ticket}: {res}")

    # ─── SL Trailing Core ──────────────────────────────────────────────────────

    def _trail_sl(
        self,
        pos: PositionSnapshot,
        ctx: MarketContext,
        c_price: float,
        atr: float,
        current_sl: float,
        equity: float,
    ):
        """Core trailing logic: breakeven stages + structural S/R ratchet."""
        new_sl  = current_sl
        actions = []
        st      = ctx.structure
        vol     = ctx.volatility
        atr_mult = 1.3 if vol.state in ("EXPANSION", "EXTREME") else 1.0
        is_micro = (pos.volume <= MICRO_VOLUME_THRESH) or (equity < 100)

        if pos.type == "BUY":
            profit_pips = c_price - pos.open_price

            if is_micro:
                # Stage 3 — 60% profit lock
                if profit_pips >= (atr * STAGE3_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price + (profit_pips * STAGE3_PROFIT_LOCK_PCT)
                    if candidate > new_sl:
                        new_sl = candidate
                        actions.append(f"STAGE3_60%@{new_sl:.4f}")

                # Stage 2 — profit lock 0.75R
                elif profit_pips >= (atr * STAGE2_ATR_TRIGGER * atr_mult) and new_sl < pos.open_price + (atr * STAGE2_PROFIT_LOCK):
                    candidate = pos.open_price + (atr * STAGE2_PROFIT_LOCK)
                    if candidate > new_sl:
                        new_sl = candidate
                        actions.append(f"STAGE2_BE+@{new_sl:.4f}")

                # Stage 1 — breakeven
                elif profit_pips >= (atr * STAGE1_ATR_TRIGGER * atr_mult) and new_sl < pos.open_price:
                    candidate = pos.open_price + (atr * STAGE1_BE_BUFFER)
                    if candidate > new_sl:
                        new_sl = candidate
                        actions.append(f"STAGE1_BE@{new_sl:.4f}")

            else:
                # Standard: move to breakeven at 1.5× ATR
                if profit_pips >= (atr * STD_ATR_TRIGGER * atr_mult) and new_sl < pos.open_price:
                    candidate = pos.open_price + (atr * STD_BE_BUFFER)
                    if candidate > new_sl:
                        new_sl = candidate
                        actions.append(f"STD_BE@{new_sl:.4f}")

            # Structural S/R ratchet — ratchet to higher-low support
            if st.higher_lows and st.demand_zone[0] > 0:
                struct_sl = st.demand_zone[0] - (atr * SR_ATR_BUFFER)
                if struct_sl > new_sl and struct_sl < c_price:
                    new_sl = struct_sl
                    actions.append(f"SR_RATCHET@{new_sl:.4f}")

            # Key level ratchet (from Phase 3 S/R clustering)
            if hasattr(st, "key_levels") and st.key_levels:
                support_levels = sorted(
                    [kl["price"] for kl in st.key_levels if kl.get("price", 0) < c_price],
                    reverse=True,
                )
                if support_levels:
                    key_sl = support_levels[0] - (atr * SR_ATR_BUFFER)
                    if key_sl > new_sl and key_sl < c_price:
                        new_sl = key_sl
                        actions.append(f"KEY_LEVEL@{new_sl:.4f}")

        elif pos.type == "SELL":
            profit_pips = pos.open_price - c_price

            if is_micro:
                if profit_pips >= (atr * STAGE3_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price - (profit_pips * STAGE3_PROFIT_LOCK_PCT)
                    if (new_sl == 0 or candidate < new_sl):
                        new_sl = candidate
                        actions.append(f"STAGE3_60%@{new_sl:.4f}")

                elif profit_pips >= (atr * STAGE2_ATR_TRIGGER * atr_mult) and (new_sl == 0 or new_sl > pos.open_price - (atr * STAGE2_PROFIT_LOCK)):
                    candidate = pos.open_price - (atr * STAGE2_PROFIT_LOCK)
                    if new_sl == 0 or candidate < new_sl:
                        new_sl = candidate
                        actions.append(f"STAGE2_BE+@{new_sl:.4f}")

                elif profit_pips >= (atr * STAGE1_ATR_TRIGGER * atr_mult) and (new_sl == 0 or new_sl > pos.open_price):
                    candidate = pos.open_price - (atr * STAGE1_BE_BUFFER)
                    if new_sl == 0 or candidate < new_sl:
                        new_sl = candidate
                        actions.append(f"STAGE1_BE@{new_sl:.4f}")

            else:
                if profit_pips >= (atr * STD_ATR_TRIGGER * atr_mult) and (new_sl == 0 or new_sl > pos.open_price):
                    candidate = pos.open_price - (atr * STD_BE_BUFFER)
                    if new_sl == 0 or candidate < new_sl:
                        new_sl = candidate
                        actions.append(f"STD_BE@{new_sl:.4f}")

            # Structural S/R ratchet — ratchet to lower-high resistance
            if st.lower_highs and st.supply_zone[1] > 0:
                struct_sl = st.supply_zone[1] + (atr * SR_ATR_BUFFER)
                if (new_sl == 0 or struct_sl < new_sl) and struct_sl > c_price:
                    new_sl = struct_sl
                    actions.append(f"SR_RATCHET@{new_sl:.4f}")

            # Key level ratchet
            if hasattr(st, "key_levels") and st.key_levels:
                resistance_levels = sorted(
                    [kl["price"] for kl in st.key_levels if kl.get("price", 0) > c_price]
                )
                if resistance_levels:
                    key_sl = resistance_levels[0] + (atr * SR_ATR_BUFFER)
                    if new_sl == 0 or key_sl < new_sl:
                        new_sl = key_sl
                        actions.append(f"KEY_LEVEL@{new_sl:.4f}")

        return new_sl, actions

    # ─── Manual Trade Handler ──────────────────────────────────────────────────

    def _handle_manual_sl(
        self,
        pos: PositionSnapshot,
        c_price: float,
        atr: float,
        current_sl: float,
    ):
        """Auto-set emergency SL for manual trades without one, or with dangerously wide SL."""
        action = None

        if pos.type == "BUY":
            if pos.sl == 0 or pos.sl < 0.0001:
                # No SL at all — set emergency at 2× ATR below entry
                new_sl = pos.open_price - (atr * EMERGENCY_SL_ATR_MULT)
                action = f"MANUAL_EMERGENCY_SL@{new_sl:.4f}"
                logger.warning(f"🛑 Manual trade #{pos.ticket} has NO SL! Auto-setting emergency SL @ {new_sl:.4f}")
                return new_sl, action
            sl_distance = pos.open_price - pos.sl
            if sl_distance > (atr * DANGEROUS_SL_ATR_MULT):
                # SL too wide — tighten to 2× ATR
                new_sl = pos.open_price - (atr * EMERGENCY_SL_ATR_MULT)
                if new_sl > current_sl:
                    action = f"MANUAL_TIGHTEN_SL@{new_sl:.4f}"
                    logger.warning(f"⚠️ Manual trade #{pos.ticket} SL too wide ({sl_distance:.2f} > {atr*DANGEROUS_SL_ATR_MULT:.2f}). Tightening to {new_sl:.4f}")
                    return new_sl, action

        elif pos.type == "SELL":
            if pos.sl == 0 or pos.sl < 0.0001:
                new_sl = pos.open_price + (atr * EMERGENCY_SL_ATR_MULT)
                action = f"MANUAL_EMERGENCY_SL@{new_sl:.4f}"
                logger.warning(f"🛑 Manual trade #{pos.ticket} has NO SL! Auto-setting emergency SL @ {new_sl:.4f}")
                return new_sl, action
            sl_distance = pos.sl - pos.open_price
            if sl_distance > (atr * DANGEROUS_SL_ATR_MULT):
                new_sl = pos.open_price + (atr * EMERGENCY_SL_ATR_MULT)
                if new_sl == 0 or new_sl < current_sl:
                    action = f"MANUAL_TIGHTEN_SL@{new_sl:.4f}"
                    logger.warning(f"⚠️ Manual trade #{pos.ticket} SL too wide. Tightening to {new_sl:.4f}")
                    return new_sl, action

        return current_sl, None

    # ─── Regime Invalidation ────────────────────────────────────────────────────

    def _check_regime_invalidation(
        self,
        pos: PositionSnapshot,
        ctx: MarketContext,
        regime: Optional[Any],
        c_price: float,
        atr: float,
        current_sl: float,
    ):
        """If the market regime flips strongly against the trade, tighten SL to lock 80% profit."""
        if regime is None:
            return current_sl, None

        try:
            regime_str = regime.primary_regime.value if hasattr(regime, "primary_regime") else str(regime)
            confidence = getattr(regime, "confidence", 0.0)

            if confidence < REGIME_INVALIDATION_CONFIDENCE:
                return current_sl, None

            is_invalidated = False
            if pos.type == "BUY" and ("BEAR" in regime_str or "REVERSAL" in regime_str):
                is_invalidated = True
            elif pos.type == "SELL" and ("BULL" in regime_str or "REVERSAL" in regime_str):
                is_invalidated = True

            if is_invalidated:
                profit_pips = (c_price - pos.open_price) if pos.type == "BUY" else (pos.open_price - c_price)
                if profit_pips > 0:
                    # Lock 80% of floating profit
                    if pos.type == "BUY":
                        candidate = pos.open_price + (profit_pips * 0.80)
                        if candidate > current_sl:
                            logger.info(
                                f"🔄 Regime invalidation for #{pos.ticket} ({regime_str} conf={confidence:.2f}) → "
                                f"80% profit lock @ {candidate:.4f}"
                            )
                            return candidate, f"REGIME_INVALIDATION@{candidate:.4f}"
                    else:
                        candidate = pos.open_price - (profit_pips * 0.80)
                        if current_sl == 0 or candidate < current_sl:
                            logger.info(
                                f"🔄 Regime invalidation for #{pos.ticket} ({regime_str} conf={confidence:.2f}) → "
                                f"80% profit lock @ {candidate:.4f}"
                            )
                            return candidate, f"REGIME_INVALIDATION@{candidate:.4f}"
                else:
                    # In loss — move to breakeven if possible
                    if pos.type == "BUY" and current_sl < pos.open_price - (atr * 0.1):
                        be = pos.open_price - (atr * 0.1)
                        if be > current_sl:
                            logger.info(f"🔄 Regime invalidation (losing) for #{pos.ticket} → BE @ {be:.4f}")
                            return be, f"REGIME_INVALIDATION_BE@{be:.4f}"
                    elif pos.type == "SELL" and (current_sl == 0 or current_sl > pos.open_price + (atr * 0.1)):
                        be = pos.open_price + (atr * 0.1)
                        if current_sl == 0 or be < current_sl:
                            logger.info(f"🔄 Regime invalidation (losing) for #{pos.ticket} → BE @ {be:.4f}")
                            return be, f"REGIME_INVALIDATION_BE@{be:.4f}"
        except Exception:
            pass

        return current_sl, None

    # ─── VWAP Cross Awareness ───────────────────────────────────────────────────

    def _check_vwap_cross(
        self,
        pos: PositionSnapshot,
        ctx: MarketContext,
        c_price: float,
        atr: float,
        current_sl: float,
    ):
        """If price crosses VWAP against the trade direction, warn and optionally tighten."""
        vwap = getattr(ctx, "vwap", 0.0)
        if vwap <= 0:
            return current_sl, None

        if pos.type == "BUY" and c_price < vwap:
            # Price dropped below VWAP — bearish signal for a BUY
            profit_pips = c_price - pos.open_price
            if profit_pips > 0:
                # Still profitable — tighten to 50% profit lock
                candidate = pos.open_price + (profit_pips * 0.50)
                if candidate > current_sl:
                    logger.info(f"📊 VWAP cross (below) on BUY #{pos.ticket} → 50% profit lock @ {candidate:.4f}")
                    return candidate, f"VWAP_CROSS_50%@{candidate:.4f}"

        elif pos.type == "SELL" and c_price > vwap:
            # Price rose above VWAP — bullish signal against a SELL
            profit_pips = pos.open_price - c_price
            if profit_pips > 0:
                candidate = pos.open_price - (profit_pips * 0.50)
                if current_sl == 0 or candidate < current_sl:
                    logger.info(f"📊 VWAP cross (above) on SELL #{pos.ticket} → 50% profit lock @ {candidate:.4f}")
                    return candidate, f"VWAP_CROSS_50%@{candidate:.4f}"

        return current_sl, None

    # ─── Momentum Exhaustion ───────────────────────────────────────────────────

    def _check_momentum_exhaustion(
        self,
        pos: PositionSnapshot,
        ctx: MarketContext,
        c_price: float,
        atr: float,
        current_sl: float,
    ):
        """If trend_score flips sign against trade, apply 80% profit lock."""
        trend_score = getattr(ctx.momentum, "trend_score", 0) if hasattr(ctx, "momentum") else 0
        profit_pips = (
            (c_price - pos.open_price) if pos.type == "BUY"
            else (pos.open_price - c_price)
        )
        if profit_pips <= 0:
            return current_sl, None

        if pos.type == "BUY" and trend_score < -20:
            candidate = pos.open_price + (profit_pips * 0.80)
            if candidate > current_sl:
                logger.info(f"⚡ Momentum exhaustion (score={trend_score}) BUY #{pos.ticket} → 80% lock @ {candidate:.4f}")
                return candidate, f"MOMENTUM_EXHAUST@{candidate:.4f}"

        elif pos.type == "SELL" and trend_score > 20:
            candidate = pos.open_price - (profit_pips * 0.80)
            if current_sl == 0 or candidate < current_sl:
                logger.info(f"⚡ Momentum exhaustion (score={trend_score}) SELL #{pos.ticket} → 80% lock @ {candidate:.4f}")
                return candidate, f"MOMENTUM_EXHAUST@{candidate:.4f}"

        return current_sl, None

    # ─── Emergency Breakeven ───────────────────────────────────────────────────

    def _emergency_breakeven(
        self,
        pos: PositionSnapshot,
        c_price: float,
        atr: float,
        current_sl: float,
    ) -> float:
        """Tighten SL to breakeven (entry ± small buffer) as fast as possible."""
        if pos.type == "BUY":
            be = pos.open_price + (atr * 0.05)
            return max(be, current_sl)
        else:
            be = pos.open_price - (atr * 0.05)
            return be if (current_sl == 0 or be < current_sl) else current_sl

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _is_manual_trade(self, pos: PositionSnapshot) -> bool:
        """Identifies trades NOT placed by JARVIS AI (manual dashboard or MT5 terminal)."""
        is_wrong_magic = (pos.magic != JARVIS_MAGIC_NUMBER)
        has_manual_comment = any(
            tag in pos.comment.upper()
            for tag in ("MANUAL", "DESK", "")
        )
        return is_wrong_magic or (pos.magic == 0)

    def _get_context(self, symbol: str) -> Optional[MarketContext]:
        """Returns cached context or fetches fresh context if TTL expired."""
        now = time.monotonic()
        with self._ctx_lock:
            cached = self._ctx_cache.get(symbol)
            if cached:
                ctx, fetched_at = cached
                if (now - fetched_at) < CONTEXT_CACHE_TTL_SEC:
                    return ctx

        # Fetch fresh context
        try:
            mtf_data = self.data_feed.fetch_multi_timeframe(symbol)
            ctx = self.context_engine.build_context(symbol, mtf_data)
            with self._ctx_lock:
                self._ctx_cache[symbol] = (ctx, now)
            return ctx
        except Exception as e:
            logger.debug(f"Context fetch failed for {symbol}: {e}")
            # Return last cached value even if stale rather than None
            with self._ctx_lock:
                cached = self._ctx_cache.get(symbol)
                if cached:
                    return cached[0]
            return None

    def _get_cached_regime(self, symbol: str) -> Optional[Any]:
        """Get the last known regime from state manager decisions."""
        try:
            decisions = self.state_manager._decisions  # type: ignore
            dec = decisions.get(symbol)
            if dec and hasattr(dec, "regime"):
                return dec.regime
        except Exception:
            pass
        return None

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "monitored_symbols": list(self._ctx_cache.keys()),
            "last_actions": dict(self._last_action),
        }
