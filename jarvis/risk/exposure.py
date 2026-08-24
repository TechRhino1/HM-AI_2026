"""
JARVIS AI 4.0 — Adaptive Portfolio Exposure & Margin Management Engine.
Enforces soft/hard same-symbol position limits, currency directional concentration,
and total portfolio monetary risk budget.
"""
from typing import List, Dict, Any, Optional
from jarvis.data.schemas import PositionSnapshot, AccountSnapshot
from jarvis.data.symbol_registry import resolve as resolve_symbol

BASE_MAX_TRADES_PER_SYMBOL = 1        # Soft limit: Standard baseline
AI_ADAPTIVE_MAX_TRADES_PER_SYMBOL = 2 # Adaptive limit: Allowed if all 15 conditions pass
HARD_MAX_TRADES_PER_SYMBOL = 2        # Hard ceiling: Never exceeded under any circumstances
MAX_PORTFOLIO_RISK_PCT = 2.5          # Hard ceiling for total combined open monetary risk

class ExposureManager:
    def __init__(
        self,
        max_open_positions: int = 3,
        max_symbol_positions: int = 2,
        max_margin_utilization_pct: float = 40.0,
        max_notional_exposure_pct: float = 200.0,
        max_portfolio_risk_pct: float = 2.5
    ):
        self.max_open_positions = max_open_positions
        self.base_max_symbol_positions = BASE_MAX_TRADES_PER_SYMBOL
        self.hard_max_symbol_positions = HARD_MAX_TRADES_PER_SYMBOL
        self.max_symbol_positions = max_symbol_positions
        self.max_margin_utilization_pct = max_margin_utilization_pct
        self.max_notional_exposure_pct = max_notional_exposure_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct

    def calculate_portfolio_monetary_risk(
        self,
        positions: List[PositionSnapshot],
        account: AccountSnapshot
    ) -> float:
        """
        Calculates total monetary stop-loss risk ($) across all active positions.
        """
        total_risk_usd = 0.0
        for pos in positions:
            spec = resolve_symbol(pos.symbol)
            contract_size = getattr(pos, 'contract_size', spec.contract_size)
            if contract_size <= 0:
                contract_size = spec.contract_size or 100000.0

            open_price = float(pos.open_price or 1.0)
            sl_price = float(pos.sl or 0.0)

            if sl_price > 0:
                risk_dist = abs(open_price - sl_price)
            else:
                # Conservative fallback: 1.5% of open price if SL not set
                risk_dist = open_price * 0.015

            pos_risk_usd = float(pos.volume) * contract_size * risk_dist
            total_risk_usd += pos_risk_usd

        return round(total_risk_usd, 2)

    def check_currency_directional_exposure(
        self,
        target_symbol: str,
        target_bias: str,
        positions: List[PositionSnapshot],
        max_same_currency_direction: int = 3
    ) -> Dict[str, Any]:
        """
        Calculates net directional currency exposure (e.g. USD Short across EURUSD, GBPUSD, AUDUSD).
        """
        # Map common symbols to currency exposures (Base, Quote)
        currency_map = {
            "EURUSD": ("EUR", "USD"),
            "GBPUSD": ("GBP", "USD"),
            "AUDUSD": ("AUD", "USD"),
            "NZDUSD": ("NZD", "USD"),
            "USDJPY": ("USD", "JPY"),
            "USDCHF": ("USD", "CHF"),
            "USDCAD": ("USD", "CAD"),
            "XAUUSD": ("XAU", "USD"),
            "BTCUSD": ("BTC", "USD"),
        }

        # Net directional tallies: currency -> count (positive = Long, negative = Short)
        net_dir: Dict[str, int] = {}

        def _add_exposure(sym: str, bias: str):
            canon = resolve_symbol(sym).canonical
            if canon in currency_map:
                base, quote = currency_map[canon]
                if bias.upper() in ("BUY", "LONG", "0"):
                    net_dir[base] = net_dir.get(base, 0) + 1
                    net_dir[quote] = net_dir.get(quote, 0) - 1
                else:
                    net_dir[base] = net_dir.get(base, 0) - 1
                    net_dir[quote] = net_dir.get(quote, 0) + 1

        for p in positions:
            p_bias = getattr(p, "side", getattr(p, "type", "BUY"))
            _add_exposure(p.symbol, p_bias)

        # Hypothetically add target
        _add_exposure(target_symbol, target_bias)

        breaches = []
        for curr, count in net_dir.items():
            if abs(count) > max_same_currency_direction:
                dir_label = "LONG" if count > 0 else "SHORT"
                breaches.append(f"Excessive currency concentration: {abs(count)} concurrent {dir_label} {curr} positions (max {max_same_currency_direction}).")

        return {
            "passed": len(breaches) == 0,
            "net_exposures": net_dir,
            "breaches": breaches
        }

    def check_exposure(
        self,
        symbol: str,
        positions: List[PositionSnapshot],
        account: AccountSnapshot,
        is_second_trade_approved: bool = False,
        incoming_risk_usd: float = 0.0
    ) -> Dict[str, Any]:
        breaches = []
        target_canon = resolve_symbol(symbol).canonical

        # 1. Total Concurrent Positions Limit
        if len(positions) >= self.max_open_positions:
            breaches.append(f"Max Concurrent Positions reached ({len(positions)} >= {self.max_open_positions}).")

        # 2. Per-Symbol Exposure (Soft Limit = 1, Hard Limit = 2)
        symbol_count = sum(1 for p in positions if resolve_symbol(p.symbol).canonical == target_canon)
        if symbol_count >= self.hard_max_symbol_positions:
            breaches.append(f"Hard Max Exposure for symbol {symbol} reached ({symbol_count} >= {self.hard_max_symbol_positions}).")
        elif symbol_count >= self.base_max_symbol_positions and not is_second_trade_approved:
            breaches.append(f"Base Exposure limit for symbol {symbol} reached ({symbol_count} >= {self.base_max_symbol_positions}). Requires Adaptive Second-Trade Approval.")

        # 3. Portfolio Monetary Risk Budget
        open_risk_usd = self.calculate_portfolio_monetary_risk(positions, account)
        total_risk_usd = open_risk_usd + incoming_risk_usd
        if account and account.equity > 0:
            total_risk_pct = (total_risk_usd / account.equity) * 100.0
            if total_risk_pct > self.max_portfolio_risk_pct:
                breaches.append(f"Portfolio Risk Budget exceeded ({total_risk_pct:.2f}% > {self.max_portfolio_risk_pct}% max portfolio risk).")

        # 4. Margin Utilization & Notional Exposure
        exposure_pct = 0.0
        if account and account.equity > 0:
            margin_pct = (account.margin / account.equity) * 100.0
            if margin_pct >= self.max_margin_utilization_pct:
                breaches.append(f"High Margin Utilization ({margin_pct:.1f}% >= {self.max_margin_utilization_pct:.1f}%).")

            # Notional exposure calculation
            long_notional = 0.0
            short_notional = 0.0
            
            for pos in positions:
                spec = resolve_symbol(pos.symbol)
                contract_size = getattr(pos, 'contract_size', spec.contract_size) or 100000.0
                current_price = getattr(pos, 'current_price', getattr(pos, 'entry_price', 1.0))
                
                pos_notional = pos.volume * contract_size * current_price
                if getattr(pos, 'side', getattr(pos, 'type', '')).upper() in ('BUY', 'LONG', '0'):
                    long_notional += pos_notional
                else:
                    short_notional += pos_notional

            notional = long_notional + short_notional
            exposure_pct = (notional / account.equity) * 100.0
            
            if exposure_pct >= self.max_notional_exposure_pct:
                breaches.append(f"Max Notional Exposure reached ({exposure_pct:.1f}% >= {self.max_notional_exposure_pct:.1f}%).")

        return {
            "passed": len(breaches) == 0,
            "open_positions": len(positions),
            "symbol_count": symbol_count,
            "open_risk_usd": open_risk_usd,
            "breaches": breaches,
            "exposure_pct": exposure_pct if account and account.equity > 0 else 0.0
        }
