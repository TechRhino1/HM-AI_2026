"""
JARVIS AI 4.0 — ML Meta-Labeler (Lopez de Prado style).

A secondary model that, given a price-window + intended bias (BUY/SELL), predicts
whether *taking* the primary signal would have been profitable over a forward horizon.
This is the classic meta-labeling pattern: the primary engine decides direction,
the meta-labeler decides *whether to act*. It only blocks trades when confidently
wrong, and is a NO-OP (neutral) until a model has actually been trained, so it can
never degrade an untrained live system.

Features are extracted from a candle window; the model is trained from historical
candles (forward-return labels) and persisted to disk.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
import os
import numpy as np

logger = logging.getLogger("JARVIS_MetaLabeler")

try:
    import joblib
    _HAVE_JOBLIB = True
except Exception:  # pragma: no cover
    _HAVE_JOBLIB = False

from sklearn.ensemble import HistGradientBoostingClassifier


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _window_features(window, bias=0.0):
    """Build a fixed-length feature vector from a candle window.

    window: list of dicts with open/high/low/close/volume (floats).
    bias: +1 for BUY context, -1 for SELL context, 0 unknown.
    Returns None if the window is too short.
    """
    n = len(window)
    if n < 20:
        return None
    try:
        closes = np.array([_safe_float(c.get("close")) for c in window], dtype=float)
        highs = np.array([_safe_float(c.get("high")) for c in window], dtype=float)
        lows = np.array([_safe_float(c.get("low")) for c in window], dtype=float)
        opens = np.array([_safe_float(c.get("open")) for c in window], dtype=float)
        vols = np.array([_safe_float(c.get("volume"), 1.0) for c in window], dtype=float)
    except Exception:
        return None
    if np.any(np.isnan(closes)) or closes[-1] <= 0:
        return None

    last = int(min(20, n))
    recent_c = closes[-last:]
    vol = np.std(np.diff(np.log(recent_c + 1e-9))) if len(recent_c) > 1 else 0.0
    atr = np.mean(np.abs(highs[-last:] - lows[-last:]))
    atr_rel = (atr / (closes[-1] + 1e-9)) if closes[-1] > 0 else 0.0

    trend = (np.mean(closes[-10:]) - np.mean(closes[:10])) / (closes[-1] + 1e-9)

    deltas = np.diff(closes)
    if len(deltas) > 0:
        gain = np.where(deltas > 0, deltas, 0.0)
        loss = np.where(deltas < 0, -deltas, 0.0)
        ag = np.mean(gain[-14:]) if len(gain) >= 14 else np.mean(gain)
        al = np.mean(loss[-14:]) if len(loss) >= 14 else np.mean(loss)
        rsi = 100.0 - (100.0 / (1.0 + (ag / (al + 1e-9))))
    else:
        rsi = 50.0

    body = abs(closes[-1] - opens[-1]) / (closes[-1] + 1e-9)
    rng = (highs[-1] - lows[-1]) / (closes[-1] + 1e-9 + 1e-9)
    up_sh = (highs[-1] - max(opens[-1], closes[-1])) / (closes[-1] + 1e-9 + 1e-9)
    dn_sh = (min(opens[-1], closes[-1]) - lows[-1]) / (closes[-1] + 1e-9 + 1e-9)

    vavg = np.mean(vols[-last:]) if vols[-1] > 0 else 1.0
    vratio = (vols[-1] / (vavg + 1e-9)) if vavg > 0 else 1.0

    hi20 = np.max(highs[-last:])
    lo20 = np.min(lows[-last:])
    pos = (closes[-1] - lo20) / (hi20 - lo20 + 1e-9)

    up_closes = np.sum(deltas > 0)
    frac_up = up_closes / (len(deltas) + 1e-9)

    feat = [
        closes[-1] / (closes[0] + 1e-9) - 1.0,
        vol,
        atr_rel,
        trend,
        rsi / 100.0,
        body, rng, up_sh, dn_sh,
        vratio,
        pos,
        frac_up,
        bias,
    ]
    return np.array(feat, dtype=float)


class MetaLabeler:
    MIN_WINDOW = 30
    MIN_PROB = 0.55  # gate threshold; below this the meta-labeler distrusts the setup

    def __init__(self, model_path=None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "jarvis_data", "meta_labeler.joblib"
        )
        self.model = None
        self._load()

    def build_dataset(self, candles, horizon=20, label_frac=0.5):
        """Create (X, y) from a candle series.

        For each bar i we emit two samples (bias=+1 long, bias=-1 short) labeled by
        whether the forward move in that direction exceeds ~half-ATR (a profitable
        move net of spread/cost)."""
        X, y = [], []
        n = len(candles)
        if n < self.MIN_WINDOW + horizon + 1:
            return np.empty((0, 14)), np.empty((0,))
        for i in range(self.MIN_WINDOW - 1, n - horizon):
            window = candles[i - self.MIN_WINDOW + 1: i + 1]
            atr = np.mean(np.abs(
                np.array([_safe_float(candles[k].get("high")) for k in range(i - self.MIN_WINDOW + 1, i + 1)], dtype=float)
                - np.array([_safe_float(candles[k].get("low")) for k in range(i - self.MIN_WINDOW + 1, i + 1)], dtype=float)
            ))
            thr = max(atr * label_frac, 1e-9)
            fwd = _safe_float(candles[i + horizon].get("close")) - _safe_float(candles[i].get("close"))
            f_long = _window_features(window, bias=1.0)
            if f_long is not None:
                X.append(f_long)
                y.append(1 if fwd > thr else 0)
            f_short = _window_features(window, bias=-1.0)
            if f_short is not None:
                X.append(f_short)
                y.append(1 if -fwd > thr else 0)
        return np.array(X, dtype=float), np.array(y, dtype=int)

    def train(self, candles, horizon=20, label_frac=0.5):
        X, y = self.build_dataset(candles, horizon=horizon, label_frac=label_frac)
        if X.shape[0] < 50 or len(set(y.tolist())) < 2:
            logger.warning("MetaLabeler: insufficient/label-degenerate data (%d samples); skipping train.", X.shape[0])
            return False
        self.model = HistGradientBoostingClassifier(
            max_depth=4, learning_rate=0.05, max_iter=300, l2_regularization=1.0, random_state=42
        )
        self.model.fit(X, y)
        self._save()
        logger.info("MetaLabeler trained on %d samples (pos=%.1f%%)", X.shape[0], 100.0 * np.mean(y))
        return True

    def predict_proba(self, window, bias=0.0):
        """Return P(profitable) for the given window + bias, or None if untrained."""
        if self.model is None:
            return None
        feat = _window_features(window, bias=bias)
        if feat is None:
            return None
        try:
            proba = self.model.predict_proba(feat.reshape(1, -1))[0]
            if hasattr(self.model, "classes_"):
                idx = list(self.model.classes_).index(1)
                return float(proba[idx])
            return float(proba[1])
        except Exception as e:  # pragma: no cover
            logger.error("MetaLabeler predict error: %s", e)
            return None

    def _load(self):
        if _HAVE_JOBLIB and self.model_path and os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info("MetaLabeler model loaded from %s", self.model_path)
            except Exception as e:  # pragma: no cover
                logger.warning("MetaLabeler load failed: %s", e)
                self.model = None

    def _save(self):
        if _HAVE_JOBLIB and self.model is not None:
            try:
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                joblib.dump(self.model, self.model_path)
            except Exception as e:  # pragma: no cover
                logger.warning("MetaLabeler save failed: %s", e)
