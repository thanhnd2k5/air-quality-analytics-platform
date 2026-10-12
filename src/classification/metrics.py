"""Evaluation for the alert classifier: confusion matrix first, never accuracy alone."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import chi2
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(y_true, y_pred, proba=None) -> dict[str, Any]:
    """Confusion-matrix counts plus accuracy / precision / recall / F1 (+ AUCs if proba)."""
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(yt, yp, labels=[0, 1]).ravel()
    out: dict[str, Any] = {
        "n": int(len(yt)),
        "positives": int(yt.sum()),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "accuracy": float((tp + tn) / len(yt)) if len(yt) else float("nan"),
        "precision": float(precision_score(yt, yp, zero_division=0)),
        "recall": float(recall_score(yt, yp, zero_division=0)),
        "f1": float(f1_score(yt, yp, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if (tn + fp) else float("nan"),
        "roc_auc": None,
        "pr_auc": None,
    }
    if proba is not None and len(np.unique(yt)) == 2:
        p = np.asarray(proba, dtype=float)
        out["roc_auc"] = float(roc_auc_score(yt, p))
        out["pr_auc"] = float(average_precision_score(yt, p))
    return out


def onset_recall(pm25_t, y_true, y_pred, threshold: float) -> dict[str, Any]:
    """Recall on alert *onsets*: hours that are clean now (PM2.5(t) < threshold) but
    exceed the threshold at the target time. Persistence scores 0 here by construction.
    """
    pm = np.asarray(pm25_t, dtype=float)
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)
    onset = (pm < threshold) & (yt == 1)
    n = int(onset.sum())
    hit = int((yp[onset] == 1).sum()) if n else 0
    return {"onsets": n, "detected": hit, "recall": float(hit / n) if n else float("nan")}


def mcnemar(y_true, pred_a, pred_b) -> dict[str, Any]:
    """McNemar test (continuity corrected) for two classifiers on the same rows.

    b = A right & B wrong, c = A wrong & B right. Small p → the error rates differ.
    """
    yt = np.asarray(y_true, dtype=int)
    a_ok = np.asarray(pred_a, dtype=int) == yt
    b_ok = np.asarray(pred_b, dtype=int) == yt
    b = int((a_ok & ~b_ok).sum())
    c = int((~a_ok & b_ok).sum())
    if b + c == 0:
        return {"b": b, "c": c, "statistic": 0.0, "p_value": 1.0}
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    return {"b": b, "c": c, "statistic": float(stat), "p_value": float(chi2.sf(stat, df=1))}


def threshold_curve(y_true, proba, grid) -> list[dict[str, float]]:
    """Precision / recall / F1 of ``proba >= t`` for every t in grid."""
    yt = np.asarray(y_true, dtype=int)
    p = np.asarray(proba, dtype=float)
    rows = []
    for t in grid:
        yp = (p >= t).astype(int)
        rows.append(
            {
                "threshold": float(t),
                "precision": float(precision_score(yt, yp, zero_division=0)),
                "recall": float(recall_score(yt, yp, zero_division=0)),
                "f1": float(f1_score(yt, yp, zero_division=0)),
            }
        )
    return rows
