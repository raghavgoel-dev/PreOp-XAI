"""Deterministic saved prediction fixtures for numerical export tests."""

import hashlib
import json
from typing import TypedDict

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from preop_xai.result_io import Json


class PredictionArrays(TypedDict):
    y: np.ndarray
    names: np.ndarray
    probabilities: np.ndarray


DIAGNOSTIC = {
    "offset_intercept": None,
    "joint_intercept": None,
    "joint_slope": None,
    "converged": False,
    "status": "not-estimable",
}


def saved_evaluation(directory, y=None, raw=None, calibrated=None, status="fitted"):
    """Save small, explicit evaluation arrays with independently calculated source metrics."""
    y = np.array([0, 1, 0, 1]) if y is None else np.asarray(y)
    raw = np.array([0.0, 0.5, 0.5, 1.0]) if raw is None else np.asarray(raw)
    calibrated = raw.copy() if calibrated is None else np.asarray(calibrated)
    available = status in {"fitted", "nonpositive-slope"}

    def ranking(p):
        both = len(np.unique(y)) == 2
        return {
            "auroc": float(roc_auc_score(y, p)) if both else None,
            "average_precision": float(average_precision_score(y, p)) if both else None,
            "brier": float(brier_score_loss(y, p)),
        }

    predicted = calibrated >= 0.5
    tp = int(np.sum((y == 1) & predicted))
    fp = int(np.sum((y == 0) & predicted))
    tn = int(np.sum((y == 0) & ~predicted))
    fn = int(np.sum((y == 1) & ~predicted))

    def ratio(a, b):
        return a / b if b else None

    model: dict[str, Json] = {
        "raw": ranking(raw),
        "calibrated": ranking(calibrated) if available else None,
        "training_prevalence_brier": float(brier_score_loss(y, np.full(len(y), 0.25))),
        "raw_calibration": dict(DIAGNOSTIC),
        "calibration": dict(DIAGNOSTIC) if available else None,
        "threshold": 0.5 if available else None,
        "tp": tp if available else None,
        "fp": fp if available else None,
        "tn": tn if available else None,
        "fn": fn if available else None,
        "sensitivity": ratio(tp, tp + fn) if available else None,
        "specificity": ratio(tn, tn + fp) if available else None,
        "ppv": ratio(tp, tp + fp) if available else None,
        "npv": ratio(tn, tn + fn) if available else None,
        "f1": ratio(2 * tp, 2 * tp + fp + fn) if available else None,
        "calibration_status": status,
        "probability_use": "research-only" if status == "fitted" else "invalid-diagnostic-only",
        "classification_use": "fixed validation operating point; not clinical advice",
    }
    metrics: dict[str, Json] = {
        "n": len(y),
        "events": int(y.sum()),
        "prevalence": float(y.mean()),
        "models": {"lr": model},
        "intervals": {},
    }
    names = ["lr_raw", "lr_calibrated"] if available else ["lr_raw"]
    probabilities = np.stack([raw, calibrated] if available else [raw])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    np.savez(directory / "predictions.npz", y=y, names=names, probabilities=probabilities)
    arrays: PredictionArrays = {"y": y, "names": np.asarray(names), "probabilities": probabilities}
    return metrics, arrays


def replace_metrics(directory, metrics):
    (directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")


def inventory(directory):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.iterdir()
        if path.is_file()
    }
