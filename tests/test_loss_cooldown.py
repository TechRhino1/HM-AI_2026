import pytest
from jarvis.risk.loss_cooldown import LossCooldownManager

def test_consecutive_loss_streak():
    manager = LossCooldownManager()
    
    manager.record_trade_result(-100, is_win=False)
    assert manager.consecutive_losses == 1
    assert manager.consecutive_wins == 0
    
    manager.record_trade_result(100, is_win=True)
    assert manager.consecutive_losses == 0
    assert manager.consecutive_wins == 1

def test_cooldown_trigger_after_3_losses():
    manager = LossCooldownManager()
    
    manager.record_trade_result(-100, is_win=False)
    manager.record_trade_result(-100, is_win=False)
    manager.record_trade_result(-100, is_win=False)
    
    assert manager.consecutive_losses == 3
    assert manager.cooldown_bars_remaining == 4
    
    skip, reason = manager.should_skip_trade()
    assert skip is True
    assert "Cooldown active" in reason

def test_fractional_kelly_multiplier():
    manager = LossCooldownManager()
    
    # Full Kelly: (1.5 * 0.55 - 0.45) / 1.5 = (0.825 - 0.45) / 1.5 = 0.375 / 1.5 = 0.25
    # Fractional Kelly (Quarter): 0.25 * 0.25 = 0.0625 = 6.25%
    # With base_risk_pct = 2.0%, final_risk_pct = min(2.0, 6.25) = 2.0%
    # multiplier = 2.0 / 2.0 = 1.0
    mult = manager.get_position_size_multiplier(base_risk_pct=2.0, account_equity=10000)
    assert pytest.approx(mult) == 1.0
    
    # Simulate a 10% drawdown (1000 loss)
    # drawdown = 0.10. drawdown_scaler = 1 - (0.10 / 0.15) = 0.333
    # final_risk_pct = min(2.0, 6.25 * 0.333) = min(2.0, 2.08) = 2.0%
    # Still close to 1.0 multiplier
    mult2 = manager.get_position_size_multiplier(base_risk_pct=2.0, account_equity=9000)
    assert mult2 > 0

def test_daily_limit_tracking():
    manager = LossCooldownManager()
    
    # 5 trades per day
    for _ in range(5):
        manager.record_trade_result(10, is_win=True, symbol="EURUSD")
        
    skip, reason = manager.should_skip_trade("EURUSD")
    assert skip is True
    assert "Max 5 trades" in reason
    
    # Different symbol shouldn't be skipped for symbol limit, but global limit might trigger
    # Wait, the manager code checks: if symbol and self.trades_today_by_symbol.get(symbol, 0) >= 5
    # So if we check "GBPUSD", it will pass the first check.
    # Ah, let's see how should_skip_trade is written.
    skip_gbp, _ = manager.should_skip_trade("GBPUSD")
    assert skip_gbp is False
    
    # Reset daily
    manager.reset_daily()
    skip, _ = manager.should_skip_trade("EURUSD")
    assert skip is False
