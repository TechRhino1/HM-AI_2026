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

    def update_calibration_from_history(self, trade_records: List[Dict[str, Any]]) -> None:
        """Updates calibration curve based on actual win rates from historical trades (§17)."""
        if len(trade_records) < 10:
            return

        # Define bins
        bins = [(0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
        bin_stats = {b: {"wins": 0, "total": 0} for b in bins}

        for record in trade_records:
            predicted_prob = float(record.get("model_confidence", record.get("predicted_probability", 0.5)))
            is_win = int(record.get("is_win", 0)) == 1
            
            for b in bins:
                if b[0] <= predicted_prob < b[1]:
                    bin_stats[b]["total"] += 1
                    if is_win:
                        bin_stats[b]["wins"] += 1
                    break
        
        # Update calibration curve for bins with enough data
        for b, stats in bin_stats.items():
            if stats["total"] >= 3:  # Require at least 3 trades per bin to adjust
                actual_win_rate = stats["wins"] / stats["total"]
                # Smooth update (alpha = 0.5)
                old_val = self.calibration_curve.get(b, b[0] + 0.05)
                self.calibration_curve[b] = round(0.5 * old_val + 0.5 * actual_win_rate, 3)
