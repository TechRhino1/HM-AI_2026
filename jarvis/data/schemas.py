"""
JARVIS AI 3.0 — Core Data Schemas & Type Definitions.
Defines immutable data models, enums, analyst reports, hypothesis structures, and decision objects.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

class MarketRegime(str, Enum):
    TREND_BULL = "TREND_BULL"
    TREND_BEAR = "TREND_BEAR"
    WEAK_TREND = "WEAK_TREND"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    TRANSITION = "TRANSITION"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    EVENT_RISK = "EVENT_RISK"
    POST_EVENT = "POST_EVENT"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"

class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"
    WAIT = "WAIT"

class ExecutionMode(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    DEMO = "DEMO"
    DISABLED = "DISABLED"

class AnalystRole(str, Enum):
    STRUCTURE = "STRUCTURE"
    MOMENTUM = "MOMENTUM"
    LIQUIDITY = "LIQUIDITY"
    VOLATILITY = "VOLATILITY"
    MACRO = "MACRO"
    RISK = "RISK"
    DEVIL_ADVOCATE = "DEVIL_ADVOCATE"

@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

@dataclass
class SwingPoint:
    index: int
    price: float
    time: datetime
    point_type: str  # "HIGH" or "LOW"

@dataclass
class StructureContext:
    bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    higher_highs: bool = False
    higher_lows: bool = False
    lower_highs: bool = False
    lower_lows: bool = False
    bos: bool = False
    bos_type: str = "NONE"
    choch: bool = False
    choch_type: str = "NONE"
    demand_zone: tuple = (0.0, 0.0)
    supply_zone: tuple = (0.0, 0.0)
    equilibrium_price: float = 0.0
    discount_premium_zone: str = "EQUILIBRIUM"  # "DISCOUNT", "PREMIUM", "EQUILIBRIUM"
    order_blocks: List[Dict[str, Any]] = field(default_factory=list)
    fair_value_gaps: List[Dict[str, Any]] = field(default_factory=list)
    key_levels: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class LiquidityContext:
    equal_highs: bool = False
    equal_lows: bool = False
    sweep_detected: bool = False
    sweep_type: str = "NONE"  # "BULLISH_SWEEP", "BEARISH_SWEEP"
    sweep_level: float = 0.0
    sweep_magnitude: float = 0.0
    liquidity_pools: List[Dict[str, Any]] = field(default_factory=list)
    buy_side_liquidity: float = 0.0
    sell_side_liquidity: float = 0.0

@dataclass
class VolatilityContext:
    atr: float = 0.0
    atr_percent: float = 0.0
    state: str = "NORMAL"  # "COMPRESSION", "NORMAL", "EXPANSION", "EXTREME"
    bollinger_bandwidth: float = 0.0
    current_spread_pips: float = 0.0
    max_allowed_spread_pips: float = 35.0
    is_excessive_spread: bool = False

@dataclass
class MomentumContext:
    rsi: float = 50.0
    adx: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    trend_score: int = 0
    trend_persistence: int = 0
    slope: float = 0.0
    roc: float = 0.0
    divergence: str = "NONE"  # "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NONE"
    acceleration: str = "STEADY"  # "ACCELERATING", "DECELERATING", "EXHAUSTION", "STEADY"

@dataclass
class SessionContext:
    current_session: str = "OFF_HOURS"  # "ASIAN", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"
    is_prime_session: bool = False
    utc_hour: int = 0
    day_of_week: int = 0

@dataclass
class MarketContext:
    symbol: str
    timestamp: datetime
    current_price: float
    bid: float
    ask: float
    structure: StructureContext
    liquidity: LiquidityContext
    volatility: VolatilityContext
    momentum: MomentumContext
    session: SessionContext
    vwap: float = 0.0
    context_quality: float = 100.0
    strategy: str = ""
    mtf_confluence_score: float = 0.0
    mtf_alignment: Dict[str, str] = field(default_factory=dict)

@dataclass
class RegimeOutput:
    primary_regime: MarketRegime
    probabilities: Dict[str, float]
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    regime_transition: bool = False
    regime_persistence: int = 0

@dataclass
class AnalystReport:
    role: AnalystRole
    symbol: str
    bias: str
    score: float
    confidence: float
    evidence: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DevilAdvocateReport:
    symbol: str
    counter_bias: str
    penalty_score: float
    invalidation_risk_coefficient: float
    threats_detected: List[str] = field(default_factory=list)
    invalidation_triggers: List[str] = field(default_factory=list)
    liquidity_traps: List[str] = field(default_factory=list)
    critique_confidence: float = 1.0
    correlated_threats: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

@dataclass
class CompetingHypotheses:
    primary_thesis: str
    primary_probability: float
    primary_evidence: List[str]
    alternative_thesis: str
    alternative_probability: float
    alternative_evidence: List[str]
    no_trade_probability: float
    invalidation_criteria: List[str]
    confirmation_conditions: List[str]
    expected_outcome: str
    structural_invalidation_distance: float = 0.0

@dataclass
class TradeQualityGateResult:
    passed: bool
    checks: Dict[str, bool]
    failing_reasons: List[str] = field(default_factory=list)

@dataclass
class DecisionObject:
    symbol: str
    timestamp: datetime
    regime: RegimeOutput
    bias: str
    probabilities: Dict[str, float]
    strategy: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    calculated_risk_percent: float
    expected_value: float
    model_confidence: float
    adversarial_penalty: float
    invalidation_levels: List[str]
    bull_case: List[str]
    bear_case: List[str]
    risk_factors: List[str]
    quality_gate: TradeQualityGateResult
    decision: str
    execution_authorized: bool = False
    sl_distance: float = 0.0
    tp_distance: float = 0.0
    waiting_reasons: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "regime": {
                "primary": self.regime.primary_regime.value,
                "probabilities": self.regime.probabilities,
                "confidence": self.regime.confidence
            },
            "bias": self.bias,
            "probabilities": self.probabilities,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "sl_distance": self.sl_distance,
            "tp_distance": self.tp_distance,
            "risk_reward_ratio": self.risk_reward_ratio,
            "calculated_risk_percent": self.calculated_risk_percent,
            "expected_value": self.expected_value,
            "model_confidence": self.model_confidence,
            "adversarial_penalty": self.adversarial_penalty,
            "invalidation_levels": self.invalidation_levels,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "risk_factors": self.risk_factors,
            "quality_gate": {
                "passed": self.quality_gate.passed,
                "checks": self.quality_gate.checks,
                "failing_reasons": self.quality_gate.failing_reasons
            },
            "waiting_reasons": self.waiting_reasons,
            "rejection_reasons": self.rejection_reasons,
            "decision": self.decision,
            "execution_authorized": self.execution_authorized
        }

@dataclass
class AccountSnapshot:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    leverage: int
    profit: float = 0.0
    name: str = "Trader"
    company: str = "XM Global"
    currency: str = "USD"
    trade_allowed: bool = True
    last_sync_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "login": self.login,
            "server": self.server,
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "margin": round(self.margin, 2),
            "free_margin": round(self.free_margin, 2),
            "margin_level": round(self.margin_level, 2),
            "leverage": self.leverage,
            "profit": round(self.profit, 2),
            "name": self.name,
            "company": self.company,
            "currency": self.currency,
            "trade_allowed": self.trade_allowed,
            "last_sync_time": self.last_sync_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(self.last_sync_time, datetime) else str(self.last_sync_time)
        }

@dataclass
class PositionSnapshot:
    ticket: int
    symbol: str
    type: str
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    swap: float
    commission: float
    open_time: str
    magic: int
    comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "type": self.type,
            "volume": self.volume,
            "open_price": self.open_price,
            "current_price": self.current_price,
            "sl": self.sl,
            "tp": self.tp,
            "profit": self.profit,
            "swap": self.swap,
            "commission": self.commission,
            "open_time": self.open_time,
            "magic": self.magic,
            "comment": self.comment
        }
