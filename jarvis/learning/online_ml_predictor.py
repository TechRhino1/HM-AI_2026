"""
JARVIS AI 4.0 — Online Adaptive Machine Learning Predictor & Meta-Labeler.
Features:
- 24-Dimensional Quantitative & Institutional Feature Extraction
- Online Stochastic Gradient Descent (SGD) with L2 Ridge Regularization
- Return-Weighted Dynamic Learning Step (R-Multiple Scaling)
- Real-Time Rolling Brier Score Tracking & Automated Model Drift Protection
- Institutional Bayesian Prior Initialization (Calibrated Baseline Win Prob ~55-60%)
- Calibrated Probability Clamping in Institutional Domain [0.35, 0.88]
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
from jarvis.data.symbol_registry import resolve as resolve_symbol
from jarvis.market.sessions import SessionEngine

logger = logging.getLogger("JARVIS_OnlineML")

class OnlineMLPredictor:
    """Online Adaptive Machine Learning engine predicting trade success probability."""
    
    FEATURE_NAMES = [
        "momentum_trend_score",       # 1. Normalized trend score (-1.0 to +1.0)
        "adx_strength",              # 2. ADX strength (0.0 to 1.0)
        "rsi_distance",              # 3. RSI distance from neutral 50 (-1.0 to +1.0)
        "rsi_divergence",            # 4. RSI divergence alignment (+1.0, -1.0, 0.0)
        "volatility_atr_ratio",       # 5. ATR ratio relative to expected ATR (-1.0 to 1.5)
        "bollinger_bandwidth",       # 6. Bollinger bandwidth expansion/compression (0.0 to 1.0)
        "spread_friction_ratio",     # 7. Spread cost relative to ATR (0.0 to 1.0)
        "structure_alignment",       # 8. Market structure alignment (+1.0, -1.0)
        "bos_choch_signal",          # 9. BOS/CHoCH structural signal (0.0 to 1.0)
        "discount_premium_alignment",# 10. Discount/Premium zone alignment (+1.0, -1.0, 0.0)
        "liquidity_sweep_alignment", # 11. Liquidity sweep alignment (+1.0, -0.5, 0.0)
        "order_block_fvg_confluence",# 12. OB / FVG presence (0.0 to 1.0)
        "mtf_confluence_score",       # 13. Multi-timeframe confluence (-1.0 to +1.0)
        "session_prime_flag",        # 14. Session prime flag (1.0 London/NY, 0.0 off-hours)
        "killzone_active_flag",      # 15. Institutional killzone active (1.0 or 0.0)
        "regime_trend_alignment",    # 16. Regime trend alignment (+1.0, -0.5, 0.0)
        "regime_volatility_state",   # 17. Regime volatility state (1.0 normal, -0.5 extreme)
        "adversarial_penalty",       # 18. Adversarial threat penalty (0.0 to 1.0)
        "risk_reward_ratio",         # 19. Risk-to-reward ratio normalized (0.0 to 1.0)
        "trade_style_encoding",      # 20. Trade style (1.0 SWING, 0.5 DAY_TRADING, 0.0 SCALP)
        "strategy_type_score",       # 21. Strategy category baseline score (0.0 to 1.0)
        "order_flow_imbalance",      # 22. Order flow delta imbalance (-1.0 to +1.0)
        "vwap_distance_normalized",  # 23. Distance from VWAP in ATR units (-1.0 to +1.0)
        "confluence_master_score"    # 24. Master Confluence Score normalized (0.0 to 1.0)
    ]

    # Institutional prior weights for 24-D feature space
    DEFAULT_WEIGHTS = np.array([
        0.35,   # 1. momentum_trend_score
        0.25,   # 2. adx_strength
        0.15,   # 3. rsi_distance
        0.20,   # 4. rsi_divergence
        -0.15,  # 5. volatility_atr_ratio
        0.10,   # 6. bollinger_bandwidth
        -0.40,  # 7. spread_friction_ratio
        0.35,   # 8. structure_alignment
        0.25,   # 9. bos_choch_signal
        0.20,   # 10. discount_premium_alignment
        0.30,   # 11. liquidity_sweep_alignment
        0.25,   # 12. order_block_fvg_confluence
        0.30,   # 13. mtf_confluence_score
        0.20,   # 14. session_prime_flag
        0.25,   # 15. killzone_active_flag
        0.30,   # 16. regime_trend_alignment
        0.15,   # 17. regime_volatility_state
        -0.35,  # 18. adversarial_penalty
        0.15,   # 19. risk_reward_ratio
        0.10,   # 20. trade_style_encoding
        0.15,   # 21. strategy_type_score
        0.20,   # 22. order_flow_imbalance
        0.10,   # 23. vwap_distance_normalized
        0.25    # 24. confluence_master_score
    ], dtype=float)

    def __init__(self, model_file: str = "jarvis_online_ml_weights.json", learning_rate: float = 0.05, l2_reg: float = 0.01):
        self.model_file = model_file
        self.learning_rate = learning_rate
        self.l2_reg = l2_reg
        self.n_features = len(self.FEATURE_NAMES)
        
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.bias = 0.20  # Baseline log-odds corresponding to ~55-58% win rate
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

    def extract_features(
        self,
        context: MarketContext,
        regime: Optional[RegimeOutput] = None,
        trade_style: str = "SWING",
        strategy: str = "STRUCTURE",
        tentative_bias: Optional[str] = None,
        devil_penalty: float = 0.0,
        target_rr: float = 2.0
    ) -> np.ndarray:
        """
        Extracts full 24-Dimensional stationary quantitative feature vector.
        """
        st = getattr(context, "structure", None)
        mom = getattr(context, "momentum", None)
        vol = getattr(context, "volatility", None)
        ses = getattr(context, "session", None)
        mtf = getattr(context, "mtf_alignment", {}) or {}

        bias = tentative_bias
        if not bias or bias not in ("BUY", "SELL"):
            if st and hasattr(st, "bias") and st.bias in ("BULLISH", "BEARISH"):
                bias = "BUY" if st.bias == "BULLISH" else "SELL"
            elif mom and getattr(mom, "trend_score", 0.0) < 0:
                bias = "SELL"
            else:
                bias = "BUY"

        # 1. Momentum Trend Score (-1.0 to +1.0 aligned with bias)
        raw_trend = (float(getattr(mom, "trend_score", 0.0) or 0.0)) / 100.0
        trend_aligned = raw_trend if bias == "BUY" else (-raw_trend if bias == "SELL" else 0.0)

        # 2. ADX Strength (0.0 to 1.0)
        adx_val = float(getattr(mom, "adx", 20.0) or 20.0)
        adx_norm = min(1.0, max(0.0, (adx_val - 15.0) / 35.0))

        # 3. RSI Distance (-1.0 to +1.0)
        rsi_val = float(getattr(mom, "rsi", 50.0) or 50.0)
        rsi_diff = (rsi_val - 50.0) / 50.0
        rsi_aligned = rsi_diff if bias == "BUY" else (-rsi_diff if bias == "SELL" else 0.0)

        # 4. RSI Divergence (+1.0 aligned, -1.0 opposing, 0.0 none)
        div = str(getattr(mom, "divergence", "NONE") or "NONE").upper()
        if (bias == "BUY" and "BULLISH" in div) or (bias == "SELL" and "BEARISH" in div):
            rsi_div = 1.0
        elif (bias == "BUY" and "BEARISH" in div) or (bias == "SELL" and "BULLISH" in div):
            rsi_div = -1.0
        else:
            rsi_div = 0.0

        # 5. Volatility ATR Ratio (-1.0 to 1.5)
        atr_val = float(getattr(vol, "atr", 0.0) or 0.0)
        curr_price = float(getattr(context, "current_price", 0.0) or 0.0)
        atr_ratio = 1.0
        if atr_val > 0 and curr_price > 0:
            expected_atr = curr_price * 0.005
            atr_ratio = min(2.5, max(0.4, atr_val / expected_atr))
        vol_atr_feat = atr_ratio - 1.0

        # 6. Bollinger Bandwidth (0.0 to 1.0)
        bb_width = float(getattr(vol, "bollinger_bandwidth", 0.05) or 0.05)
        bb_norm = min(1.0, max(0.0, bb_width / 0.10))

        # 7. Spread Friction Ratio (0.0 to 1.0)
        sym_str = getattr(context, "symbol", "EURUSD")
        spec = resolve_symbol(sym_str)
        spr_pips = float(getattr(vol, "current_spread_pips", spec.typical_spread_pips) or spec.typical_spread_pips)
        spread_price = spr_pips * spec.pip_size
        friction = min(1.0, max(0.0, (spread_price / (atr_val + 1e-9)) * 5.0))

        # 8. Structure Alignment (+1.0 aligned, -1.0 opposing)
        st_bias = str(getattr(st, "bias", "NEUTRAL") or "NEUTRAL").upper()
        if st_bias == "BULLISH":
            struct_align = 1.0 if bias == "BUY" else -1.0
        elif st_bias == "BEARISH":
            struct_align = 1.0 if bias == "SELL" else -1.0
        else:
            struct_align = 0.0

        # 9. BOS / CHoCH Signal (0.0 to 1.0)
        has_bos = bool(getattr(st, "bos", False))
        has_choch = bool(getattr(st, "choch", False))
        bos_choch = (0.5 if has_bos else 0.0) + (0.5 if has_choch else 0.0)

        # 10. Discount / Premium Zone Alignment (+1.0 aligned, -1.0 opposing, 0.0 neutral)
        dp_zone = str(getattr(st, "discount_premium_zone", "EQUILIBRIUM") or "EQUILIBRIUM").upper()
        if (bias == "BUY" and dp_zone == "DISCOUNT") or (bias == "SELL" and dp_zone == "PREMIUM"):
            dp_align = 1.0
        elif (bias == "BUY" and dp_zone == "PREMIUM") or (bias == "SELL" and dp_zone == "DISCOUNT"):
            dp_align = -1.0
        else:
            dp_align = 0.0

        # 11. Liquidity Sweep Alignment (+1.0 aligned, -0.5 opposing, 0.0 none)
        liq = getattr(context, "liquidity", None)
        sweep_det = bool(getattr(liq, "sweep_detected", False))
        sweep_type = str(getattr(liq, "sweep_type", "NONE") or "NONE").upper()
        if sweep_det:
            if (bias == "BUY" and "BULLISH" in sweep_type) or (bias == "SELL" and "BEARISH" in sweep_type):
                sweep_align = 1.0
            elif (bias == "BUY" and "BEARISH" in sweep_type) or (bias == "SELL" and "BULLISH" in sweep_type):
                sweep_align = -0.5
            else:
                sweep_align = 0.5
        else:
            sweep_align = 0.0

        # 12. Order Block / FVG Confluence (0.0 to 1.0)
        obs = getattr(st, "order_blocks", []) or []
        fvgs = getattr(st, "fair_value_gaps", []) or []
        has_ob = 1.0 if len(obs) > 0 else 0.0
        has_fvg = 1.0 if len(fvgs) > 0 else 0.0
        ob_fvg_conf = (has_ob + has_fvg) / 2.0

        # 13. MTF Confluence Score (-1.0 to +1.0)
        confluence = 0.0
        h4 = mtf.get("H4", "NEUTRAL") if isinstance(mtf, dict) else "NEUTRAL"
        d1 = mtf.get("D1", "NEUTRAL") if isinstance(mtf, dict) else "NEUTRAL"
        if bias == "BUY":
            confluence += (0.5 if h4 == "BULLISH" else (-0.5 if h4 == "BEARISH" else 0.0))
            confluence += (0.5 if d1 == "BULLISH" else (-0.5 if d1 == "BEARISH" else 0.0))
        elif bias == "SELL":
            confluence += (0.5 if h4 == "BEARISH" else (-0.5 if h4 == "BULLISH" else 0.0))
            confluence += (0.5 if d1 == "BEARISH" else (-0.5 if d1 == "BULLISH" else 0.0))

        # 14. Session Prime Flag (1.0 or 0.0)
        is_prime = 1.0 if getattr(ses, "is_prime_session", False) else 0.0

        # 15. Killzone Active Flag (1.0 or 0.0)
        kz_info = SessionEngine.get_active_killzone(getattr(context, "timestamp", None))
        is_killzone = 1.0 if kz_info.get("is_in_killzone", False) else 0.0

        # 16. Regime Trend Alignment (+1.0 aligned, -0.5 opposing, 0.0 neutral)
        reg_val = "RANGE"
        if regime is not None:
            if hasattr(regime, "primary_regime"):
                reg_val = regime.primary_regime.value if hasattr(regime.primary_regime, "value") else str(regime.primary_regime)
            else:
                reg_val = str(regime)
        reg_val = reg_val.upper()

        if "TREND_BULL" in reg_val:
            reg_align = 1.0 if bias == "BUY" else -0.5
        elif "TREND_BEAR" in reg_val:
            reg_align = 1.0 if bias == "SELL" else -0.5
        elif "BREAKOUT" in reg_val:
            reg_align = 0.5
        else:
            reg_align = 0.0

        # 17. Regime Volatility State (1.0 normal, -0.5 extreme)
        vol_state = str(getattr(vol, "state", "NORMAL") or "NORMAL").upper()
        if vol_state in ("NORMAL", "COMPRESSION"):
            reg_vol_score = 1.0
        elif vol_state in ("EXPANSION",):
            reg_vol_score = 0.5
        else:
            reg_vol_score = -0.5

        # 18. Adversarial Penalty (0.0 to 1.0)
        raw_penalty = float(devil_penalty or 0.0)
        penalty_norm = min(1.0, max(0.0, raw_penalty / 50.0 if raw_penalty > 1.0 else raw_penalty))

        # 19. Risk Reward Ratio Normalized (0.0 to 1.0)
        rr_norm = min(1.0, max(0.0, float(target_rr or 2.0) / 4.0))

        # 20. Trade Style Encoding (1.0 SWING, 0.5 DAY_TRADING, 0.0 SCALP)
        style_norm = str(trade_style or "SWING").upper()
        if "SWING" in style_norm:
            style_feat = 1.0
        elif "DAY" in style_norm or "INTRADAY" in style_norm:
            style_feat = 0.5
        else:
            style_feat = 0.0

        # 21. Strategy Type Baseline Score (0.0 to 1.0)
        strat_str = str(strategy or "STRUCTURE").upper()
        if "REVERSAL" in strat_str or "SWEEP" in strat_str:
            strat_score = 0.75
        elif "TREND" in strat_str or "EXPANSION" in strat_str:
            strat_score = 0.85
        elif "FVG" in strat_str or "SCALP" in strat_str:
            strat_score = 0.65
        else:
            strat_score = 0.50

        # 22. Order Flow Imbalance (-1.0 to +1.0)
        of_data = getattr(context, "order_flow", {}) or {}
        delta = float(of_data.get("delta_imbalance", 0.0) or of_data.get("delta", 0.0) or 0.0)
        of_align = min(1.0, max(-1.0, delta / 100.0 if abs(delta) > 1.0 else delta))
        if bias == "SELL":
            of_align = -of_align

        # 23. VWAP Distance Normalized (-1.0 to +1.0)
        vwap = float(getattr(context, "vwap", 0.0) or 0.0)
        if vwap > 0 and atr_val > 0:
            dist_atr = (curr_price - vwap) / atr_val
            vwap_feat = min(1.0, max(-1.0, dist_atr / 2.0))
        else:
            vwap_feat = 0.0

        # 24. Confluence Master Score (0.0 to 1.0)
        mtf_conf = float(getattr(context, "mtf_confluence_score", 0.0) or 0.0)
        conf_norm = min(1.0, max(0.0, mtf_conf / 100.0 if mtf_conf > 1.0 else mtf_conf))

        features = np.array([
            trend_aligned,
            adx_norm,
            rsi_aligned,
            rsi_div,
            vol_atr_feat,
            bb_norm,
            friction,
            struct_align,
            bos_choch,
            dp_align,
            sweep_align,
            ob_fvg_conf,
            confluence,
            is_prime,
            is_killzone,
            reg_align,
            reg_vol_score,
            penalty_norm,
            rr_norm,
            style_feat,
            strat_score,
            of_align,
            vwap_feat,
            conf_norm
        ], dtype=float)

        return features

    def extract_feature_vector(
        self,
        context: MarketContext,
        regime: Optional[RegimeOutput] = None,
        tentative_bias: str = "BUY",
        devil_penalty: float = 0.0,
        target_rr: float = 2.0,
        trade_style: str = "SWING",
        strategy: str = "STRUCTURE"
    ) -> np.ndarray:
        """Backward-compatible wrapper for 24-D feature extraction."""
        return self.extract_features(
            context=context,
            regime=regime,
            trade_style=trade_style,
            strategy=strategy,
            tentative_bias=tentative_bias,
            devil_penalty=devil_penalty,
            target_rr=target_rr
        )

    def predict_probability(self, features: np.ndarray) -> float:
        """
        Computes calibrated win probability using current online weights.
        Output is strictly calibrated in the institutional domain [0.35, 0.88].
        """
        feat = np.asarray(features, dtype=float)
        if len(feat) == self.n_features:
            z = float(np.dot(self.weights, feat) + self.bias)
        elif len(feat) < self.n_features:
            padded = np.zeros(self.n_features, dtype=float)
            padded[:len(feat)] = feat
            z = float(np.dot(self.weights, padded) + self.bias)
        else:
            z = float(np.dot(self.weights, feat[:self.n_features]) + self.bias)

        prob = self._sigmoid(z)
        return round(float(np.clip(prob, 0.35, 0.88)), 3)

    def predict_win_probability(self, features: np.ndarray) -> float:
        """Alias for predict_probability for backward compatibility."""
        return self.predict_probability(features)

    def update_from_trade_record(self, trade_record: Dict[str, Any]):
        """
        Extracts features and outcome from a closed trade record and triggers online SGD parameter update.
        """
        try:
            is_win = 1 if trade_record.get("is_win", 0) > 0 or trade_record.get("pnl", 0.0) > 0 else 0
            raw_feats = trade_record.get("ml_features")
            r_mult = float(trade_record.get("r_multiple", 1.0) or 1.0)
            if isinstance(raw_feats, str):
                raw_feats = json.loads(raw_feats)
            
            if isinstance(raw_feats, (list, np.ndarray)):
                features = np.array(raw_feats, dtype=float)
                self.update_online(features, is_win, r_multiple=r_mult)
                logger.info(f"Online ML predictor updated from closed trade #{trade_record.get('ticket')}: Win={is_win}, R={r_mult}, BrierScore={self.get_brier_score():.3f}")
        except Exception as e:
            logger.warning(f"Failed to update OnlineMLPredictor from trade record: {e}")

    def update_online(self, features: np.ndarray, target_win: int, r_multiple: float = 1.0):
        """
        Executes online stochastic gradient step after trade completion with return-weighted learning step.
        target_win = 1 if win, 0 if loss.
        r_multiple = realized R-multiple of the trade.
        """
        with self._lock:
            feat = np.asarray(features, dtype=float)
            if len(feat) < self.n_features:
                padded = np.zeros(self.n_features, dtype=float)
                padded[:len(feat)] = feat
                feat = padded
            elif len(feat) > self.n_features:
                feat = feat[:self.n_features]

            pred = self._sigmoid(np.dot(self.weights, feat) + self.bias)
            error = pred - float(target_win)  # Gradient of binary cross-entropy
            
            # Brier score tracking & Automated Model Drift Protection
            self._brier_window.append(error ** 2)
            current_brier = self.get_brier_score()
            if current_brier > 0.28 and len(self._brier_window) >= 15:
                logger.warning(f"⚠️ MODEL DRIFT DETECTED! Rolling Brier score = {current_brier:.3f}. Damping weights to prior baseline.")
                self.weights = np.clip(self.weights * 0.70, -2.0, 2.0)
                self.training_steps = 10

            # Return-weighted learning step: scales gradient by realized R-magnitude
            return_weight = max(0.5, min(3.0, abs(float(r_multiple or 1.0))))
            weighted_error = error * return_weight

            grad_w = (weighted_error * feat) + (self.l2_reg * self.weights)
            self._grad_buffer.append((grad_w, weighted_error))

            if len(self._grad_buffer) >= self._batch_size:
                avg_grad_w = np.mean([g[0] for g in self._grad_buffer], axis=0)
                avg_error = np.mean([g[1] for g in self._grad_buffer])

                # Adaptive learning rate decay
                self.training_steps += 1
                eta = self.learning_rate / np.sqrt(self.training_steps)

                # Update weights & bias
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
                "n_features": int(self.n_features),
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
                    loaded_weights = data.get("weights")
                    if isinstance(loaded_weights, list) and len(loaded_weights) == self.n_features:
                        self.weights = np.array(loaded_weights, dtype=float)
                    else:
                        self.weights = self.DEFAULT_WEIGHTS.copy()
                    self.bias = float(data.get("bias", self.bias))
                    self.training_steps = int(data.get("training_steps", 10))
                    self._feature_importance = np.abs(self.weights).copy()
                except Exception:
                    self.weights = self.DEFAULT_WEIGHTS.copy()
