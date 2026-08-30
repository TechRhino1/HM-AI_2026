# JARVIS AI 4.0 — Institutional Quantitative MT5 Trading System

An institutional-grade, multi-factor adaptive algorithmic trading architecture built for MetaTrader 5 (MT5). The system integrates Smart Money Concepts (ICT/SMC), Wyckoff accumulation/distribution frameworks, Minervini Trend Templates, Volatility Contraction Patterns (VCP), and dynamic Fractional Kelly risk management to achieve high-expectancy trade execution.

---

## 🏛️ Master Trader Architecture & Core Innovations

### 1. ICT Fair Value Gap (FVG) & Order Block (OB) Imbalance Engine
- **Fair Value Gap Detection:** Identifies 3-candle price imbalance zones (unmitigated liquidity voids) across multiple timeframes.
- **Order Block Mapping:** Locates high-volume displacement candles that create confirmed Breaks of Structure (BOS).
- **Optimal Trade Entry (OTE):** Calculates precision Fibonacci retracement entries (62.0%, 70.5% sweet spot, and 79.0%) aligned with institutional dealing ranges.
- **Imbalance Mitigation Tracking:** Actively filters out invalidated or mitigated zones in real time.

### 2. Multi-Timeframe Institutional Dealing Range & Premium/Discount Filtering
- **True HTF Equilibrium:** Computes institutional dealing ranges over 200-bar macroeconomic lookbacks.
- **Directional Zone Enforcement:** Hard-blocks BUY entries in Premium zones (top 50% of range) and SELL entries in Discount zones (bottom 50% of range) unless supported by confirmed liquidity sweep reversals.

### 3. Session Killzone Timing Engine
- **Forex Session Gating:** Restricts Forex entries strictly to high-liquidity institutional windows:
  - **London Open Killzone:** 07:00 – 10:00 UTC (initial directional expansion)
  - **New York Open Killzone:** 12:00 – 15:00 UTC (highest volume & overlap)
  - **London Close Window:** 15:00 – 17:00 UTC (mean reversion & position unwinding)
  - **Asian Range Reference Box:** 00:00 – 07:00 UTC (defines liquidity boundary sweeps)

### 4. Advanced Regime & Confluence Stack
- **Wyckoff / ICT Fusion:** Recognizes Wyckoff Springs, Upthrusts, Accumulation/Distribution phases, and Change of Character (CHoCH).
- **Minervini Trend Template & VCP:** Measures multi-stage volatility contractions and multi-timeframe moving average slope alignment.
- **Hard Confluence Gate:** Enforces institutional quality hurdles (Score >= 65/100 for Forex, >= 55/100 for Commodities & Crypto).

### 5. Professional Trade Management & Execution Protocol
- **Asset-Adaptive Partial Exits:** 
  - Takes 33% profit at 1.5R (Forex) or 1.8R (Gold/Crypto).
  - Automatically moves Stop Loss to true Breakeven (0.0R) to eliminate downside risk on remaining position.
- **Dynamic ATR Chandelier Trailing Stop:** Trails remaining runner positions with a 1.5x ATR buffer from recent swing extremes, allowing macro trends to run without premature suffocation.
- **24-Bar Time Stop:** Force-closes stale, non-moving trades after 24 hours on H1 if 0.5R favorable excursion is not achieved, preventing capital lock-up.

### 6. Consecutive Loss Circuit Breakers & Fractional Kelly Position Sizing
- **Streak Protection:**
  - 2 consecutive losses -> automatically cuts position risk by 50%.
  - 3 consecutive losses -> activates a 4-bar mandatory cooling-off period.
  - Daily Drawdown >= 3.0% -> halts all new executions for the remainder of the trading day.
- **Dynamic Kelly Allocation:** Dynamically scales trade size using Quarter-Kelly optimal sizing adjusted for high-water mark drawdown.

### 7. Asset-Class Specific Strategy Specialization
- **Commodities (XAUUSD/Gold):** High-momentum trend following and break-of-structure expansion with structure-anchored stops.
- **Forex Majors (EURUSD, GBPUSD, USDJPY):** Range mean reversion (Bollinger Band 20, 2.0 SD with ADX < 22) and killzone liquidity sweep reversals.
- **Crypto (BTCUSD):** High-volatility swing momentum and multi-timeframe FVG pullbacks.

---

## 📐 Architecture Diagram

`
                RAW MARKET DATA (MT5 Feed / Tick & Bar OHLCV)
                                     │
                                     ▼
                MULTI-TIMEFRAME ENGINE (D1 / H4 / H1 / M15 / M5)
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
  ICT FVG & OB ENGINE         MARKET STRUCTURE           ORDER FLOW & SESSIONS
 (Imbalance, Mitigation,     (200-Bar P/D Range,        (Killzones, Volume Delta,
   OTE 62%-79% Zones)         BOS, CHoCH, Swings)         Absorption Traps)
         └───────────────────────────┬───────────────────────────┘
                                     │
                                     ▼
                      MASTER CONFLUENCE SCORING ENGINE
                 (Wyckoff + Minervini VCP + ICT Triple Confluence)
                                     │
                                     ▼
                         AI DECISION & QUALITY GATE
              (Hard Confluence >= 65, Session Gating, EV & R:R)
                                     │
                                     ▼
                     DYNAMIC RISK & LOSS COOLDOWN MANAGER
                (Fractional Kelly, 3-Loss Circuit Breaker, 3% DD)
                                     │
                                     ▼
                     EXECUTION & ACTIVE TRADE MANAGEMENT
              (Partials at 1.5R/1.8R, True BE, ATR Trail, 24-Bar Time Stop)
`

---

## 🛠️ Project Structure

`
HM-AI-2026/
├── jarvis/
│   ├── analysts/               # Specialized AI analyst agents (Structure, Flow, Momentum, etc.)
│   ├── backtesting/            # Event-driven backtesting engine & performance analytics
│   ├── core/                   # Configuration, symbol registry, and regime classifiers
│   ├── data/                   # Data schemas, database models, and symbol resolvers
│   ├── intelligence/           # Decision engine, master confluence, mean reversion, strategy selector
│   ├── market/                 # FVG engine, session engine, market context, liquidity sweeps
│   └── risk/                   # Loss cooldown manager, circuit breakers, position sizing
├── tests/                      # Automated pytest unit and integration test suite
├── run_multiasset_6m_backtest.py # Real 6-month MT5 historical backtest benchmark suite
└── README.md                   # System documentation
`

---

## 🚀 Installation & Usage

### 1. Environment Setup
`ash
# Clone the repository
git clone https://github.com/TechRhino1/HM-AI_2026.git
cd HM-AI-2026

# Install dependencies
pip install -r requirements.txt
`

### 2. Run Test Suite
Verify that all 109 system tests pass:
` ash
python -m pytest tests/ -v
`

### 3. Run Real MT5 1-Year Multi-Asset Benchmark (43,800 H1 Bars)
Ensure your MetaTrader 5 terminal is open and logged into your broker:
```bash
# Run comprehensive 1-year benchmark across 5 core assets (8,760 H1 bars each)
python -u run_comprehensive_1y_mt5_backtest.py

# Or run fast 6-month benchmark
python -u run_multiasset_6m_backtest.py
```

---

## 📊 1-Year Multi-Asset Historical Benchmarks (Real MT5 Data: 43,800 H1 Bars)

| Metric | Baseline (Initial) | Architecture V2 (Staggered 2.0R) | Architecture V3 (Multi-Tier Ratchet) |
| :--- | :--- | :--- | :--- |
| **Historical Period** | 12–18 Months (Real MT5 H1) | 12–18 Months (Real MT5 H1) | 12–18 Months (Real MT5 H1) |
| **Total Bars Evaluated** | 43,800 H1 Bars | 43,800 H1 Bars | 43,800 H1 Bars |
| **Total Trades Executed**| 418 trades | 261 trades | 206 trades |
| **Portfolio Win Rate %** | 40.43% | 29.12% | **48.06%** (up to 52.5% on USDJPY) |
| **Max Portfolio Drawdown**| 4.92% | 3.96% | **3.90%** (Robust Capital Preservation) |
| **Catastrophic SL Exits**| 249 (59.6%) | 185 (70.9%) | **97 (47.1%)** (-61% loss events) |
| **Top Edge Strategy** | — | — | **`LIQUIDITY_SWEEP_REVERSAL`** (PF 1.07, +$15.65) |
| **Top Edge Regime** | — | — | **`RANGE`** (PF 1.92, 50.0% Win Rate) |
