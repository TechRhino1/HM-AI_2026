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

from jarvis.data.schemas import PositionSnapshot, MarketContext, AccountSnapshot, MarketRegime
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
STAGE1_ATR_TRIGGER         = 0.9    # Stage 1 micro-position BE trigger (0.9x ATR, earlier BE for higher win rate)
STAGE1_BE_BUFFER           = 0.15   # Buffer above/below entry for Stage 1 BE
STAGE2_ATR_TRIGGER         = 1.4    # Stage 2 Profit lock trigger (0.60x ATR, earlier profit lock)
STAGE2_PROFIT_LOCK         = 0.60   # Lock 0.60x ATR profit
STAGE3_ATR_TRIGGER         = 2.0    # Stage 3 Profit lock trigger (60% profit lock)
STAGE3_PROFIT_LOCK_PCT     = 0.60   # Lock 60% of total unrealized profit
STD_ATR_TRIGGER            = 1.5    # Standard-position BE trigger (1.5x ATR)
STD_BE_BUFFER              = 0.20   # Buffer above/below entry for Standard BE
SR_ATR_BUFFER              = 0.20   # S/R ratchet buffer
PARTIAL_TP_TRIGGER_R       = 1.0    # Default partial TP trigger (1.0R)
PARTIAL_CLOSE_PCT          = 0.50   # 50% scale out at partial target

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
        # Per-ticket tracking for partial closes (§B-2 / §B-3)
        self._partially_closed_tickets: Set[int] = set()
        # Per-ticket live MFE high-water mark tracking (E2)
        self._peak_favorable_price: Dict[int, float] = {}
        # Autonomous dynamic trailing tracking
        self._initial_risk_dist: Dict[int, float] = {}
        self._highest_favorable_price: Dict[int, float] = {}

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

        # ── Prune memory for closed tickets ─────────────────────────────────
        active_tickets = {p.ticket for p in positions}
        self._partially_closed_tickets = {t for t in self._partially_closed_tickets if t in active_tickets}
        self._last_action = {t: act for t, act in self._last_action.items() if t in active_tickets}
        self._peak_favorable_price = {t: pr for t, pr in self._peak_favorable_price.items() if t in active_tickets}
        self._initial_risk_dist = {t: r for t, r in self._initial_risk_dist.items() if t in active_tickets}
        self._highest_favorable_price = {t: pr for t, pr in self._highest_favorable_price.items() if t in active_tickets}

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
        equity: float = 10000.0,
        balance: float = 10000.0,
        emergency_brake: bool = False,
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
            pip_size = spec.pip_size if spec.pip_size > 0 else 0.0001
            digits = spec.digits
        except Exception:
            typical_spread = 3.0
            pip_size = 0.0001
            digits = 5

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
            # ── 0. Partial Profit-Taking (§B-2 / §B-3) ──────────────────────────
            if pos.ticket not in self._partially_closed_tickets and pos.volume >= 0.02:
                decision_obj = self.state_manager.latest_decisions.get(symbol)
                first_target = getattr(decision_obj, "first_target_price", None)
                target_pct = getattr(decision_obj, "first_target_volume_pct", PARTIAL_CLOSE_PCT)

                risk_dist_init = abs(pos.open_price - pos.sl) if pos.sl > 0 else (atr * 1.5)
                if not first_target or first_target <= 0:
                    first_target = (pos.open_price + (risk_dist_init * PARTIAL_TP_TRIGGER_R)) if pos.type == "BUY" else (pos.open_price - (risk_dist_init * PARTIAL_TP_TRIGGER_R))

                is_target_hit = (c_price >= first_target) if pos.type == "BUY" else (c_price <= first_target)
                if is_target_hit:
                    close_volume = round(pos.volume * target_pct, 2)
                    remaining_volume = round(pos.volume - close_volume, 2)
                    if close_volume >= 0.01 and remaining_volume >= 0.01:
                        p_res = self.mt5_client.close_position(pos.ticket, volume=close_volume)
                        if p_res and p_res.get("status") in ("PARTIALLY_CLOSED", "CLOSED"):
                            self._partially_closed_tickets.add(pos.ticket)
                            logger.info(f"🎯 PARTIAL TP HIT: #{pos.ticket} {symbol} closed {close_volume} lots @ {c_price:.4f}. Remaining: {remaining_volume}")
                            actions.append(f"PARTIAL_TP_{int(target_pct*100)}%@{c_price:.4f}")
                            # Immediately ratchet SL to Breakeven + buffer on the remaining size
                            be_candidate = (pos.open_price + (atr * STAGE1_BE_BUFFER)) if pos.type == "BUY" else (pos.open_price - (atr * STAGE1_BE_BUFFER))
                            if pos.type == "BUY" and be_candidate > new_sl and be_candidate < c_price:
                                new_sl = be_candidate
                                actions.append(f"PARTIAL_BE@{new_sl:.4f}")
                            elif pos.type == "SELL" and (new_sl == 0 or be_candidate < new_sl) and be_candidate > c_price:
                                new_sl = be_candidate
                                actions.append(f"PARTIAL_BE@{new_sl:.4f}")

            # ── 1. Manual trade: auto-set or tighten emergency SL ──────────
            if is_manual:
                new_sl, act = self._handle_manual_sl(pos, c_price, atr, new_sl)
                if act:
                    actions.append(act)

            # ── 1.5 Adversarial Order Flow Shield ───────────────────────────
            shield_triggered, shield_action = self._check_adversarial_order_flow_shield(pos, ctx, c_price, atr, digits)
            if shield_triggered:
                if shield_action == "CLOSE":
                    logger.warning(
                        f"🛡️ ADVERSARIAL ORDER FLOW SHIELD: Closing underwater/flat #{pos.ticket} ({pos.symbol} {pos.type}) "
                        f"to prevent full stop-out."
                    )
                    self.mt5_client.close_position(pos.ticket)
                    return
                elif shield_action is not None and isinstance(shield_action, (int, float)):
                    shield_sl = float(shield_action)
                    if pos.type == "BUY" and shield_sl > new_sl and shield_sl < c_price:
                        new_sl = shield_sl
                        actions.append(f"ADVERSARIAL_SHIELD@{new_sl:.4f}")
                    elif pos.type == "SELL" and (new_sl == 0 or shield_sl < new_sl) and shield_sl > c_price:
                        new_sl = shield_sl
                        actions.append(f"ADVERSARIAL_SHIELD@{new_sl:.4f}")

            # ── 2. Autonomous Horizon-Adaptive Trailing & R-Multiple Management ──
            if pos.ticket not in self._initial_risk_dist:
                self._initial_risk_dist[pos.ticket] = abs(pos.open_price - pos.sl) if pos.sl > 0 else (1.5 * atr)
            risk_dist = max(self._initial_risk_dist[pos.ticket], pip_size * 5)

            style = self._determine_position_style(pos, ctx)
            if style == "SCALP":
                s0_trigger, s0_lock = 0.65, 0.08
                s1_trigger, s1_lock = 1.10, 0.40
                s2_trigger, s2_atr  = 1.50, 0.80
            elif style in ("DAY_TRADING", "DAY", "INTRADAY"):
                s0_trigger, s0_lock = 0.85, 0.12
                s1_trigger, s1_lock = 1.40, 0.60
                s2_trigger, s2_atr  = 1.80, 1.20
            elif style == "SWING":
                s0_trigger, s0_lock = 1.10, 0.20
                s1_trigger, s1_lock = 1.80, 0.85
                s2_trigger, s2_atr  = 2.20, 1.80
            else:  # LEGACY / Untagged baseline
                s0_trigger, s0_lock = 0.80, 0.10
                s1_trigger, s1_lock = 1.20, 0.40
                s2_trigger, s2_atr  = 1.50, 1.20

            if pos.type == "BUY":
                prev_high = self._highest_favorable_price.get(pos.ticket, pos.open_price)
                high_price = max(prev_high, c_price)
                self._highest_favorable_price[pos.ticket] = high_price
                self._peak_favorable_price[pos.ticket] = high_price
                favorable_dist = max(0.0, high_price - pos.open_price)
                r_multiple = round(favorable_dist / max(risk_dist, 1e-6), 4)

                # Stage 2 (Horizon-Adaptive Chandelier Trail)
                if r_multiple >= s2_trigger:
                    cand_sl = round(c_price - (s2_atr * atr), digits)
                    if cand_sl > new_sl and cand_sl < c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE2_CHANDELIER@{new_sl:.4f}")
                # Stage 1 (Profit Floor Lock)
                elif r_multiple >= s1_trigger:
                    cand_sl = round(pos.open_price + (s1_lock * risk_dist), digits)
                    if cand_sl > new_sl and cand_sl < c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE1_PROFIT_FLOOR@{new_sl:.4f}")
                # Stage 0 (Zero-Risk Lock)
                elif r_multiple >= s0_trigger:
                    cand_sl = round(pos.open_price + (s0_lock * risk_dist), digits)
                    if cand_sl > new_sl and cand_sl < c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE0_ZERO_RISK@{new_sl:.4f}")

                # Structural S/R ratchet — ratchet to higher-low support
                if hasattr(ctx, "structure") and ctx.structure:
                    st = ctx.structure
                    if getattr(st, "higher_lows", False) and st.demand_zone[0] > 0:
                        struct_sl = round(st.demand_zone[0] - (atr * SR_ATR_BUFFER), digits)
                        if struct_sl > new_sl and struct_sl < c_price:
                            new_sl = struct_sl
                            actions.append(f"SR_RATCHET@{new_sl:.4f}")

                    if hasattr(st, "key_levels") and st.key_levels:
                        support_levels = sorted(
                            [kl["price"] for kl in st.key_levels if kl.get("price", 0) < c_price],
                            reverse=True,
                        )
                        if support_levels:
                            key_sl = round(support_levels[0] - (atr * SR_ATR_BUFFER), digits)
                            if key_sl > new_sl and key_sl < c_price:
                                new_sl = key_sl
                                actions.append(f"KEY_LEVEL@{new_sl:.4f}")

            elif pos.type == "SELL":
                prev_low = self._highest_favorable_price.get(pos.ticket, pos.open_price)
                low_price = min(prev_low, c_price)
                self._highest_favorable_price[pos.ticket] = low_price
                self._peak_favorable_price[pos.ticket] = low_price
                favorable_dist = max(0.0, pos.open_price - low_price)
                r_multiple = round(favorable_dist / max(risk_dist, 1e-6), 4)

                # Stage 2 (Horizon-Adaptive Chandelier Trail)
                if r_multiple >= s2_trigger:
                    cand_sl = round(c_price + (s2_atr * atr), digits)
                    if (new_sl == 0 or cand_sl < new_sl) and cand_sl > c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE2_CHANDELIER@{new_sl:.4f}")
                # Stage 1 (Profit Floor Lock)
                elif r_multiple >= s1_trigger:
                    cand_sl = round(pos.open_price - (s1_lock * risk_dist), digits)
                    if (new_sl == 0 or cand_sl < new_sl) and cand_sl > c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE1_PROFIT_FLOOR@{new_sl:.4f}")
                # Stage 0 (Zero-Risk Lock)
                elif r_multiple >= s0_trigger:
                    cand_sl = round(pos.open_price - (s0_lock * risk_dist), digits)
                    if (new_sl == 0 or cand_sl < new_sl) and cand_sl > c_price:
                        new_sl = cand_sl
                        actions.append(f"STAGE0_ZERO_RISK@{new_sl:.4f}")

                # Structural S/R ratchet — ratchet to lower-high resistance
                if hasattr(ctx, "structure") and ctx.structure:
                    st = ctx.structure
                    if getattr(st, "lower_highs", False) and st.supply_zone[1] > 0:
                        struct_sl = round(st.supply_zone[1] + (atr * SR_ATR_BUFFER), digits)
                        if (new_sl == 0 or struct_sl < new_sl) and struct_sl > c_price:
                            new_sl = struct_sl
                            actions.append(f"SR_RATCHET@{new_sl:.4f}")

                    if hasattr(st, "key_levels") and st.key_levels:
                        resistance_levels = sorted(
                            [kl["price"] for kl in st.key_levels if kl.get("price", 0) > c_price]
                        )
                        if resistance_levels:
                            key_sl = round(resistance_levels[0] + (atr * SR_ATR_BUFFER), digits)
                            if (new_sl == 0 or key_sl < new_sl) and key_sl > c_price:
                                key_sl = key_sl
                                actions.append(f"KEY_LEVEL@{new_sl:.4f}")

            # ── 3.5 Live MFE Scale-Out & Retracement Protection (E2) ───────────
            if pos.type == "BUY":
                peak_mfe = self._peak_favorable_price[pos.ticket] - pos.open_price
                if peak_mfe >= (atr * 1.5):
                    current_gain = c_price - pos.open_price
                    giveback_pct = (peak_mfe - current_gain) / (peak_mfe + 1e-9)
                    if giveback_pct >= 0.40:
                        mfe_locked_sl = round(pos.open_price + (peak_mfe * 0.50), digits)
                        if mfe_locked_sl > new_sl and mfe_locked_sl < c_price:
                            new_sl = mfe_locked_sl
                            actions.append(f"MFE_RETRACE_50%_LOCK@{new_sl:.4f}")
            elif pos.type == "SELL":
                peak_mfe = pos.open_price - self._peak_favorable_price[pos.ticket]
                if peak_mfe >= (atr * 1.5):
                    current_gain = pos.open_price - c_price
                    giveback_pct = (peak_mfe - current_gain) / (peak_mfe + 1e-9)
                    if giveback_pct >= 0.40:
                        mfe_locked_sl = round(pos.open_price - (peak_mfe * 0.50), digits)
                        if (new_sl == 0 or mfe_locked_sl < new_sl) and mfe_locked_sl > c_price:
                            new_sl = mfe_locked_sl
                            actions.append(f"MFE_RETRACE_50%_LOCK@{new_sl:.4f}")

            # ── 4. Regime invalidation exit ────────────────────────────────
            new_sl, act = self._check_regime_invalidation(pos, ctx, regime, c_price, atr, new_sl)
            if act:
                actions.append(act)

            # ── 5. VWAP cross awareness ────────────────────────────────────
            new_sl, act = self._check_vwap_cross(pos, ctx, c_price, atr, new_sl)
            if act:
                actions.append(act)

            # ── 6. Momentum exhaustion exit ───────────────────────────────
            new_sl, act = self._check_momentum_exhaustion(pos, ctx, c_price, atr, new_sl)
            if act:
                actions.append(act)

            # ── 7. Horizon-Adaptive Stagnation & Time-Decay Auto-Exit ────────
            open_dur_sec = self._get_position_duration_sec(pos)
            if open_dur_sec > 0:
                current_r = ((c_price - pos.open_price) if pos.type == "BUY" else (pos.open_price - c_price)) / max(risk_dist, 1e-6)

                # Scalp: 45 min max hold without progress (R < 0.50R) -> Close position
                if style == "SCALP" and open_dur_sec >= 2700.0 and current_r < 0.50:
                    logger.info(
                        f"⏳ SCALP STAGNATION EXIT: Closing position #{pos.ticket} ({symbol}) after "
                        f"{open_dur_sec/60:.1f}m hold without progress (R={current_r:.2f} < 0.50R, PnL: ${pos.profit:.2f})."
                    )
                    self.mt5_client.close_position(pos.ticket)
                    return

                # Day: 6 hours max hold without progress (R < 0.75R) -> Close position
                elif style in ("DAY_TRADING", "DAY", "INTRADAY") and open_dur_sec >= 21600.0 and current_r < 0.75:
                    logger.info(
                        f"⏳ DAY TRADING STAGNATION EXIT: Closing position #{pos.ticket} ({symbol}) after "
                        f"{open_dur_sec/3600:.1f}h hold without progress (R={current_r:.2f} < 0.75R, PnL: ${pos.profit:.2f})."
                    )
                    self.mt5_client.close_position(pos.ticket)
                    return

                # Swing: 36 hours max hold in compression -> Close position
                elif style == "SWING" and open_dur_sec >= 129600.0:
                    is_comp = (
                        getattr(ctx.volatility, "state", "").upper() == "COMPRESSION"
                        or (regime and hasattr(regime, "primary_regime") and regime.primary_regime in (
                            MarketRegime.COMPRESSION, MarketRegime.CONSOLIDATION, MarketRegime.LOW_VOLATILITY, MarketRegime.RANGE
                        ))
                        or getattr(ctx.momentum, "adx", 0.0) < 18.0
                    )
                    if is_comp:
                        logger.info(
                            f"⏳ SWING COMPRESSION STAGNATION EXIT: Closing position #{pos.ticket} ({symbol}) after "
                            f"{open_dur_sec/3600:.1f}h hold in compression (PnL: ${pos.profit:.2f})."
                        )
                        self.mt5_client.close_position(pos.ticket)
                        return

                # Fallback Regime-Adaptive Time-Decay Stale Trade Exit
                try:
                    regime_str = getattr(regime, "primary_regime", None)
                    r_name = getattr(regime_str, "value", str(regime_str or "DEFAULT")).upper()
                    if "TREND" in r_name:
                        max_stall_sec = 43200.0
                    elif "RANGE" in r_name or "LOW_VOLATILITY" in r_name:
                        max_stall_sec = 28800.0
                    elif "BREAKOUT" in r_name:
                        max_stall_sec = 21600.0
                    else:
                        max_stall_sec = 86400.0

                    if open_dur_sec >= max_stall_sec:
                        trend_score = getattr(ctx.momentum, "trend_score", 0.0)
                        profit_ratio = abs(pos.profit / (balance + 1e-9))
                        if profit_ratio < 0.005 and abs(trend_score) < 20.0:
                            logger.info(
                                f"⏳ REGIME TIME-DECAY EXIT: Closing position #{pos.ticket} ({symbol}) after "
                                f"{open_dur_sec/3600:.1f}h stall in {r_name} regime (PnL: ${pos.profit:.2f})."
                            )
                            self.mt5_client.close_position(pos.ticket)
                            return
                        elif profit_ratio >= 0.005:
                            be_cand = round((pos.open_price + (atr * STAGE1_BE_BUFFER)), digits) if pos.type == "BUY" else round((pos.open_price - (atr * STAGE1_BE_BUFFER)), digits)
                            if pos.type == "BUY" and be_cand > new_sl and be_cand < c_price:
                                new_sl = be_cand
                                actions.append(f"TIME_DECAY_BE@{new_sl:.4f}")
                            elif pos.type == "SELL" and (new_sl == 0 or be_cand < new_sl) and be_cand > c_price:
                                new_sl = be_cand
                                actions.append(f"TIME_DECAY_BE@{new_sl:.4f}")
                except Exception:
                    pass

        # Monotonic ratchet enforcement (SL only moves closer to price, never backward)
        if pos.type == "BUY":
            if pos.sl > 0 and new_sl < pos.sl:
                new_sl = pos.sl
        elif pos.type == "SELL":
            if pos.sl > 0 and new_sl > pos.sl:
                new_sl = pos.sl

        # ── Apply modifications if SL changes by > 1.0 pip or TP changes ─────────────────────────
        sl_pip_diff = abs(new_sl - pos.sl) / (pip_size if pip_size > 0 else 1.0)
        sl_changed = (sl_pip_diff >= 1.0) or (pos.sl == 0 and new_sl > 0)
        tp_changed = abs(new_tp - pos.tp) > 0.0001

        if sl_changed or tp_changed:
            new_sl = round(new_sl, digits)
            new_tp = round(new_tp, digits)
            action_key = f"{new_sl:.{digits}f}"
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

        # Determine conviction-aware breathing factor (§B-4)
        is_high_conviction = (
            getattr(ctx.momentum, "adx", 0.0) > 25.0
            and getattr(ctx.momentum, "trend_score", 0.0) != 0.0
            and (
                (pos.type == "BUY" and getattr(ctx.momentum, "trend_score", 0.0) > 20)
                or (pos.type == "SELL" and getattr(ctx.momentum, "trend_score", 0.0) < -20)
            )
        )
        conviction_mult = 1.25 if is_high_conviction else 1.0

        stage1_trigger = STAGE1_ATR_TRIGGER * conviction_mult
        std_trigger = STD_ATR_TRIGGER * conviction_mult
        chandelier_trigger = 0.75 * conviction_mult

        if pos.type == "BUY":
            profit_pips = c_price - pos.open_price

            # ── 1. Breakeven & Profit Lock Stages ──────────────────────────────
            if is_micro:
                # Stage 3 — 60% profit lock
                if profit_pips >= (atr * STAGE3_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price + (profit_pips * STAGE3_PROFIT_LOCK_PCT)
                    if candidate > new_sl and candidate < c_price:
                        new_sl = candidate
                        actions.append(f"STAGE3_60%@{new_sl:.4f}")

                # Stage 2 — profit lock 0.75R
                elif profit_pips >= (atr * STAGE2_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price + (atr * STAGE2_PROFIT_LOCK)
                    if candidate > new_sl and candidate < c_price:
                        new_sl = candidate
                        actions.append(f"STAGE2_BE+@{new_sl:.4f}")

                # Stage 1 — breakeven (+ small buffer)
                elif profit_pips >= (atr * stage1_trigger * atr_mult) and new_sl < pos.open_price:
                    candidate = pos.open_price + (atr * STAGE1_BE_BUFFER)
                    if candidate > new_sl and candidate < c_price:
                        new_sl = candidate
                        actions.append(f"STAGE1_BE@{new_sl:.4f}")

            else:
                # Standard: move to breakeven at STD_ATR_TRIGGER (or conviction adjusted)
                if profit_pips >= (atr * std_trigger * atr_mult) and new_sl < pos.open_price:
                    candidate = pos.open_price + (atr * STD_BE_BUFFER)
                    if candidate > new_sl and candidate < c_price:
                        new_sl = candidate
                        actions.append(f"STD_BE@{new_sl:.4f}")

            # ── 2. Dynamic ATR Chandelier Trailing Stop (Continuous Ratchet) ──
            if profit_pips >= (atr * chandelier_trigger * atr_mult):
                dynamic_trail = c_price - (atr * 0.85 * atr_mult)
                if dynamic_trail > pos.open_price and dynamic_trail > new_sl and dynamic_trail < c_price:
                    new_sl = dynamic_trail
                    actions.append(f"DYNAMIC_ATR_TRAIL@{new_sl:.4f}")

            # ── 3. Structural S/R ratchet — ratchet to higher-low support ──
            if st.higher_lows and st.demand_zone[0] > 0:
                struct_sl = st.demand_zone[0] - (atr * SR_ATR_BUFFER)
                if struct_sl > new_sl and struct_sl < c_price:
                    new_sl = struct_sl
                    actions.append(f"SR_RATCHET@{new_sl:.4f}")

            # ── 4. Key level ratchet (from Phase 3 S/R clustering) ──
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

            # ── 1. Breakeven & Profit Lock Stages ──────────────────────────────
            if is_micro:
                if profit_pips >= (atr * STAGE3_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price - (profit_pips * STAGE3_PROFIT_LOCK_PCT)
                    if (new_sl == 0 or candidate < new_sl) and candidate > c_price:
                        new_sl = candidate
                        actions.append(f"STAGE3_60%@{new_sl:.4f}")

                elif profit_pips >= (atr * STAGE2_ATR_TRIGGER * atr_mult):
                    candidate = pos.open_price - (atr * STAGE2_PROFIT_LOCK)
                    if (new_sl == 0 or candidate < new_sl) and candidate > c_price:
                        new_sl = candidate
                        actions.append(f"STAGE2_BE+@{new_sl:.4f}")

                elif profit_pips >= (atr * stage1_trigger * atr_mult) and (new_sl == 0 or new_sl > pos.open_price):
                    candidate = pos.open_price - (atr * STAGE1_BE_BUFFER)
                    if (new_sl == 0 or candidate < new_sl) and candidate > c_price:
                        new_sl = candidate
                        actions.append(f"STAGE1_BE@{new_sl:.4f}")

            else:
                if profit_pips >= (atr * std_trigger * atr_mult) and (new_sl == 0 or new_sl > pos.open_price):
                    candidate = pos.open_price - (atr * STD_BE_BUFFER)
                    if (new_sl == 0 or candidate < new_sl) and candidate > c_price:
                        new_sl = candidate
                        actions.append(f"STD_BE@{new_sl:.4f}")

            # ── 2. Dynamic ATR Chandelier Trailing Stop (Continuous Ratchet) ──
            if profit_pips >= (atr * chandelier_trigger * atr_mult):
                dynamic_trail = c_price + (atr * 0.85 * atr_mult)
                if dynamic_trail < pos.open_price and (new_sl == 0 or dynamic_trail < new_sl) and dynamic_trail > c_price:
                    new_sl = dynamic_trail
                    actions.append(f"DYNAMIC_ATR_TRAIL@{new_sl:.4f}")

            # ── 3. Structural S/R ratchet — ratchet to lower-high resistance ──
            if st.lower_highs and st.supply_zone[1] > 0:
                struct_sl = st.supply_zone[1] + (atr * SR_ATR_BUFFER)
                if (new_sl == 0 or struct_sl < new_sl) and struct_sl > c_price:
                    new_sl = struct_sl
                    actions.append(f"SR_RATCHET@{new_sl:.4f}")

            # ── 4. Key level ratchet ──
            if hasattr(st, "key_levels") and st.key_levels:
                resistance_levels = sorted(
                    [kl["price"] for kl in st.key_levels if kl.get("price", 0) > c_price]
                )
                if resistance_levels:
                    key_sl = resistance_levels[0] + (atr * SR_ATR_BUFFER)
                    if (new_sl == 0 or key_sl < new_sl) and key_sl > c_price:
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
            tag in (pos.comment or "").upper()
            for tag in ("MANUAL", "DESK")
        )
        return is_wrong_magic or (pos.magic == 0) or has_manual_comment

    def _determine_position_style(self, pos: PositionSnapshot, ctx: Optional[MarketContext] = None) -> str:
        """
        Determine position style (SCALP, DAY_TRADING, SWING) from comment, tag, or duration.
        """
        comment = (pos.comment or "").upper()
        tag = str(getattr(pos, "tag", "") or "").upper()
        trade_style = str(getattr(pos, "trade_style", "") or "").upper()

        for text in (comment, tag, trade_style):
            if "SCALP" in text:
                return "SCALP"
            if "SWING" in text:
                return "SWING"
            if "DAY" in text or "INTRADAY" in text:
                return "DAY_TRADING"

        # Check duration
        dur_sec = self._get_position_duration_sec(pos)
        if dur_sec > 24.0 * 3600:
            return "SWING"
        elif dur_sec > 2.0 * 3600:
            return "DAY_TRADING"

        return "LEGACY"

    def _get_position_duration_sec(self, pos: PositionSnapshot) -> float:
        """Returns elapsed open duration of a position in seconds."""
        if not hasattr(pos, "open_time") or not pos.open_time:
            return 0.0
        try:
            if isinstance(pos.open_time, str):
                if "T" in pos.open_time:
                    open_dt = datetime.fromisoformat(pos.open_time.replace("Z", "+00:00"))
                else:
                    open_dt = datetime.strptime(pos.open_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            elif isinstance(pos.open_time, datetime):
                open_dt = pos.open_time if pos.open_time.tzinfo else pos.open_time.replace(tzinfo=timezone.utc)
            else:
                return 0.0
            now = datetime.now(timezone.utc)
            if open_dt.tzinfo is None:
                open_dt = open_dt.replace(tzinfo=timezone.utc)
            return max(0.0, (now - open_dt).total_seconds())
        except Exception:
            return 0.0

    def _check_adversarial_order_flow_shield(
        self,
        pos: PositionSnapshot,
        ctx: MarketContext,
        c_price: float,
        atr: float,
        digits: int
    ) -> Tuple[bool, Optional[Any]]:
        """
        Adversarial Order Flow Shield:
        If counter volume delta > 35% or absorption trap detected while holding open trade:
          - If in profit: Immediately ratchet SL to Bid/Ask +/- 0.15x ATR.
          - If underwater / flat: Close position to prevent full stop-out.
        """
        of_data = getattr(ctx, "order_flow", {})
        if not of_data or not isinstance(of_data, dict):
            return False, None

        delta_score = float(of_data.get("delta_score", 0.0))
        delta_ratio = float(of_data.get("delta_ratio", 0.0))
        absorption_trap = of_data.get("absorption_trap")

        is_adversarial = False
        if pos.type == "BUY":
            counter_delta = (delta_score < -35.0) or (delta_ratio < -0.35)
            counter_trap = absorption_trap in ("SELLER_ABSORPTION_TRAP", "ABSORPTION_TRAP", "BEARISH_ABSORPTION_TRAP")
            if counter_delta or counter_trap:
                is_adversarial = True
        elif pos.type == "SELL":
            counter_delta = (delta_score > 35.0) or (delta_ratio > 0.35)
            counter_trap = absorption_trap in ("BUYER_ABSORPTION_TRAP", "ABSORPTION_TRAP", "BULLISH_ABSORPTION_TRAP")
            if counter_delta or counter_trap:
                is_adversarial = True

        if not is_adversarial:
            return False, None

        is_in_profit = (pos.profit > 0.0) or ((c_price > pos.open_price) if pos.type == "BUY" else (c_price < pos.open_price))

        if is_in_profit:
            # In profit -> ratchet SL to Bid/Ask +/- 0.15x ATR
            if pos.type == "BUY":
                bid_price = getattr(ctx, "bid", c_price)
                cand_sl = round(bid_price - (0.15 * atr), digits)
                return True, cand_sl
            else:
                ask_price = getattr(ctx, "ask", c_price)
                cand_sl = round(ask_price + (0.15 * atr), digits)
                return True, cand_sl
        else:
            # Underwater or flat -> close position
            return True, "CLOSE"

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
