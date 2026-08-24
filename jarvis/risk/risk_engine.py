"""
JARVIS AI 4.0 — Master Adaptive Risk Management Engine.
Enforces multi-tier portfolio protection:
  - Base Soft Limit: 1 trade per symbol
  - AI-Adaptive Second Trade Gate: 15-condition validation for high-conviction pyramiding
  - Hard Ceiling: Max 2 trades per symbol, Max 3 total concurrent positions
  - Unified 0-100 Portfolio Heat scoring and atomic multi-threaded risk reservation.
"""
import time
import logging
import threading
from typing import Dict, List, Any, Optional
from jarvis.data.schemas import DecisionObject, AccountSnapshot, PositionSnapshot, MarketContext
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.risk.position_sizing import PositionSizer
from jarvis.risk.drawdown import DrawdownGuard
from jarvis.risk.exposure import ExposureManager, BASE_MAX_TRADES_PER_SYMBOL, HARD_MAX_TRADES_PER_SYMBOL, MAX_PORTFOLIO_RISK_PCT
from jarvis.risk.circuit_breaker import CircuitBreaker
from jarvis.risk.trade_guard import TradeGuard
from jarvis.risk.portfolio_heat import PortfolioHeatEngine, PortfolioHeatResult
from jarvis.market.correlations import DynamicCorrelationEngine

logger = logging.getLogger("JARVIS_RiskEngine")

class RiskEngine:
    def __init__(
        self,
        max_daily_loss_pct: float = 4.0,
        max_drawdown_pct: float = 10.0,
        max_open_positions: int = 3,
        max_symbol_positions: int = 2,
        max_risk_per_trade_pct: float = 0.5,
        max_portfolio_risk_pct: float = 2.5,
        is_backtest: bool = False
    ):
        self._lock = threading.RLock()
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.drawdown_guard = DrawdownGuard(
            max_daily_loss_pct, max_drawdown_pct,
            db_path="" if is_backtest else "jarvis_drawdown_state.db"
        )
        self.exposure_manager = ExposureManager(
            max_open_positions=max_open_positions,
            max_symbol_positions=max_symbol_positions,
            max_portfolio_risk_pct=max_portfolio_risk_pct
        )
        self.portfolio_heat_engine = PortfolioHeatEngine(
            max_portfolio_risk_pct=max_portfolio_risk_pct,
            max_daily_loss_pct=max_daily_loss_pct,
            max_open_positions=max_open_positions
        )
        self.circuit_breaker = CircuitBreaker(
            db_path="" if is_backtest else "jarvis_circuit_state.db"
        )
        self.position_sizer = PositionSizer()
        self.trade_guard = TradeGuard()
        self.correlation_engine = DynamicCorrelationEngine()

        # Atomic Risk Reservation table: {symbol: (reserved_usd, expiry_time)}
        self._reserved_risk: Dict[str, tuple] = {}
        self._reserved_lock = threading.Lock()

    # ─── Atomic Risk Reservation (Thread-Safe Execution) ───────────────────────

    def reserve_risk(self, symbol: str, risk_usd: float, ttl_sec: float = 15.0) -> bool:
        """Atomically reserves monetary risk capacity before placing order to prevent race conditions."""
        canon = resolve_symbol(symbol).canonical
        with self._reserved_lock:
            now = time.time()
            self._prune_expired_reservations(now)
            self._reserved_risk[canon] = (risk_usd, now + ttl_sec)
            return True

    def release_risk(self, symbol: str):
        """Releases reserved risk if order execution fails or is cancelled."""
        canon = resolve_symbol(symbol).canonical
        with self._reserved_lock:
            self._reserved_risk.pop(canon, None)

    def commit_risk(self, symbol: str):
        """Clears reservation upon successful broker execution (now tracked via open positions)."""
        self.release_risk(symbol)

    def get_total_reserved_risk_usd(self) -> float:
        """Returns total unexpired reserved monetary risk across pending orders."""
        with self._reserved_lock:
            now = time.time()
            self._prune_expired_reservations(now)
            return sum(r[0] for r in self._reserved_risk.values())

    def _prune_expired_reservations(self, now: float):
        expired = [k for k, v in self._reserved_risk.items() if now > v[1]]
        for k in expired:
            self._reserved_risk.pop(k, None)

    # ─── 15-Condition Adaptive Second-Trade Validation ─────────────────────────

    def _validate_adaptive_second_trade(
        self,
        decision: DecisionObject,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        context: Optional[MarketContext] = None,
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0,
        heat_res: Optional[PortfolioHeatResult] = None
    ) -> Dict[str, Any]:
        """
        Evaluates all 15 institutional conditions required to authorize a 2nd trade on the same symbol.
        """
        breaches = []
        symbol = decision.symbol
        canon = resolve_symbol(symbol).canonical
        existing_sym_positions = [p for p in positions if resolve_symbol(p.symbol).canonical == canon]

        # Condition 1: High Calibrated Win Probability (>= 60.0%)
        min_adaptive_prob = 0.60
        if decision.model_confidence < min_adaptive_prob:
            breaches.append(f"ADAPTIVE_GATE_1: Calibrated win probability ({decision.model_confidence*100:.1f}%) below adaptive threshold ({min_adaptive_prob*100:.1f}%).")

        # Condition 2: Positive Expected Value
        if decision.expected_value <= 0.0:
            breaches.append(f"ADAPTIVE_GATE_2: Expected Value (${decision.expected_value:.2f}) must be strictly positive.")

        # Condition 3: Risk / Reward Ratio >= 1.50
        if decision.risk_reward_ratio < 1.50:
            breaches.append(f"ADAPTIVE_GATE_3: Risk/Reward ratio (1:{decision.risk_reward_ratio:.2f}) below 1:1.50 minimum.")

        # Condition 4: Market Regime Supports Setup
        regime = decision.regime
        if regime and hasattr(regime, "primary_regime"):
            r_val = getattr(regime.primary_regime, "value", str(regime.primary_regime)).upper()
            if "VOLATILITY" in r_val or "EVENT_RISK" in r_val:
                breaches.append(f"ADAPTIVE_GATE_4: Market regime '{r_val}' is too volatile for same-symbol scaling.")
            if getattr(regime, "confidence", 1.0) < 0.60:
                breaches.append(f"ADAPTIVE_GATE_4: Regime classification confidence ({regime.confidence*100:.1f}%) is below 60%.")

        # Condition 5: Multi-Timeframe Structure Confirms Direction
        if context and hasattr(context, "structure") and context.structure.bias != "NEUTRAL":
            expected_struct_bias = "BULLISH" if decision.bias == "BUY" else "BEARISH"
            if context.structure.bias != expected_struct_bias:
                breaches.append(f"ADAPTIVE_GATE_5: Higher timeframe structure ({context.structure.bias}) conflicts with trade bias ({decision.bias}).")

        # Condition 6: Momentum & Trend Score Alignment
        if context and hasattr(context, "momentum"):
            trend_score = getattr(context.momentum, "trend_score", 0.0)
            if decision.bias == "BUY" and trend_score < 0:
                breaches.append(f"ADAPTIVE_GATE_6: Momentum trend score ({trend_score:.1f}) is negative for BUY setup.")
            elif decision.bias == "SELL" and trend_score > 0:
                breaches.append(f"ADAPTIVE_GATE_6: Momentum trend score ({trend_score:.1f}) is positive for SELL setup.")

        # Condition 7: Anti-Averaging Down Guard (Pyramiding vs Averaging Down)
        # MUST REJECT if existing trade in the same direction is currently losing
        for p in existing_sym_positions:
            p_side = getattr(p, "side", getattr(p, "type", "BUY")).upper()
            if (p_side == "BUY" and decision.bias == "BUY") or (p_side == "SELL" and decision.bias == "SELL"):
                if p.profit < -0.01:
                    breaches.append(
                        f"ADAPTIVE_GATE_7_ANTI_AVERAGING_DOWN: Existing #{p.ticket} {p.symbol} position is currently in drawdown (${p.profit:.2f}). "
                        f"Adding to losing position is strictly prohibited."
                    )

        # Condition 8: Portfolio Risk Budget Capacity
        spec = resolve_symbol(symbol)
        contract_size = spec.contract_size or 100000.0
        risk_dist = abs(decision.entry_price - decision.stop_loss)
        est_new_risk_usd = 0.01 * contract_size * risk_dist
        open_risk_usd = self.exposure_manager.calculate_portfolio_monetary_risk(positions, account)
        total_projected_risk_usd = open_risk_usd + self.get_total_reserved_risk_usd() + est_new_risk_usd
        if account.equity > 0:
            proj_risk_pct = (total_projected_risk_usd / account.equity) * 100.0
            if proj_risk_pct > self.max_portfolio_risk_pct:
                breaches.append(f"ADAPTIVE_GATE_8: Projected portfolio risk ({proj_risk_pct:.2f}%) exceeds budget ({self.max_portfolio_risk_pct}%).")

        # Condition 9: Margin Utilization Safe
        if account.equity > 0:
            margin_pct = (account.margin / account.equity) * 100.0
            if margin_pct >= 40.0:
                breaches.append(f"ADAPTIVE_GATE_9: Margin utilization ({margin_pct:.1f}%) is at or above 40% threshold.")

        # Condition 10: Daily Drawdown Safe
        dd_check = self.drawdown_guard.check_limits(account.equity, account.balance)
        if not dd_check.get("passed"):
            breaches.append(f"ADAPTIVE_GATE_10: Daily drawdown guard breached: {dd_check.get('breaches')}")

        # Condition 11: Portfolio Heat Safe (< 70.0 for normal additions, < 85.0 for ultra-conviction)
        if heat_res:
            if heat_res.score >= 85.0:
                breaches.append(f"ADAPTIVE_GATE_11: Extreme portfolio heat ({heat_res.score:.1f}/100). Same-symbol scaling blocked.")
            elif heat_res.score >= 70.0 and decision.model_confidence < 0.75:
                breaches.append(f"ADAPTIVE_GATE_11: High portfolio heat ({heat_res.score:.1f}/100) requires >=75% win probability (got {decision.model_confidence*100:.1f}%).")

        # Condition 12: Currency & Asset Concentration Safe
        curr_check = self.exposure_manager.check_currency_directional_exposure(symbol, decision.bias, positions)
        if not curr_check.get("passed"):
            breaches.extend([f"ADAPTIVE_GATE_12: {b}" for b in curr_check.get("breaches", [])])

        # Condition 13: Volatility & Spread Acceptable
        if current_spread_pips > max_allowed_spread_pips:
            breaches.append(f"ADAPTIVE_GATE_13: Current spread ({current_spread_pips} pips) exceeds allowed ({max_allowed_spread_pips} pips).")

        # Condition 14: Liquidity & Session Active
        if context and hasattr(context, "session"):
            if not getattr(context.session, "is_prime_session", True) and decision.adversarial_penalty > 15.0:
                breaches.append(f"ADAPTIVE_GATE_14: Off-hours session with elevated adversarial penalty (-{decision.adversarial_penalty:.1f} pts).")

        # Condition 15: Valid Independent Entry Geometry
        for p in existing_sym_positions:
            price_diff = abs(decision.entry_price - p.open_price)
            if price_diff < (risk_dist * 0.25):
                breaches.append(f"ADAPTIVE_GATE_15: New entry price ({decision.entry_price}) is too close to existing entry #{p.ticket} ({p.open_price}). Requires independent structural level.")

        return {
            "passed": len(breaches) == 0,
            "breaches": breaches
        }

    # ─── Master Authorization Pipeline ─────────────────────────────────────────

    def authorize_execution(
        self,
        decision: DecisionObject,
        account: AccountSnapshot,
        positions: List[PositionSnapshot],
        symbol_info: Dict[str, Any],
        current_spread_pips: float = 2.0,
        max_allowed_spread_pips: float = 35.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Master Authorization Pipeline.
        Evaluates Circuit Breaker, Drawdown, Exposure, Quality Guard, Heat, and Adaptive 2nd Trade conditions.
        """
        if "spread_pips" in kwargs:
            current_spread_pips = float(kwargs["spread_pips"])
        context: Optional[MarketContext] = kwargs.get("context")

        with self._lock:
            rejection_reasons = []
            symbol = decision.symbol
            canon = resolve_symbol(symbol).canonical

            # Count active positions on this symbol (including canonical aliases)
            existing_sym_positions = [
                p for p in positions if resolve_symbol(p.symbol).canonical == canon
            ]
            symbol_count = len(existing_sym_positions)
            is_second_trade = symbol_count == 1
            is_over_hard_limit = symbol_count >= HARD_MAX_TRADES_PER_SYMBOL

            # 1. Circuit Breaker status (Global + Per-Symbol / Per-Regime)
            cb = self.circuit_breaker.check_status()
            if cb.get("active"):
                rejection_reasons.append(f"Circuit Breaker active: {cb.get('reason')} (Cooldown: {cb.get('remaining_cooldown_sec', 0)}s)")
            if self.circuit_breaker.is_symbol_paused(symbol):
                rejection_reasons.append(f"Symbol {symbol} is temporarily paused due to recent consecutive losses.")
            if decision.regime and hasattr(decision.regime, "primary_regime") and self.circuit_breaker.is_regime_paused(decision.regime.primary_regime.value):
                rejection_reasons.append(f"Regime {decision.regime.primary_regime.value} is temporarily paused due to consecutive losses.")

            # 2. Drawdown & Daily Loss limits
            dd = self.drawdown_guard.check_limits(account.equity, account.balance)
            if not dd.get("passed"):
                rejection_reasons.extend(dd.get("breaches", []))

            # 3. Portfolio Heat Evaluation
            open_monetary_risk = self.exposure_manager.calculate_portfolio_monetary_risk(positions, account) + self.get_total_reserved_risk_usd()
            heat_res = self.portfolio_heat_engine.calculate_heat(
                account=account,
                positions=positions,
                open_monetary_risk_usd=open_monetary_risk
            )
            if not heat_res.allow_new_risk:
                rejection_reasons.append(f"PORTFOLIO_HEAT_BLOCK: Portfolio Heat is {heat_res.score:.1f}/100 (EXTREME). All new risk blocked.")

            # 4. Hard Same-Symbol & Portfolio Position Limits
            if is_over_hard_limit:
                rejection_reasons.append(f"HARD_SYMBOL_LIMIT: Symbol {symbol} already has {symbol_count} open positions (Max {HARD_MAX_TRADES_PER_SYMBOL}).")

            # 5. Adaptive Second-Trade 15-Point Validation
            is_second_trade_approved = False
            if is_second_trade and not is_over_hard_limit:
                adaptive_check = self._validate_adaptive_second_trade(
                    decision=decision,
                    account=account,
                    positions=positions,
                    context=context,
                    current_spread_pips=current_spread_pips,
                    max_allowed_spread_pips=max_allowed_spread_pips,
                    heat_res=heat_res
                )
                if not adaptive_check.get("passed"):
                    rejection_reasons.extend(adaptive_check.get("breaches", []))
                else:
                    is_second_trade_approved = True
                    logger.info(f"✨ ADAPTIVE 2ND TRADE APPROVED for {symbol}: All 15 quality/risk conditions passed.")

            # 6. Portfolio Exposure & Margin limits
            exp = self.exposure_manager.check_exposure(
                symbol=symbol,
                positions=positions,
                account=account,
                is_second_trade_approved=is_second_trade_approved
            )
            if not exp.get("passed"):
                rejection_reasons.extend(exp.get("breaches", []))

            # 7. Pre-Execution Geometry & Gate validation
            guard = self.trade_guard.validate_pre_execution(
                decision, account, positions, max_allowed_spread_pips, current_spread_pips
            )
            if not guard.get("passed"):
                rejection_reasons.extend(guard.get("reasons", []))

            # 8. Cross-Asset Correlation check
            for pos in positions:
                if resolve_symbol(pos.symbol).canonical == canon:
                    continue  # Same-symbol is governed by adaptive same-symbol validator
                corr = self.correlation_engine.get_correlation(symbol, pos.symbol)
                if corr > 0.70:
                    rejection_reasons.append(f"Correlation too high ({corr:.2f}) with existing position {pos.symbol}.")

            if rejection_reasons:
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": rejection_reasons,
                    "heat_score": heat_res.score,
                    "heat_zone": heat_res.zone
                }

            # 9. Dynamic Position Sizing with Heat & 2nd Position Scaling
            sample_size = getattr(decision, "pattern_sample_size", 0)
            lots = self.position_sizer.calculate_lot_size(
                account_balance=account.equity,
                entry_price=decision.entry_price,
                sl_price=decision.stop_loss,
                risk_pct=self.max_risk_per_trade_pct,
                symbol_info=symbol_info,
                invalidation_risk_coefficient=1.0 - (decision.adversarial_penalty / 60.0),
                model_confidence=decision.model_confidence,
                pattern_sample_size=sample_size,
                portfolio_heat_multiplier=heat_res.risk_multiplier,
                is_second_trade=is_second_trade
            )

            # Final backstop checks
            cb_final = self.circuit_breaker.check_status()
            if cb_final.get("active"):
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": [f"Circuit Breaker tripped during authorization: {cb_final.get('reason')}"]
                }
                
            dd_final = self.drawdown_guard.check_limits(account.equity, account.balance)
            if not dd_final.get("passed"):
                return {
                    "authorized": False,
                    "lots": 0.0,
                    "reasons": dd_final.get("breaches", [])
                }

            return {
                "authorized": True,
                "lots": lots,
                "reasons": [],
                "is_second_trade": is_second_trade,
                "heat_score": heat_res.score,
                "heat_zone": heat_res.zone
            }

