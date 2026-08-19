"""
JARVIS AI 4.0 — Centralized Symbol Metadata Registry.
Eliminates all hardcoded "XAU", "GOLD", "JPY", "BTC" string checks scattered across 6+ files.
Provides contract_size, pip_size, pip_value, spread multiplier, asset class, and margin info per symbol.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SymbolSpec:
    """Immutable specification for a tradeable instrument."""
    canonical: str              # Canonical name (e.g. "XAUUSD")
    asset_class: str            # "COMMODITY", "FOREX", "CRYPTO", "INDEX"
    contract_size: float        # Lots → units multiplier
    pip_size: float             # Minimum price increment for 1 pip
    pip_value_per_lot: float    # Dollar value of 1 pip move per 1.0 standard lot
    typical_spread_pips: float  # Expected average spread in pips
    max_spread_pips: float      # Reject trade if spread exceeds this
    typical_atr_pct: float      # Typical daily ATR as % of price
    margin_pct: float           # Margin requirement as % of notional (1:1000 = 0.1%)
    digits: int = 5             # Price precision digits
    is_crypto: bool = False     # 24/7 market — exempt from session blackouts
    is_jpy_quote: bool = False  # JPY-quoted pair (affects pip calculation)

# ─── Master Registry ─────────────────────────────────────────────────────────
_REGISTRY: Dict[str, SymbolSpec] = {
    "XAUUSD": SymbolSpec(
        canonical="XAUUSD", asset_class="COMMODITY",
        contract_size=100.0, pip_size=0.1, pip_value_per_lot=10.0,
        typical_spread_pips=2.0, max_spread_pips=5.0,
        typical_atr_pct=0.8, margin_pct=0.1, digits=2
    ),
    "EURUSD": SymbolSpec(
        canonical="EURUSD", asset_class="FOREX",
        contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0,
        typical_spread_pips=1.2, max_spread_pips=3.0,
        typical_atr_pct=0.4, margin_pct=0.1, digits=5
    ),
    "GBPUSD": SymbolSpec(
        canonical="GBPUSD", asset_class="FOREX",
        contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0,
        typical_spread_pips=1.5, max_spread_pips=4.0,
        typical_atr_pct=0.5, margin_pct=0.1, digits=5
    ),
    "USDJPY": SymbolSpec(
        canonical="USDJPY", asset_class="FOREX",
        contract_size=100_000.0, pip_size=0.01, pip_value_per_lot=6.80,
        typical_spread_pips=1.0, max_spread_pips=3.0,
        typical_atr_pct=0.4, margin_pct=0.1, digits=3, is_jpy_quote=True
    ),
    "BTCUSD": SymbolSpec(
        canonical="BTCUSD", asset_class="CRYPTO",
        contract_size=1.0, pip_size=0.01, pip_value_per_lot=0.01,
        typical_spread_pips=30.0, max_spread_pips=80.0,
        typical_atr_pct=2.5, margin_pct=0.5, digits=2, is_crypto=True
    ),
}

# ─── Broker Alias Resolution ─────────────────────────────────────────────────
_ALIAS_MAP: Dict[str, str] = {
    "GOLD.I#": "XAUUSD", "GOLD": "XAUUSD", "GOLD.I": "XAUUSD", "XAUUSD#": "XAUUSD", "XAUUSD.I#": "XAUUSD", "XAUUSD.I": "XAUUSD",
    "EURUSD#": "EURUSD", "EURUSD.I#": "EURUSD", "EURUSD.I": "EURUSD",
    "GBPUSD#": "GBPUSD", "GBPUSD.I#": "GBPUSD", "GBPUSD.I": "GBPUSD",
    "USDJPY#": "USDJPY", "USDJPY.I#": "USDJPY", "USDJPY.I": "USDJPY",
    "BTCUSD#": "BTCUSD", "BTCUSD.I#": "BTCUSD", "BTCUSD.I": "BTCUSD",
}


def resolve(symbol: str) -> SymbolSpec:
    """Resolves any broker alias to its canonical SymbolSpec."""
    key = symbol.upper().strip()
    if key in _REGISTRY:
        return _REGISTRY[key]
    canonical = _ALIAS_MAP.get(key)
    if canonical and canonical in _REGISTRY:
        return _REGISTRY[canonical]
    # Fuzzy fallback: check if any known canonical is a substring
    for canon, spec in _REGISTRY.items():
        if canon in key or key in canon:
            return spec
    # Ultimate fallback — generic forex
    return SymbolSpec(
        canonical=key, asset_class="FOREX",
        contract_size=100_000.0, pip_size=0.0001, pip_value_per_lot=10.0,
        typical_spread_pips=2.0, max_spread_pips=5.0,
        typical_atr_pct=0.5, margin_pct=0.1
    )


def is_crypto(symbol: str) -> bool:
    return resolve(symbol).is_crypto

def is_jpy_quote(symbol: str) -> bool:
    return resolve(symbol).is_jpy_quote

def get_contract_size(symbol: str) -> float:
    return resolve(symbol).contract_size

def get_pip_size(symbol: str) -> float:
    return resolve(symbol).pip_size

def get_max_spread(symbol: str) -> float:
    return resolve(symbol).max_spread_pips
