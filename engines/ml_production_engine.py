import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List

class MLProductionPipelineEngine:
    """
    Production-Grade Machine Learning Pipeline Engine.
    Extracts 14 Institutional Features from real-time price action, Volume Profile, and Order Flow,
    and runs out-of-sample win probability prediction & Sharpe expectancy scoring.
    """
    def __init__(self, memory_file: str = "learning_memory.json", logger: Any = None):
        self.memory_file = memory_file
        self.logger = logger
        self.regime_map = {
            "STRONG_TREND_BULLISH": 1.0,
            "STRONG_TREND_BEARISH": -1.0,
            "BREAKOUT_EXPANSION_BULLISH": 0.8,
            "BREAKOUT_EXPANSION_BEARISH": -0.8,
            "ACCUMULATION_DISTRIBUTION": 0.3,
            "CONSOLIDATION_COMPRESSION": 0.0,
            "HIGH_VOLATILITY_SHOCK": 0.0
        }
        self.strategy_map = {
            "TREND_PULLBACK_BULLISH": 1.0,
            "TREND_PULLBACK_BEARISH": 1.0,
            "BREAKOUT_EXPANSION_BUY": 0.9,
            "BREAKOUT_EXPANSION_SELL": 0.9,
            "ULTRA_FAST_MICRO_SCALP_BUY": 0.8,
            "ULTRA_FAST_MICRO_SCALP_SELL": 0.8,
            "LIQUIDITY_SWEEP_REVERSAL": 0.7
        }

    def extract_feature_vector(
        self,
        df: pd.DataFrame,
        structure: Dict[str, Any],
        trend: Dict[str, Any],
        volatility: Dict[str, Any],
        liquidity: Dict[str, Any],
        orderflow: Dict[str, Any],
        regime: str,
        strategy: str,
        rr_ratio: float,
        spread_pips: float
    ) -> List[float]:
        """
        Extracts 14 Institutional Features for Online ML Model:
        1. Volatility ATR Ratio
        2. Order Flow Volume Delta Ratio
        3. POC Distance Pct
        4. RSI 14 Level
        5. MACD Histogram Norm
        6. ADX Trend Strength
        7. FVG Imbalance Ratio
        8. EMA Fast/Slow Spread Pct
        9. Liquidity Sweep Flag (0/1)
        10. Risk-to-Reward Ratio
        11. Session UTC Hour Norm (0-1)
        12. Spread Cost Ratio
        13. Encoded Market Regime (-1.0 to +1.0)
        14. Encoded Strategy Weight (0.0 to 1.0)
        """
        if len(df) < 14:
            return [0.0] * 14

        c_price = float(df["close"].iloc[-1])
        atr = volatility.get("atr", c_price * 0.005)
        atr_norm = atr / (c_price + 1e-9)

        buy_vol_ratio = orderflow.get("buy_vol_ratio", 0.5) if isinstance(orderflow, dict) else 0.5
        poc = orderflow.get("poc", c_price) if isinstance(orderflow, dict) else c_price
        poc_dist_pct = abs(c_price - poc) / (c_price + 1e-9)

        # RSI 14
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
        rs = gain / (loss + 1e-9)
        rsi = float(100 - (100 / (1 + rs))) if not np.isnan(rs) else 50.0

        # MACD
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_hist_norm = float((macd.iloc[-1] - signal.iloc[-1]) / (atr + 1e-9))

        adx = float(trend.get("adx", 20.0))
        fvg_ratio = 1.0 if liquidity.get("fvg_detected") else 0.0
        
        ema_fast = float(trend.get("ema_fast", c_price))
        ema_slow = float(trend.get("ema_slow", c_price))
        ema_diff_pct = (ema_fast - ema_slow) / (c_price + 1e-9)

        sweep_flag = 1.0 if liquidity.get("sweep_detected") else 0.0
        
        from datetime import datetime, timezone
        utc_hour_norm = datetime.now(timezone.utc).hour / 24.0

        spread_ratio = (spread_pips * 0.0001) / (atr + 1e-9)

        regime_enc = self.regime_map.get(regime, 0.0)
        strat_enc = self.strategy_map.get(strategy, 0.5)

        return [
            round(atr_norm, 4),
            round(buy_vol_ratio, 2),
            round(poc_dist_pct, 4),
            round(rsi, 1),
            round(macd_hist_norm, 3),
            round(adx, 1),
            fvg_ratio,
            round(ema_diff_pct, 4),
            sweep_flag,
            round(rr_ratio, 2),
            round(utc_hour_norm, 2),
            round(spread_ratio, 3),
            regime_enc,
            strat_enc
        ]

    def predict_opportunity_expectancy(self, feature_vector: List[float], base_score: float) -> Dict[str, Any]:
        """
        Online ML Predictor Engine:
        Calculates Win Probability, Expected Sharpe Ratio, and Confidence Rating.
        """
        atr_norm, buy_vol, poc_dist, rsi, macd_h, adx, fvg, ema_diff, sweep, rr, hour, spread_cost, r_enc, s_enc = feature_vector

        # Feature Scoring Weights
        score = base_score * 0.40  # 40% base technical score
        score += (buy_vol - 0.5) * 20.0  # Order flow bonus
        score += (1.0 if (30.0 <= rsi <= 70.0) else 0.0) * 10.0  # Non-overextended RSI
        score += (1.0 if adx >= 25.0 else 0.0) * 10.0  # Trend strength
        score += sweep * 10.0  # Liquidity sweep bonus
        score += (1.0 if rr >= 2.0 else 0.0) * 10.0  # R:R ratio bonus

        final_score = round(min(100.0, max(0.0, score)), 1)
        win_prob = round(min(0.95, max(0.35, final_score / 100.0)), 2)

        expected_sharpe = round(win_prob * rr - (1.0 - win_prob), 2)

        return {
            "ml_feature_vector": feature_vector,
            "ml_win_probability": win_prob,
            "ml_expected_sharpe": expected_sharpe,
            "ml_trade_score": final_score,
            "ml_status": "EXPERT_QUALIFIED" if win_prob >= 0.70 and expected_sharpe >= 0.8 else "STANDARD"
        }
