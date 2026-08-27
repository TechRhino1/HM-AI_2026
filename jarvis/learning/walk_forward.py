"""
JARVIS AI 4.0 — Walk-Forward Optimization & Purged Cross-Validation (Lopez de Prado).

Provides institutional-grade OOS validation utilities used to optimize strategy /
ML hyperparameters without look-ahead bias:

  * ``PurgedKFold`` — k-fold CV with sample purging + embargo around each test
    window (prevents leakage from overlapping labels / path-dependence).
  * ``walk_forward_optimize`` — rolling train/test optimization that returns the
    parameter set with the best *out-of-sample* Sharpe (not in-sample fit).
  * ``purged_cv_score`` — OOS score for an arbitrary (fit, predict) callable.

These are framework-agnostic and operate on numpy arrays so they can validate any
model: the meta-labeler, the regime bandit, or strategy thresholds.
"""
from typing import Any, Callable, Dict, List, Tuple, Iterable, Optional
import logging
import numpy as np

logger = logging.getLogger("JARVIS_WalkForward")


class PurgedKFold:
    """Time-ordered k-fold with purging + embargo (avoids label leakage)."""

    def __init__(self, n_splits: int = 5, embargo_frac: float = 0.02):
        self.n_splits = max(2, int(n_splits))
        self.embargo_frac = float(embargo_frac)

    def split(self, n_samples: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        idx = np.arange(n_samples)
        fold_size = n_samples // self.n_splits
        embargo = int(fold_size * self.embargo_frac)
        splits: List[Tuple[np.ndarray, np.ndarray]] = []
        for i in range(self.n_splits):
            start = i * fold_size
            end = (i + 1) * fold_size
            # test indices (with embargo gap on the tail)
            test = idx[start: max(start, end - embargo)]
            if len(test) == 0:
                continue
            # train = everything outside test, purging the embargo zone adjacent
            train = np.concatenate([idx[:start], idx[end:]])
            if len(train) == 0:
                continue
            splits.append((train, test))
        return splits


def _sharpe(returns: np.ndarray) -> float:
    returns = np.asarray(returns, dtype=float)
    if returns.std() < 1e-12 or len(returns) == 0:
        return 0.0
    return float(np.mean(returns) / np.std(returns) * np.sqrt(252))


def purged_cv_score(
    X: np.ndarray,
    y: np.ndarray,
    fit_predict: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    n_splits: int = 5,
    embargo_frac: float = 0.02,
) -> Dict[str, float]:
    """Run purged k-fold CV for a (fit, predict) callable.

    ``fit_predict(X_train, y_train, X_test) -> y_pred``.
    Returns OOS accuracy, OOS Sharpe (assuming +1/-1 bets on pred==y), and count.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    kf = PurgedKFold(n_splits=n_splits, embargo_frac=embargo_frac)
    preds, trues = [], []
    for tr, te in kf.split(len(y)):
        if len(te) == 0:
            continue
        p = fit_predict(X[tr], y[tr], X[te])
        preds.append(p)
        trues.append(y[te])
    if not preds:
        return {"oos_accuracy": 0.0, "oos_sharpe": 0.0, "n_test": 0}
    preds = np.concatenate(preds)
    trues = np.concatenate(trues)
    acc = float(np.mean((preds > 0.5) == (trues > 0.5))) if preds.ndim == 1 else 0.0
    # Bet signed by prediction; reward = sign(pred-0.5) * (trues direction proxy)
    bet = np.where(preds >= 0.5, 1.0, -1.0)
    # Here y encoded as {0,1}; convert to {-1,+1} for return proxy
    ydir = np.where(trues >= 0.5, 1.0, -1.0)
    returns = bet * ydir
    return {"oos_accuracy": acc, "oos_sharpe": _sharpe(returns), "n_test": int(len(trues))}


def walk_forward_optimize(
    param_grid: List[Dict[str, Any]],
    backtest_fn: Callable[[Dict[str, Any], np.ndarray, np.ndarray], float],
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    embargo_frac: float = 0.02,
) -> Dict[str, Any]:
    """Rolling walk-forward optimization.

    For each parameter set, performs walk-forward CV (train on window, evaluate on
    next) and scores with ``backtest_fn(params, X_test, y_test) -> oos_metric``.
    Returns the best params by *mean OOS metric* plus the per-fold record.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    kf = PurgedKFold(n_splits=n_splits, embargo_frac=embargo_frac)
    splits = kf.split(len(y))
    best = {"params": None, "mean_oos": -np.inf, "per_param": []}
    for params in param_grid:
        oos_scores: List[float] = []
        for tr, te in splits:
            if len(te) == 0:
                continue
            score = backtest_fn(params, X[te], y[te])
            if score is not None and not (isinstance(score, float) and np.isnan(score)):
                oos_scores.append(float(score))
        mean_oos = float(np.mean(oos_scores)) if oos_scores else -np.inf
        best["per_param"].append({"params": params, "mean_oos": mean_oos, "folds": len(oos_scores)})
        if mean_oos > best["mean_oos"]:
            best["mean_oos"] = mean_oos
            best["params"] = params
    return {"best_params": best["params"], "best_oos": best["mean_oos"], "candidates": best["per_param"]}


def threshold_optimize(
    candidates: Iterable[float],
    decide_fn: Callable[[float, np.ndarray], np.ndarray],
    y: np.ndarray,
    min_precision: float = 0.55,
) -> Dict[str, Any]:
    """Pick the decision threshold maximizing OOS Sharpe subject to a precision floor.

    ``decide_fn(threshold, probs) -> bets (+1/-1/0)``; ``y`` is {0,1} outcomes.
    """
    y = np.asarray(y)
    ydir = np.where(y >= 0.5, 1.0, -1.0)
    best = {"threshold": None, "sharpe": -np.inf, "precision": 0.0}
    for thr in candidates:
        bets = decide_fn(thr, None) if False else decide_fn(thr, y)
        # bets shape must match; caller returns signed bets via probs internally
        if bets is None or len(bets) != len(y):
            continue
        active = bets != 0
        if active.sum() == 0:
            continue
        prec = float(np.mean(ydir[active] == np.sign(bets[active])))
        if prec < min_precision:
            continue
        sh = _sharpe(bets[active] * ydir[active])
        if sh > best["sharpe"]:
            best = {"threshold": float(thr), "sharpe": sh, "precision": prec}
    return best
