"""
JARVIS AI 3.0 — Online Adaptive Machine Learning Predictor.
Features:
- Online Stochastic Gradient Descent (SGD) with L2 Ridge Regularization
- 9-Dimensional Real-Time Quantitative Feature Extraction
- Bayesian Prior Initialization (Prior Win Probability = 0.55)
- Continuous Real-Time Parameter Learning from Closed Trades
"""
import os
import json
import sqlite3
import numpy as np
import threading
import logging
from collections import deque
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from jarvis.data.schemas import MarketContext, RegimeOutput, DecisionObject

class OnlineMLPredictor:
    """Online Adaptive Machine Learning engine predicting trade success probability."""
    
    FEATURE_NAMES = [
        "momentum_trend_score",
        "adx_strength",
        "volatility_atr_ratio",
        "rsi_distance",
        "spread_friction_ratio",
        "adversarial_penalty",
        "structure_alignment",
        "session_prime_flag",
        "mtf_confluence_score"
    ]

    def __init__(self, model_file: str = "jarvis_online_ml_weights.json", learning_rate: float = 0.05, l2_reg: float = 0.01):
        self.model_file = model_file
        self.learning_rate = learning_rate
        self.l2_reg = l2_reg
        self.n_features = len(self.FEATURE_NAMES)
        
        # Initialize weights with institutional baseline priors
        self.weights = np.array([
            0.35,   # momentum_trend_score
            0.25,   # adx_strength
            -0.20,  # volatility_atr_ratio (extreme volatility penalizes slightly)
            0.15,   # rsi_distance
            -0.45,  # spread_friction_ratio (high spread reduces win rate)
            -0.30,  # adversarial_penalty (high devil penalty reduces win rate)
            0.40,   # structure_alignment (BOS/CHoCH alignment strongly positive)
            0.30,   # session_prime_flag (London/NY session bonus)
            0.35    # mtf_confluence_score (Macro alignment bonus)
        ], dtype=float)
        
        self.bias = 0.20  # Log-odds corresponding to ~55% base win rate
        self.training_steps = 10
        self._lock = threading.Lock()
        self._grad_buffer = []
        self._batch_size = 3
        self._feature_importance = np.abs(self.weights).copy()
        self._brier_window = deque(maxlen=50)
        self._load_model()

    def _sigmoid(self, z: float) -> float:
        z_clamped = np.clip(z, -15.0, 15.0)
        return float(1.0 / (1.0 + np.exp(-z_clamped)))

    def extract_feature_vector(
        self,
        context: MarketContext,
        regime: RegimeOutput,
        tentative_bias: str,
        devil_penalty: float = 0.0,
        target_rr: float = 2.0
    ) -> np.ndarray:
        st = context.structure
        mom = context.momentum
        vol = context.volatility
        ses = context.session
        mtf = context.mtf_alignment

        # 1. Momentum Trend Score (-1.0 to +1.0 aligned with trade bias)
        raw_trend = mom.trend_score / 100.0
        trend_aligned = raw_trend if tentative_bias == "BUY" else (-raw_trend if tentative_bias == "SELL" else 0.0)

        # 2. ADX Strength (0.0 to 1.0)
        adx_norm = min(1.0, max(0.0, (mom.adx - 15.0) / 35.0))

        # 3. Volatility ATR Ratio (Normalized around 1.0)
        atr_ratio = 1.0
        if vol.atr > 0 and context.current_price > 0:
            expected_atr = context.current_price * 0.005
            atr_ratio = min(2.5, max(0.4, vol.atr / expected_atr))

        # 4. RSI Distance from Neutral 50 (-1.0 to +1.0)
        rsi_diff = (mom.rsi - 50.0) / 50.0
        rsi_aligned = rsi_diff if tentative_bias == "BUY" else (-rsi_diff if tentative_bias == "SELL" else 0.0)

        # 5. Spread Friction Ratio (0.0 to 1.0)
        friction = min(1.0, max(0.0, vol.current_spread_pips / 10.0))

        # 6. Devil Penalty (0.0 to 1.0)
        penalty_norm = min(1.0, max(0.0, devil_penalty / 50.0))

        # 7. Structure Alignment (+1.0 aligned, -1.0 opposite)
        struct_align = 0.0
        if st.bias == "BULLISH":
            struct_align = 1.0 if tentative_bias == "BUY" else -1.0
        elif st.bias == "BEARISH":
            struct_align = 1.0 if tentative_bias == "SELL" else -1.0
        if st.choch or st.bos:
            struct_align = min(1.0, struct_align + 0.3)

        # 8. Session Prime Flag (1.0 if Prime, 0.0 otherwise)
        is_prime = 1.0 if ses.is_prime_session else 0.0

        # 9. MTF Confluence Score (-1.0 to +1.0)
        confluence = 0.0
        h4 = mtf.get("H4", "NEUTRAL")
        d1 = mtf.get("D1", "NEUTRAL")
        if tentative_bias == "BUY":
            confluence += (0.5 if h4 == "BULLISH" else (-0.5 if h4 == "BEARISH" else 0.0))
            confluence += (0.5 if d1 == "BULLISH" else (-0.5 if d1 == "BEARISH" else 0.0))
        elif tentative_bias == "SELL":
            confluence += (0.5 if h4 == "BEARISH" else (-0.5 if h4 == "BULLISH" else 0.0))
            confluence += (0.5 if d1 == "BEARISH" else (-0.5 if d1 == "BULLISH" else 0.0))

        features = np.array([
            trend_aligned,
            adx_norm,
            atr_ratio - 1.0,
            rsi_aligned,
            friction,
            penalty_norm,
            struct_align,
            is_prime,
            confluence
        ], dtype=float)

        return features

    def predict_win_probability(self, features: np.ndarray) -> float:
        """Computes calibrated win probability using current online weights."""
        z = np.dot(self.weights, features) + self.bias
        prob = self._sigmoid(z)
        return round(float(np.clip(prob, 0.20, 0.88)), 3)

    def update_from_trade_record(self, trade_record: Dict[str, Any]):
        """
        Extracts features and outcome from a closed trade record and triggers online SGD parameter update.
        """
        try:
            is_win = 1 if trade_record.get("is_win", 0) > 0 or trade_record.get("pnl", 0.0) > 0 else 0
            raw_feats = trade_record.get("ml_features")
            if isinstance(raw_feats, str):
                raw_feats = json.loads(raw_feats)
            
            if isinstance(raw_feats, list) and len(raw_feats) == self.n_features:
                features = np.array(raw_feats, dtype=float)
                self.update_online(features, is_win)
                logging.info(f"Online ML predictor updated from closed trade #{trade_record.get('ticket')}: Win={is_win}, BrierScore={self.get_brier_score():.3f}")
        except Exception as e:
            logging.warning(f"Failed to update OnlineMLPredictor from trade record: {e}")

    def update_online(self, features: np.ndarray, target_win: int):
        """
        Executes online stochastic gradient step after trade completion.
        target_win = 1 if win, 0 if loss.
        """
        with self._lock:
            pred = self._sigmoid(np.dot(self.weights, features) + self.bias)
            error = pred - target_win  # Gradient of binary cross-entropy
            
            # Brier score tracking
            self._brier_window.append(error ** 2)
            if self.get_brier_score() > 0.30:
                logging.warning(f"Brier score degraded: {self.get_brier_score():.3f} (worse than random)")

            # Gradient computation
            grad_w = (error * features) + (self.l2_reg * self.weights)
            self._grad_buffer.append((grad_w, error))

            if len(self._grad_buffer) >= self._batch_size:
                avg_grad_w = np.mean([g[0] for g in self._grad_buffer], axis=0)
                avg_error = np.mean([g[1] for g in self._grad_buffer])

                # Adaptive learning rate decay
                self.training_steps += 1
                eta = self.learning_rate / np.sqrt(self.training_steps)

                # Update weights
                self.weights -= eta * avg_grad_w
                self.bias -= eta * avg_error
                
                # Clamp weights
                self.weights = np.clip(self.weights, -3.0, 3.0)
                
                # Update feature importance
                self._feature_importance = np.abs(self.weights).copy()
                
                self._grad_buffer.clear()
                self._save_model_internal()


    def get_feature_importance(self) -> Dict[str, float]:
        """Returns the current absolute weights as feature importance."""
        with self._lock:
            return {name: float(imp) for name, imp in zip(self.FEATURE_NAMES, self._feature_importance)}

    def get_brier_score(self) -> float:
        """Returns the rolling Brier score."""
        if not self._brier_window:
            return 0.0
        return float(np.mean(self._brier_window))

    def _save_model(self):
        with self._lock:
            self._save_model_internal()
            
    def _save_model_internal(self):
        try:
            data = {
                "weights": self.weights.tolist(),
                "bias": float(self.bias),
                "training_steps": int(self.training_steps),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self.model_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_model(self):
        with self._lock:
            if os.path.exists(self.model_file):
                try:
                    with open(self.model_file, "r") as f:
                        data = json.load(f)
                    self.weights = np.array(data["weights"], dtype=float)
                    self.bias = float(data["bias"])
                    self.training_steps = int(data.get("training_steps", 10))
                    self._feature_importance = np.abs(self.weights).copy()
                except Exception:
                    pass
