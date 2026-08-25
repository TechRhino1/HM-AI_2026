# HM-AI-V7 Adaptive Same-Symbol Risk Engine: 15-Condition Validation Matrix

## Overview
The **Adaptive Same-Symbol Risk Engine** in [`jarvis/risk/risk_engine.py`](file:///C:/xampp/htdocs/HM-Ai-v7/jarvis/risk/risk_engine.py) governs multi-position scaling and pyramiding on the same underlying asset. To prevent over-leveraging, revenge trading, and correlation blowout, a secondary position on the same instrument must satisfy **15 consecutive institutional risk gates**.

---

## 15-Gate Validation Matrix

| Condition # | Gate Name | Threshold / Rule | Institutional Risk Prevented |
| :---: | :--- | :--- | :--- |
| **1** | **Calibrated Win Probability** | $\text{Win Probability} \ge 60.0\%$ | Rejects low-probability or coin-flip scaling entries. |
| **2** | **Expected Value (EV)** | $\text{EV} > \$0.00$ strictly positive | Guarantees positive mathematical expectancy after spread and slippage drag. |
| **3** | **Risk / Reward Ratio** | $\text{R:R} \ge 1:1.50$ minimum | Prevents poor asymmetrical payoff structures. |
| **4** | **Regime Viability & Confidence** | Regime $\ne$ `VOLATILITY_SHOCK` / `EVENT_RISK` and $\text{Confidence} \ge 60\%$ | Prevents adding exposure during regime transitions or news flash shocks. |
| **5** | **Multi-Timeframe Structure Alignment** | Higher Timeframe (H4/D1) Structure matches trade bias | Protects against scaling into macro counter-trend traps. |
| **6** | **Momentum & Trend Score Alignment** | $\text{Trend Score} > 0$ for BUY, $< 0$ for SELL | Ensures positive directional velocity. |
| **7** | **Anti-Averaging Down Guard** | Existing position profit $\ge -\$0.01$ (Cannot be losing) | **Strictly prohibits averaging down on losing trades**; allows only profitable pyramiding. |
| **8** | **Portfolio Risk Budget Capacity** | $\text{Total Projected Risk} \le 2.5\%$ of equity | Enforces strict monetary portfolio drawdown ceiling. |
| **9** | **Margin Utilization Ceiling** | $\text{Margin Utilization} < 40.0\%$ | Prevents margin calls and liquidation cascades. |
| **10** | **Daily & Total Drawdown Guard** | Daily DD within limits ($< 4.0\%$) | Halts all scaling if daily loss threshold is approached. |
| **11** | **Portfolio Heat Constraints** | Heat Score $< 70.0$ (or $< 85.0$ if $\text{Prob} \ge 75\%$) | Prevents multi-asset systemic correlation heat buildup. |
| **12** | **Currency Directional Exposure** | Net currency exposure $\le 2$ simultaneous legs | Protects against hidden single-currency overexposure (e.g. 3x USD long). |
| **13** | **Spread & Slippage Feasibility** | Current spread $\le$ Max allowed symbol spread | Prevents costly execution in wide-spread illiquid windows. |
| **14** | **Session Active & Prime Liquidity** | Prime session (London/NY) or penalty $\le 15.0$ | Blocks off-hours scaling during low-volume Asian/weekend periods. |
| **15** | **Independent Entry Geometry** | $|\text{Entry}_{\text{new}} - \text{Entry}_{\text{old}}| \ge 0.25 \times \text{Risk Distance}$ | Ensures new trade represents an independent structural level rather than a duplicate order. |

---

## Pyramiding vs Averaging Down Rule (Condition 7)
* **Pyramiding (Permitted)**: When Position #1 is in profit (e.g. $+1.0\text{R}$), Position #1's stop loss is ratcheted to Breakeven, and a new distinct breakout setup fires on higher timeframes. Total monetary risk remains neutral or reduced.
* **Averaging Down (Prohibited)**: When Position #1 is in loss/drawdown, adding Position #2 is immediately blocked under `ADAPTIVE_GATE_7_ANTI_AVERAGING_DOWN`.
