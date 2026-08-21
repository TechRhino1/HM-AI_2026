from typing import Dict, Any, List

class RiskManagerEngine:
    def __init__(self, settings: Dict[str, Any], logger: Any = None):
        self.risk_cfg = settings.get("risk", {})
        self.logger = logger
        self.daily_starting_equity = 0.0

    def set_daily_starting_equity(self, equity: float):
        if self.daily_starting_equity <= 0.0 or equity > self.daily_starting_equity:
            self.daily_starting_equity = equity

    def calculate_position_size(
        self,
        account_info: Dict[str, Any],
        symbol_info: Dict[str, Any],
        sl_price: float,
        entry_price: float,
        trade_score: float = 75.0,
        win_probability: float = 0.65,
        regime: str = "NEUTRAL"
    ) -> float:
        """
        Dynamic Balance & AI Win Probability-Weighted Lot Sizing Engine.
        Dynamically scales risk percentage based on Account Equity and Trade Score / Probability.
        """
        equity = account_info.get("equity", 10000.0)
        base_risk_pct = self.risk_cfg.get("max_risk_per_trade_pct", 0.5) / 100.0

        # AI Probability & Score Multiplier + Strong Trend Boost (+35%)
        regime_boost = 1.35 if "STRONG_TREND" in str(regime) else 1.00

        if trade_score >= 88.0 or win_probability >= 0.80:
            prob_multiplier = 1.50 * regime_boost  # High Conviction + Strong Trend -> Up to 1.5x-2.0x
        elif trade_score >= 75.0 or win_probability >= 0.65:
            prob_multiplier = 1.00 * regime_boost  # Standard Setup -> 1.35x
        elif trade_score >= 65.0:
            prob_multiplier = 0.50 * regime_boost
        else:
            prob_multiplier = 0.25

        # Ultra-Micro & $100 Account Dynamic Sizing (Enforces 0.02 / 0.03 Lots on $100 Accounts)
        if equity <= 50.0:
            dynamic_risk_pct = 0.025 * regime_boost  # 2.5% max risk per trade
            risk_amount = min(0.65, equity * dynamic_risk_pct)
        elif equity <= 200.0:
            # User Directive: In $100 account use lot size 0.02 (Standard) or 0.03 (Strong Trend)
            risk_amount = 3.00 if "STRONG_TREND" in str(regime) else 2.00
        else:
            dynamic_risk_pct = base_risk_pct * prob_multiplier
            risk_amount = equity * dynamic_risk_pct

        risk_dist = abs(entry_price - sl_price)
        if risk_dist <= 0:
            return 0.01

        contract_size = symbol_info.get("trade_contract_size", 100000)
        if contract_size <= 0:
            contract_size = 1.0

        raw_lots = risk_amount / (risk_dist * contract_size + 1e-9)

        min_lot = symbol_info.get("volume_min", 0.01)
        max_lot = symbol_info.get("volume_max", 100.0)
        step_lot = symbol_info.get("volume_step", 0.01)

        # Tiered Account-Balance Hard Lot Size Rules (Prevents over-leveraging on small/large accounts)
        symbol = str(symbol_info.get("name", "")).upper()
        is_high_vol = any(x in symbol for x in ["XAU", "GOLD", "BTC", "OIL", "US30", "NAS100"])

        if is_high_vol:
            raw_lots *= 0.80

        if equity <= 50.0:
            hard_max_lot = 0.01  # Hard cap 0.01 lots for ultra-micro $18 accounts
        elif equity <= 200.0:
            # User Directive: In $100 account use lot size 0.02 (Standard) or 0.03 (Strong Trend)
            hard_max_lot = 0.03 if "STRONG_TREND" in str(regime) else 0.02
            if is_high_vol:
                hard_max_lot = min(hard_max_lot, 0.02)
        elif equity <= 500.0:
            hard_max_lot = 0.03 if "STRONG_TREND" in str(regime) else 0.02
            if is_high_vol:
                hard_max_lot = min(hard_max_lot, 0.02)
        elif equity <= 1000.0:
            hard_max_lot = 0.04 if "STRONG_TREND" in str(regime) else 0.03
            if is_high_vol:
                hard_max_lot = min(hard_max_lot, 0.03)
        elif equity <= 5000.0:
            hard_max_lot = 0.06 if "STRONG_TREND" in str(regime) else 0.04
            if is_high_vol:
                hard_max_lot = min(hard_max_lot, 0.05)
        else:
            hard_max_lot = max_lot

        max_allowed_lot = min(max_lot, hard_max_lot)

        lots = round(raw_lots / step_lot) * step_lot
        lots = max(min_lot, min(max_allowed_lot, lots))
        lots = round(lots, 2)

        if self.logger:
            self.logger.info(f"Dynamic Position Sizing: Equity=${equity:,.2f} | Score={trade_score:.1f} | Dynamic Risk=${risk_amount:,.2f} -> Lots={lots:.2f}")

        return lots

    def validate_risk_limits(
        self,
        account_info: Dict[str, Any],
        open_positions: List[Dict[str, Any]],
        symbol: str,
        current_spread_pips: float,
        profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        reasons = []

        equity = account_info.get("equity", 10000.0)
        balance = account_info.get("balance", 10000.0)
        self.set_daily_starting_equity(balance)

        # 1. Daily Drawdown Guard (5.0% Max Daily Loss)
        max_daily_pct = self.risk_cfg.get("max_daily_loss_pct", 5.0)
        daily_loss_pct = ((self.daily_starting_equity - equity) / (self.daily_starting_equity + 1e-9)) * 100.0
        if daily_loss_pct >= max_daily_pct:
            reasons.append(f"Max Daily Loss limit breached ({daily_loss_pct:.2f}% >= {max_daily_pct:.2f}%). Trading halted for the day.")

        # 2. Max Open Positions Guard
        max_pos = self.risk_cfg.get("max_open_positions", 3)
        if len(open_positions) >= max_pos:
            reasons.append(f"Max Open Positions limit reached ({len(open_positions)} >= {max_pos}).")

        # 3. Max Symbol Exposure Guard
        symbol_pos_count = sum(1 for p in open_positions if p.get("symbol") == symbol)
        max_symbol_exp = self.risk_cfg.get("max_symbol_exposure_count", 1)
        if symbol_pos_count >= max_symbol_exp:
            reasons.append(f"Max Exposure limit for {symbol} reached ({symbol_pos_count} position already open).")

        # 4. Spread Limit Guard
        max_spread = profile.get("max_allowed_spread_pips", 35.0)
        if current_spread_pips > max_spread:
            reasons.append(f"Current spread ({current_spread_pips} pips) exceeds profile limit ({max_spread} pips).")

        is_passed = len(reasons) == 0

        if not is_passed and self.logger:
            self.logger.warning(f"RISK CHECK FAILED for {symbol}: {', '.join(reasons)}")

        return {
            "passed": is_passed,
            "reasons": reasons
        }
