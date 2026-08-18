# Production-Grade Adaptive AI MT5 Trading System

An institutional-grade, multi-factor adaptive automated trading architecture built for MetaTrader 5 (MT5). The system dynamically detects market regimes, performs multi-timeframe price structure analysis, calculates AI trade scores (0–100), and enforces strict capital preservation rules.

---

## Key Features

1. **Market Regime Classification:** Classifies market state into `STRONG_TREND_BULLISH`, `STRONG_TREND_BEARISH`, `RANGE_BOUND`, `CONSOLIDATION_COMPRESSION`, `BREAKOUT_EXPANSION`, `ACCUMULATION_DISTRIBUTION`, `HIGH_VOLATILITY_SHOCK`, or `UNCLEAR_INDETERMINATE` with calculated confidence %.
2. **Multi-Timeframe Structure Analysis:** Detects Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (Supply/Demand), and Liquidity Pools (Equal Highs/Lows).
3. **Multi-Factor AI Scoring (0–100):** Evaluates Market Structure (20%), Trend Momentum (15%), Multi-Timeframe Alignment (15%), Volatility (10%), Liquidity (10%), News/Fundamental Risk (10%), and Risk-Reward (10%). Requires minimum 75/100 score (85/100 under news risk) for trade execution.
4. **Institutional Risk Manager:** Dynamic position sizing based on account equity and exact pip risk. Enforces `MAX_DAILY_LOSS` (2.0%), `MAX_OPEN_POSITIONS` (3), `MAX_SPREAD` limits, and account drawdown guards.
5. **News Intelligence & Offline Fallback:** Monitors high-impact economic calendar events (FOMC, CPI, NFP) and blocks trades 30 minutes before and after events. If news feeds are offline, it safely defaults to `NEWS_DATA_UNAVAILABLE` and automatically elevates the required trade score threshold.
6. **Active Trade Management:** Automated Break-Even adjustment at 1.5 ATR profit, structure-based Trailing Stops, and emergency exits on opposing regime shifts.
7. **Event-Driven Backtester & Walk-Forward Suite:** Supports bar-by-bar historical backtesting with realistic spread, slippage, and quantitative metrics (Sharpe Ratio, Sortino Ratio, Profit Factor, Max Drawdown).

---

## Architecture Diagram

```
 RAW MARKET DATA (MT5 / OHLCV)
         │
         ▼
 MULTI-TIMEFRAME ENGINE (D1 / H4 / H1 / M15 / M5)
         │
 ┌───────┴──────────────┬───────────────────┬───────────────────┐
 │                      │                   │                   │
 ▼                      ▼                   ▼                   ▼
MARKET STRUCTURE   TREND ENGINE      VOLATILITY ENGINE   LIQUIDITY ENGINE
(BOS, CHoCH, S/D) (EMA, ADX, Slope)   (ATR %, Ratio)    (Sweeps, EQH/EQL)
 └───────┬──────────────┴───────────────────┴───────────────────┘
         │
         ▼
 MARKET REGIME ENGINE  <────  NEWS INTELLIGENCE ENGINE
 (State + Confidence %)        (Calendar + Offline Fallback)
         │
         ▼
 ADAPTIVE STRATEGY SELECTOR
 (Trend Pullback, Range Reversion, Breakout, Liquidity Sweep)
         │
         ▼
 AI DECISION ENGINE (Multi-factor Trade Score 0-100)
         │
         ▼
 INSTITUTIONAL RISK MANAGER (Daily Drawdown, Exposure, Lot Sizing)
         │
         ▼
 MT5 EXECUTION ENGINE (Market Orders, Trailing SL, Telemetry Dashboard)
```

---

## Installation & Setup

1. **Clone/Navigate to Project Folder:**
   ```bash
   cd C:\Users\musu9\.gemini\antigravity\scratch\mt5_adaptive_ai_trader
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Settings:**
   - Edit `config/settings.json` for risk thresholds, magic number, and mode.
   - Edit `config/symbol_profiles.json` for per-symbol spread & ATR parameters.

---

## Execution Options

### 1. Run Unit Tests
Validate risk calculations, regime classification, and AI scoring:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 2. Run Historical Backtest
Run historical backtest on XAUUSD:
```bash
python main.py --symbol XAUUSD --backtest
```

### 3. Run Single Telemetry Sweep (Dry-Run / Simulation Mode)
Inspect current market regime, confidence %, and trade decision:
```bash
python main.py --symbol XAUUSD --once
```

### 4. Run Continuous Automated Loop (Live MT5 Mode)
Ensure MT5 terminal is open and logged into your account:
```bash
python main.py --symbol XAUUSD --mode live
```
