"""
JARVIS AI 3.0 — Confidence Calibration Engine.
Calibrates model confidence against historical win rates using reliability curves to eliminate overconfidence.
"""
from typing import Dict, List, Any
import numpy as np

class ConfidenceCalibrationEngine:
    def __init__(self):
        # Default historical calibration mapping: raw confidence bin -> calibrated true probability
        self.calibration_curve = {
            (0.50, 0.60): 0.53,
            (0.60, 0.70): 0.62,
            (0.70, 0.80): 0.71,
            (0.80, 0.90): 0.79,
            (0.90, 1.00): 0.84
        }

    def calibrate_probability(self, raw_confidence: float) -> float:
        """Applies empirical calibration curve to adjust for overconfidence."""
        raw_confidence = min(1.0, max(0.0, raw_confidence))
        for (low, high), true_prob in self.calibration_curve.items():
            if low <= raw_confidence < high:
                # Linear interpolation within the bin
                bin_span = high - low
                frac = (raw_confidence - low) / bin_span
                next_val = true_prob + (frac * (high - low) * 0.8)
                return round(float(next_val), 3)
        return round(raw_confidence * 0.85, 3)

    def compute_brier_score(self, predictions: List[float], outcomes: List[int]) -> float:
        """Calculates Brier Score (lower is better, 0.0 is perfect calibration)."""
        if not predictions or len(predictions) != len(outcomes):
            return 0.25
        preds = np.array(predictions)
        outs = np.array(outcomes)
        return float(np.mean((preds - outs) ** 2))
