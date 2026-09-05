"""
JARVIS AI 4.0 — Institutional Symbol-Specific Configuration Matrix.
Defines separate, specialized trading logic, Bayesian strategy priors,
dynamic SL/TP envelopes, fast-cash profit banking, trailing ratchets,
session hours, and XM Ultra Low Standard account specifications.

CRITICAL INVARIANCE: Everything related to XAUUSD / Gold is strictly preserved
and 100% untouched.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class SymbolProfileConfig:
    symbol: str
    canonical: str
    asset_class: str  # "CRYPTO", "INDEX", "COMMODITY", "FOREX"
    
    # Strategy Priorities & Bayesian Likelihood Weights
    strategy_weights: Dict[str, float]
    banned_strategies: List[str] = field(default_factory=list)
    
    # Dynamic Structural Levels & Stop-Loss Breathing Room
    sl_atr_multiplier: float = 1.80
    min_target_rr: float = 2.0
    asym_rr: float = 3.5
    anti_wick_buffer_atr: float = 0.35
    
    # Profit Protection & Execution Ratchet
    fast_cash_r: float = 1.00
    fast_cash_volume_pct: float = 0.50  # Bank 50% or 60%
    be_trigger_r: float = 1.00
    be_buffer_pct: float = 0.08
    runner_trail_atr: float = 2.0
    
    # Session & Timing Filters
    session_restriction: bool = False
    allowed_utc_hours: Optional[Tuple[int, int]] = None  # (start_hour, end_hour) inclusive
    
    # XM Ultra Low Standard Account Specifications
    contract_size: float = 1.0
    pip_size: float = 0.01
    pip_value_per_lot: float = 0.01
    digits: int = 2
    typical_spread_pips: float = 15.0
    max_allowed_spread_pips: float = 50.0
    commission_per_lot: float = 0.0  # XM Ultra Low Standard has $0.00 commission
    min_volume: float = 0.01
    volume_step: float = 0.01
    margin_pct: float = 0.5


# ─── SYMBOL-SPECIFIC INSTITUTIONAL CONFIGURATION MATRIX ──────────────────────────

SYMBOL_PROFILES: Dict[str, SymbolProfileConfig] = {
    # =========================================================================
    # 1. CRYPTO ASSETS (XM Ultra Low Standard Specs: $0 Commission, 24/7)
    # =========================================================================
    "BTCUSD": SymbolProfileConfig(
        symbol="BTCUSD",
        canonical="BTCUSD",
        asset_class="CRYPTO",
        # Bitcoin: Momentum breakouts and trend continuation.
        strategy_weights={
            "BREAKOUT_EXPANSION": 3.6,
            "TREND_FOLLOWING": 3.0,
            "CHOCH_STRUCTURAL_REVERSAL": 2.0,
            "TREND_PULLBACK": 1.6,
            "LIQUIDITY_SWEEP_REVERSAL": 0.0,  # Banned: fading BTC sweeps causes asymmetric losses
            "RANGE_MEAN_REVERSION": 0.0,
        },
        banned_strategies=["LIQUIDITY_SWEEP_REVERSAL", "RANGE_MEAN_REVERSION"],
        sl_atr_multiplier=2.20,  # Balanced breathing room prevents oversized losses
        min_target_rr=2.0,
        asym_rr=3.5,
        anti_wick_buffer_atr=0.45,
        fast_cash_r=0.95,  # Bank early at +0.95R
        fast_cash_volume_pct=0.50,
        be_trigger_r=0.95,
        runner_trail_atr=2.40,
        session_restriction=False,
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=0.01,
        pip_value_per_lot=0.01,
        digits=2,
        typical_spread_pips=1500.0,  # ~$15.00 on $60,000+ price (0.025%)
        max_allowed_spread_pips=3000.0,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.5
    ),

    "ETHUSD": SymbolProfileConfig(
        symbol="ETHUSD",
        canonical="ETHUSD",
        asset_class="CRYPTO",
        # Ethereum: High beta to BTC, explosive expansion legs, wicks through shallow stops
        strategy_weights={
            "BREAKOUT_EXPANSION": 3.4,
            "TREND_FOLLOWING": 2.8,
            "CHOCH_STRUCTURAL_REVERSAL": 2.0,
            "TREND_PULLBACK": 1.5,
            "LIQUIDITY_SWEEP_REVERSAL": 0.0,  # Banned: fading ETH sweeps is toxic
            "RANGE_MEAN_REVERSION": 0.1,
        },
        banned_strategies=["LIQUIDITY_SWEEP_REVERSAL"],
        sl_atr_multiplier=2.65,
        min_target_rr=2.0,
        asym_rr=3.5,
        anti_wick_buffer_atr=0.50,
        fast_cash_r=0.85,
        fast_cash_volume_pct=0.50,
        be_trigger_r=0.85,
        runner_trail_atr=2.60,
        session_restriction=False,
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=0.01,
        pip_value_per_lot=0.01,
        digits=2,
        typical_spread_pips=120.0,  # ~$1.20 on $2,500+ price (0.05%)
        max_allowed_spread_pips=300.0,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.5
    ),

    "SOLUSD": SymbolProfileConfig(
        symbol="SOLUSD",
        canonical="SOLUSD",
        asset_class="CRYPTO",
        # Solana: High-beta crypto. Explosive trend runs, wide wicks.
        strategy_weights={
            "BREAKOUT_EXPANSION": 3.5,
            "TREND_FOLLOWING": 2.8,
            "CHOCH_STRUCTURAL_REVERSAL": 2.0,
            "TREND_PULLBACK": 1.6,
            "LIQUIDITY_SWEEP_REVERSAL": 0.0,
            "RANGE_MEAN_REVERSION": 0.0,
        },
        banned_strategies=["LIQUIDITY_SWEEP_REVERSAL", "RANGE_MEAN_REVERSION"],
        sl_atr_multiplier=2.40,  # Calibrated breathing room prevents outsized loss
        min_target_rr=2.0,
        asym_rr=3.5,
        anti_wick_buffer_atr=0.45,
        fast_cash_r=0.90,  # Bank 50% at +0.90R
        fast_cash_volume_pct=0.50,
        be_trigger_r=0.90,
        runner_trail_atr=2.50,
        session_restriction=False,
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=0.01,
        pip_value_per_lot=0.01,
        digits=2,
        typical_spread_pips=15.0,  # ~$0.15 on $130+ price (0.11%)
        max_allowed_spread_pips=50.0,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.5
    ),

    # =========================================================================
    # 2. EQUITY INDICES (XM Ultra Low Standard Specs: $0 Commission, 13:00-21:00 UTC)
    # =========================================================================
    "US500": SymbolProfileConfig(
        symbol="US500",
        canonical="US500",
        asset_class="INDEX",
        # S&P 500: Broad basket mean-reverting. Banning trend following in chop.
        strategy_weights={
            "LIQUIDITY_SWEEP_REVERSAL": 3.5,
            "CHOCH_STRUCTURAL_REVERSAL": 3.0,
            "RANGE_MEAN_REVERSION": 2.4,
            "TREND_PULLBACK": 1.8,
            "BREAKOUT_EXPANSION": 0.5,
            "TREND_FOLLOWING": 0.0,  # Banned: blind trend chasing causes -$789 loss
        },
        banned_strategies=["TREND_FOLLOWING"],
        sl_atr_multiplier=1.65,
        min_target_rr=2.0,
        asym_rr=3.2,
        anti_wick_buffer_atr=0.30,
        fast_cash_r=1.00,
        fast_cash_volume_pct=0.50,
        be_trigger_r=1.00,
        runner_trail_atr=2.10,
        session_restriction=True,
        allowed_utc_hours=(13, 21),  # Active US Cash & NY Overlap only (eliminates overnight chop)
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=0.1,
        pip_value_per_lot=1.0,
        digits=1,
        typical_spread_pips=0.6,
        max_allowed_spread_pips=2.5,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.2
    ),

    "NAS100": SymbolProfileConfig(
        symbol="NAS100",
        canonical="NAS100",
        asset_class="INDEX",
        # Nasdaq 100: High-beta tech growth index. Trends cleanly during NY cash session (52.4% WR, 0.89 PF).
        strategy_weights={
            "TREND_FOLLOWING": 2.8,
            "BREAKOUT_EXPANSION": 2.6,
            "LIQUIDITY_SWEEP_REVERSAL": 2.5,
            "TREND_PULLBACK": 2.2,
            "CHOCH_STRUCTURAL_REVERSAL": 2.0,
            "RANGE_MEAN_REVERSION": 0.8,
        },
        banned_strategies=[],
        sl_atr_multiplier=1.75,
        min_target_rr=2.2,
        asym_rr=3.5,
        anti_wick_buffer_atr=0.35,
        fast_cash_r=1.00,
        fast_cash_volume_pct=0.50,
        be_trigger_r=1.00,
        runner_trail_atr=2.20,
        session_restriction=True,
        allowed_utc_hours=(13, 21),  # Active US Cash & NY Overlap only
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=1.0,
        pip_value_per_lot=1.0,
        digits=1,
        typical_spread_pips=2.0,
        max_allowed_spread_pips=7.0,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.2
    ),

    "US30": SymbolProfileConfig(
        symbol="US30",
        canonical="US30",
        asset_class="INDEX",
        # Wall Street 30: Large point swings (300-600 pts). Focus on institutional NY trend expansion.
        strategy_weights={
            "TREND_FOLLOWING": 2.8,
            "BREAKOUT_EXPANSION": 2.5,
            "TREND_PULLBACK": 2.2,
            "CHOCH_STRUCTURAL_REVERSAL": 2.0,
            "LIQUIDITY_SWEEP_REVERSAL": 0.5,
            "RANGE_MEAN_REVERSION": 0.8,
        },
        banned_strategies=[],
        sl_atr_multiplier=1.75,
        min_target_rr=2.2,
        asym_rr=3.5,
        anti_wick_buffer_atr=0.35,
        fast_cash_r=1.00,
        fast_cash_volume_pct=0.50,
        be_trigger_r=1.00,
        runner_trail_atr=2.20,
        session_restriction=True,
        allowed_utc_hours=(13, 21),  # Active US Cash & NY Overlap only
        # XM Ultra Low Standard Specs
        contract_size=1.0,
        pip_size=1.0,
        pip_value_per_lot=1.0,
        digits=1,
        typical_spread_pips=2.5,
        max_allowed_spread_pips=8.0,
        commission_per_lot=0.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.2
    ),

    # =========================================================================
    # 3. COMMODITIES — 100% UNTOUCHED AND PRESERVED INVARIANCE
    # =========================================================================
    "XAUUSD": SymbolProfileConfig(
        symbol="XAUUSD",
        canonical="XAUUSD",
        asset_class="COMMODITY",
        # GOLD: Proven alpha producer (+$3,014.70, 56.6% WR, 2.40 PF) — 100% PRESERVED
        strategy_weights={
            "LIQUIDITY_SWEEP_REVERSAL": 3.0,
            "CHOCH_STRUCTURAL_REVERSAL": 2.5,
            "TREND_PULLBACK": 2.2,
            "BREAKOUT_EXPANSION": 1.2,
            "RANGE_MEAN_REVERSION": 1.5,
            "TREND_FOLLOWING": 1.8,
        },
        banned_strategies=[],
        sl_atr_multiplier=2.80,  # Exact winning wide runner envelope
        min_target_rr=2.0,
        asym_rr=4.2,
        anti_wick_buffer_atr=0.35,
        fast_cash_r=1.00,
        fast_cash_volume_pct=0.60,  # Bank 60% at 1.0R
        be_trigger_r=1.00,
        runner_trail_atr=2.60,
        session_restriction=False,
        # Standard Commodity specs
        contract_size=100.0,
        pip_size=0.01,
        pip_value_per_lot=1.0,
        digits=2,
        typical_spread_pips=2.0,
        max_allowed_spread_pips=5.0,
        commission_per_lot=5.0,  # 100% UNCHANGED
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.1
    ),

    "WTI": SymbolProfileConfig(
        symbol="WTI",
        canonical="WTI",
        asset_class="COMMODITY",
        # Crude Oil: (+$469.20, 55.9% WR, 1.19 PF) — PRESERVED
        strategy_weights={
            "LIQUIDITY_SWEEP_REVERSAL": 2.4,
            "TREND_PULLBACK": 2.2,
            "RANGE_MEAN_REVERSION": 1.6,
            "TREND_FOLLOWING": 1.2,
            "CHOCH_STRUCTURAL_REVERSAL": 1.5,
            "BREAKOUT_EXPANSION": 0.8,
        },
        banned_strategies=[],
        sl_atr_multiplier=2.80,
        min_target_rr=2.0,
        asym_rr=3.6,
        anti_wick_buffer_atr=0.35,
        fast_cash_r=1.00,
        fast_cash_volume_pct=0.60,
        be_trigger_r=1.00,
        runner_trail_atr=2.60,
        session_restriction=False,
        contract_size=1000.0,
        pip_size=0.01,
        pip_value_per_lot=10.0,
        digits=2,
        typical_spread_pips=3.0,
        max_allowed_spread_pips=8.0,
        commission_per_lot=5.0,
        min_volume=0.01,
        volume_step=0.01,
        margin_pct=0.2
    ),

    # =========================================================================
    # 4. FOREX MAJORS
    # =========================================================================
    "EURUSD": SymbolProfileConfig(
        symbol="EURUSD", canonical="EURUSD", asset_class="FOREX",
        strategy_weights={"RANGE_MEAN_REVERSION": 2.6, "LIQUIDITY_SWEEP_REVERSAL": 2.4, "CHOCH_STRUCTURAL_REVERSAL": 2.0, "TREND_PULLBACK": 1.4, "TREND_FOLLOWING": 0.1, "BREAKOUT_EXPANSION": 0.0},
        banned_strategies=["BREAKOUT_EXPANSION"], sl_atr_multiplier=1.80, min_target_rr=2.0, asym_rr=3.2,
        fast_cash_r=1.00, fast_cash_volume_pct=0.50, be_trigger_r=1.00, runner_trail_atr=1.80,
        session_restriction=True, allowed_utc_hours=(7, 18), contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0, digits=5,
        typical_spread_pips=0.8, max_allowed_spread_pips=2.5, commission_per_lot=0.0, margin_pct=0.1
    ),
    "GBPUSD": SymbolProfileConfig(
        symbol="GBPUSD", canonical="GBPUSD", asset_class="FOREX",
        strategy_weights={"LIQUIDITY_SWEEP_REVERSAL": 2.8, "CHOCH_STRUCTURAL_REVERSAL": 2.4, "RANGE_MEAN_REVERSION": 2.2, "TREND_PULLBACK": 1.6, "TREND_FOLLOWING": 0.2, "BREAKOUT_EXPANSION": 0.0},
        banned_strategies=["BREAKOUT_EXPANSION"], sl_atr_multiplier=1.80, min_target_rr=2.0, asym_rr=3.2,
        fast_cash_r=1.00, fast_cash_volume_pct=0.50, be_trigger_r=1.00, runner_trail_atr=1.80,
        session_restriction=True, allowed_utc_hours=(7, 18), contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0, digits=5,
        typical_spread_pips=1.0, max_allowed_spread_pips=3.0, commission_per_lot=0.0, margin_pct=0.1
    ),
    "USDJPY": SymbolProfileConfig(
        symbol="USDJPY", canonical="USDJPY", asset_class="FOREX",
        strategy_weights={"TREND_PULLBACK": 2.4, "TREND_FOLLOWING": 2.2, "LIQUIDITY_SWEEP_REVERSAL": 2.0, "RANGE_MEAN_REVERSION": 1.6, "CHOCH_STRUCTURAL_REVERSAL": 1.5, "BREAKOUT_EXPANSION": 0.5},
        sl_atr_multiplier=1.80, min_target_rr=2.0, asym_rr=3.2, fast_cash_r=1.00, fast_cash_volume_pct=0.50, be_trigger_r=1.00, runner_trail_atr=1.80,
        session_restriction=False, contract_size=100_000.0, pip_size=0.01, pip_value_per_lot=6.80, digits=3,
        typical_spread_pips=0.9, max_allowed_spread_pips=3.0, commission_per_lot=0.0, margin_pct=0.1
    ),
    "AUDUSD": SymbolProfileConfig(
        symbol="AUDUSD", canonical="AUDUSD", asset_class="FOREX",
        strategy_weights={"RANGE_MEAN_REVERSION": 2.5, "LIQUIDITY_SWEEP_REVERSAL": 2.3, "TREND_PULLBACK": 1.5, "CHOCH_STRUCTURAL_REVERSAL": 1.8, "TREND_FOLLOWING": 0.1, "BREAKOUT_EXPANSION": 0.0},
        banned_strategies=["BREAKOUT_EXPANSION"], sl_atr_multiplier=1.80, min_target_rr=2.0, asym_rr=3.2,
        fast_cash_r=1.00, fast_cash_volume_pct=0.50, be_trigger_r=1.00, runner_trail_atr=1.80,
        session_restriction=False, contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0, digits=5,
        typical_spread_pips=1.0, max_allowed_spread_pips=3.0, commission_per_lot=0.0, margin_pct=0.1
    ),
    "USDCHF": SymbolProfileConfig(
        symbol="USDCHF", canonical="USDCHF", asset_class="FOREX",
        strategy_weights={"RANGE_MEAN_REVERSION": 2.5, "LIQUIDITY_SWEEP_REVERSAL": 2.2, "TREND_PULLBACK": 1.5, "CHOCH_STRUCTURAL_REVERSAL": 1.8, "TREND_FOLLOWING": 0.1, "BREAKOUT_EXPANSION": 0.0},
        banned_strategies=["BREAKOUT_EXPANSION"], sl_atr_multiplier=1.80, min_target_rr=2.0, asym_rr=3.2,
        fast_cash_r=1.00, fast_cash_volume_pct=0.50, be_trigger_r=1.00, runner_trail_atr=1.80,
        session_restriction=True, allowed_utc_hours=(7, 18), contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0, digits=5,
        typical_spread_pips=1.2, max_allowed_spread_pips=3.0, commission_per_lot=0.0, margin_pct=0.1
    ),
}

# Alias resolution mapping
_ALIAS_TO_CANONICAL: Dict[str, str] = {
    "GOLD": "XAUUSD", "GOLD.I#": "XAUUSD", "GOLD.I": "XAUUSD", "XAUUSD#": "XAUUSD", "XAUUSD.I#": "XAUUSD", "XAUUSD.I": "XAUUSD",
    "BTCUSD#": "BTCUSD", "BTCUSD.I#": "BTCUSD", "BTCUSD.I": "BTCUSD", "BITCOIN": "BTCUSD",
    "ETHUSD#": "ETHUSD", "ETHUSD.I#": "ETHUSD", "ETHEREUM": "ETHUSD", "ETH": "ETHUSD",
    "SOLUSD#": "SOLUSD", "SOLUSD.I#": "SOLUSD", "SOLANA": "SOLUSD", "SOL": "SOLUSD",
    "US500#": "US500", "SPX500": "US500", "SP500": "US500", "US500.I#": "US500",
    "NAS100#": "NAS100", "USTECH": "NAS100", "NDX100": "NAS100", "US100": "NAS100",
    "US30#": "US30", "DJ30": "US30", "WALLSTREET": "US30", "US30CASH#": "US30",
    "USOIL": "WTI", "OIL": "WTI", "CRUDE": "WTI", "USOIL.I#": "WTI", "OIL.I#": "WTI", "CL": "WTI", "OILCASH#": "WTI",
    "EURUSD#": "EURUSD", "EURUSD.I#": "EURUSD",
    "GBPUSD#": "GBPUSD", "GBPUSD.I#": "GBPUSD",
    "USDJPY#": "USDJPY", "USDJPY.I#": "USDJPY",
    "AUDUSD#": "AUDUSD", "AUDUSD.I#": "AUDUSD",
    "USDCHF#": "USDCHF", "USDCHF.I#": "USDCHF",
}


def get_symbol_profile_config(symbol: str) -> SymbolProfileConfig:
    """Returns the dedicated, symbol-specific configuration profile."""
    key = str(symbol or "XAUUSD").upper().strip()
    canonical = _ALIAS_TO_CANONICAL.get(key, key)
    if canonical in SYMBOL_PROFILES:
        return SYMBOL_PROFILES[canonical]
    # Fallback to general Forex template if symbol is unknown
    return SymbolProfileConfig(
        symbol=symbol,
        canonical=canonical,
        asset_class="FOREX",
        strategy_weights={"RANGE_MEAN_REVERSION": 2.0, "LIQUIDITY_SWEEP_REVERSAL": 2.0, "TREND_PULLBACK": 1.5, "CHOCH_STRUCTURAL_REVERSAL": 1.5},
        contract_size=100_000.0,
        pip_size=0.0001,
        pip_value_per_lot=10.0,
        digits=5
    )
