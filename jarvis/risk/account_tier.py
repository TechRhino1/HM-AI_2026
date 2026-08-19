"""
JARVIS AI 4.0 — Unified Account Tier & Micro Definition System.

Provides a single source of truth for account sizing tiers, micro-mode gating,
lot caps, and economic expected-value (EV) scaling across all JARVIS engines.
"""
from enum import Enum
from typing import Dict, Any

class AccountTier(str, Enum):
    ULTRA_SURVIVAL = "ULTRA_SURVIVAL"  # < $40
    MICRO_GROWTH   = "MICRO_GROWTH"    # $40 - $100
    SMALL_ACCOUNT  = "SMALL_ACCOUNT"   # $100 - $250
    STANDARD       = "STANDARD"        # $250 - $1,000
    INSTITUTIONAL  = "INSTITUTIONAL"   # >= $1,000

def get_account_tier(equity: float) -> AccountTier:
    """Returns canonical AccountTier based on current account equity."""
    eq = float(equity)
    if eq < 40.0:
        return AccountTier.ULTRA_SURVIVAL
    elif eq < 100.0:
        return AccountTier.MICRO_GROWTH
    elif eq < 250.0:
        return AccountTier.SMALL_ACCOUNT
    elif eq < 1000.0:
        return AccountTier.STANDARD
    else:
        return AccountTier.INSTITUTIONAL

def is_micro_account(equity: float) -> bool:
    """True if account is in micro mode (< $100 equity)."""
    return float(equity) < 100.0

def get_max_lot_cap(equity: float) -> float:
    """Returns hard lot cap for risk protection on smaller accounts."""
    eq = float(equity)
    if eq < 40.0:
        return 0.01
    elif eq < 100.0:
        return 0.03
    elif eq < 250.0:
        return 0.05
    else:
        return 100.0  # Standard risk sizing handles larger accounts

def get_effective_min_ev(equity: float, planned_risk_dollars: float) -> float:
    """
    Returns mathematically sound expected-value hurdle (in dollars)
    scaled smoothly to account equity and 0.01 lot-floor constraints (§3).
    """
    eq = float(equity)
    prd = float(planned_risk_dollars)
    
    if eq < 100.0:
        return max(0.01, prd * 0.05)
    elif eq < 500.0:
        return max(0.05, prd * 0.15)
    elif eq < 1000.0:
        return max(0.15, prd * 0.30)
    else:
        return max(0.50, prd * 0.50)
