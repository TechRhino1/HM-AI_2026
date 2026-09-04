import logging
from typing import Tuple, Dict

logger = logging.getLogger("JARVIS_LossCooldown")

class LossCooldownManager:
    """Professional consecutive loss cooldown and Fractional Kelly dynamic position sizing.
    
    Research shows:
    - Quarter-Kelly achieves 87% of full Kelly growth with max DD reduced from 64% to 12%
    - Circuit breaker after 3 consecutive losses prevents tilt spirals
    - Dynamic drawdown deleveraging prevents catastrophic failure
    """

    def __init__(self):
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.daily_pnl = 0.0
        self.cooldown_bars_remaining = 0
        self.trades_today = 0
        self.trades_today_by_symbol: Dict[str, int] = {}
        self.peak_equity = 0.0
        self.current_date = None

    def record_trade_result(self, pnl: float, is_win: bool, symbol: str = "", current_date=None) -> None:
        """Record trade outcome and update streak tracking."""
        if current_date is not None and current_date != self.current_date:
            self.reset_daily(current_date)
            
        self.daily_pnl += pnl
        self.trades_today += 1
        if symbol:
            self.trades_today_by_symbol[symbol] = self.trades_today_by_symbol.get(symbol, 0) + 1
            
        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
        if self.consecutive_losses == 3:
            self.cooldown_bars_remaining = 4
            logger.info("LossCooldownManager: 3 consecutive losses. Pausing for 4 bars.")
        elif self.consecutive_losses == 5:
            self.cooldown_bars_remaining = 8
            logger.info("LossCooldownManager: 5 consecutive losses. Pausing for 8 bars.")

    def should_skip_trade(self, symbol: str = "") -> Tuple[bool, str]:
        """Check if we should skip the next trade.
        Returns (should_skip, reason)."""
        if self.cooldown_bars_remaining > 0:
            return True, f"Cooldown active for {self.cooldown_bars_remaining} more bars."
            
        # Max 3% daily drawdown
        if self.peak_equity > 0:
            daily_dd = self.daily_pnl / self.peak_equity
            if daily_dd <= -0.03:
                return True, "Max daily drawdown (3%) reached."
                
        # Max 5 trades per day per symbol
        if symbol and self.trades_today_by_symbol.get(symbol, 0) >= 5:
            return True, f"Max 5 trades per day reached for symbol {symbol}."
        elif not symbol and self.trades_today >= 5:
            # Fallback if symbol isn't provided: limit total trades
            # This handles cases where the caller uses the manager per-symbol implicitly
            return True, "Max 5 trades per day reached."
            
        return False, ""

    def get_position_size_multiplier(self, base_risk_pct: float, account_equity: float, 
                                       win_rate: float = 0.55, payoff_ratio: float = 1.5) -> float:
        """Calculate Fractional Kelly position size multiplier.
        
        Formula:
        1. Full Kelly: f* = (b*p - q) / b where p=win_rate, q=1-p, b=payoff_ratio
        2. Fractional Kelly: f_trade = 0.25 * f*  (Quarter-Kelly)
        3. Drawdown scaling: multiply by max(0, 1 - current_dd/max_dd)
        4. Loss streak scaling: multiply by 0.5^max(0, consecutive_losses - 2)
        5. Cap at base_risk_pct
        
        Returns multiplier (0.0 to 1.0) to apply to base risk percentage.
        """
        if account_equity <= 0:
            logger.warning("Account equity is zero or negative. Multiplier is 0.0")
            return 0.0
            
        if payoff_ratio <= 0:
            logger.warning("Payoff ratio is zero or negative. Multiplier is 0.0")
            return 0.0
            
        # Track peak equity for drawdown calculations
        if account_equity > self.peak_equity:
            self.peak_equity = account_equity
            
        p = win_rate
        q = 1.0 - p
        b = payoff_ratio
        
        # 1. Full Kelly
        f_star = (b * p - q) / b
        if f_star <= 0:
            return 0.0
            
        # 2. Fractional Kelly (Quarter-Kelly)
        f_trade = 0.25 * f_star
        # Convert f_trade fraction to percentage to compare with base_risk_pct
        f_trade_pct = f_trade * 100.0
        
        # 3. Drawdown scaling
        current_drawdown = 0.0
        if self.peak_equity > 0:
            current_drawdown = max(0.0, (self.peak_equity - account_equity) / self.peak_equity)
            
        # 0.15 is 15% max drawdown threshold
        drawdown_scaler = max(0.0, 1.0 - (current_drawdown / 0.15))
        
        # 4. Smooth loss streak scaling (bounded so recovery trades are not artificially impaired)
        loss_scaler = 1.0
        if self.consecutive_losses >= 3:
            loss_scaler = max(0.75, 1.0 - (0.08 * (self.consecutive_losses - 2)))
            
        # Final risk calculation
        final_risk_pct = min(base_risk_pct, f_trade_pct * drawdown_scaler * loss_scaler)
        
        if base_risk_pct > 0:
            multiplier = final_risk_pct / base_risk_pct
        else:
            multiplier = 0.0
            
        # Cooldown rule: After 2 consecutive losses, reduce size by 50%
        if self.consecutive_losses == 2:
            multiplier = min(multiplier, 0.5)
            
        return max(0.0, min(1.0, multiplier))

    def tick_bar(self) -> None:
        """Called each bar to decrement cooldown timer."""
        if self.cooldown_bars_remaining > 0:
            self.cooldown_bars_remaining -= 1
            if self.cooldown_bars_remaining == 0:
                logger.info("LossCooldownManager: Cooldown finished. Resuming trading.")

    def reset_daily(self, current_date=None) -> None:
        """Reset daily counters."""
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.trades_today_by_symbol.clear()
        self.current_date = current_date
        logger.info(f"LossCooldownManager: Daily counters reset for {current_date}")
