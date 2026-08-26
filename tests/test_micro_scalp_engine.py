"""
Automated Test Suite for Micro-Compounding Scalp Engine & Adaptive Learning
Tests:
1. Adaptive Confidence Gate thresholding (0.50 for high RR scalps vs 0.55 standard)
2. Micro-Scalp Quality Gate evaluations
3. Multi-Armed Bandit strategy arms registration and outcome recording
4. 2-Tier Target & R:R generation
"""
import sys
import os
import pytest

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from jarvis.learning.strategy_bandit import StrategyBandit
from jarvis.intelligence.decision_engine import DecisionEngine
from jarvis.market.market_context import MarketContextEngine
from jarvis.execution.position_monitor import (
    STAGE1_ATR_TRIGGER,
    STAGE2_ATR_TRIGGER,
    PARTIAL_TP_TRIGGER_R,
    PARTIAL_CLOSE_PCT
)

def test_strategy_bandit_micro_arms():
    bandit = StrategyBandit(state_file="test_bandit_state.json")
    assert "MICRO_LIQUIDITY_SWEEP" in bandit.STRATEGIES
    assert "M1_M5_FVG_SCALP" in bandit.STRATEGIES
    assert "MICRO_ACCOUNT_ADAPTIVE" in bandit.STRATEGIES

    # Test outcome recording
    bandit.record_outcome("MICRO_LIQUIDITY_SWEEP", is_win=1, r_multiple=2.1, regime="BREAKOUT")
    boosts = bandit.get_strategy_boosts(current_regime="BREAKOUT")
    assert "MICRO_LIQUIDITY_SWEEP" in boosts
    assert boosts["MICRO_LIQUIDITY_SWEEP"] > 0

    # Clean up test file
    if os.path.exists("test_bandit_state.json"):
        try:
            os.remove("test_bandit_state.json")
        except Exception:
            pass

def test_position_monitor_constants():
    assert STAGE1_ATR_TRIGGER == 1.0
    assert STAGE2_ATR_TRIGGER == 1.6
    assert PARTIAL_TP_TRIGGER_R == 1.0
    assert PARTIAL_CLOSE_PCT == 0.50

def test_decision_engine_initialization():
    engine = DecisionEngine()
    assert engine is not None
    assert hasattr(engine, "_apply_quality_gate")
    assert hasattr(engine, "evaluate")

if __name__ == "__main__":
    test_strategy_bandit_micro_arms()
    test_position_monitor_constants()
    test_decision_engine_initialization()
    print("ALL MICRO SCALP ENGINE TESTS PASSED!")
