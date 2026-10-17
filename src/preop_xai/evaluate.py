"""Locked-prediction paired uncertainty; no retraining or test-driven choices."""

import json
from pathlib import Path
from typing import NotRequired, TypedDict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logit
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)

from preop_xai.calibration import probabilities
from preop_xai.preprocessing import LABS
from preop_xai.train import ModelBundle


class CalibrationParameters(TypedDict):
    offset_intercept: float | None
    joint_intercept: float | None
    joint_slope: float | None
    converged: bool


class CalibrationBin(TypedDict):
    n: int
    predicted: float
    observed: float


class ModelEvaluation(TypedDict):
    raw: dict[str, float | None]
    calibrated: dict[str, float | None]
    training_prevalence_brier: float
    raw_calibration: CalibrationParameters
    calibration: CalibrationParameters
    bins: list[CalibrationBin]
    threshold: float
    tp: int
    fp: int
    tn: int
    fn: int
    sensitivity: float | None
    specificity: float | None
    ppv: float | None
    npv: float | None
    f1: float | None
    missing_labs_mean: float


class EvaluationInterval(TypedDict):
    lower: float
    upper: float
    effective_resamples: int
    undefined: int


class EvaluationResult(TypedDict):
    n: int
    events: int
    prevalence: float
    models: dict[str, ModelEvaluation]
    bootstrap_resamples: int
    seed: int
    intervals: NotRequired[dict[str, EvaluationInterval]]
    undefined_resamples: NotRequired[dict[str, int]]


def calibration_parameters(y: np.ndarray, probability: np.ndarray) -> CalibrationParameters:
    """Estimate offset intercept and separate joint intercept/slope by likelihood."""
    if len(np.unique(y)) < 2:
        return {
            "offset_intercept": None,
            "joint_intercept": None,
            "joint_slope": None,
            "converged": False,
        }
    score = logit(np.clip(probability, 1e-12, 1 - 1e-12))

    def offset_loss(theta: np.ndarray) -> float:
        eta = score + theta[0]
        return float(np.sum(np.logaddexp(0, eta) - y * eta))

    def joint_loss(theta: np.ndarray) -> float:
        eta = theta[0] + theta[1] * score
        return float(np.sum(np.logaddexp(0, eta) - y * eta))

    offset = minimize(offset_loss, np.array([0.0]), method="BFGS", tol=1e-6)
    joint = minimize(joint_loss, np.array([0.0, 1.0]), method="BFGS", tol=1e-6)
    return {
        "offset_intercept": float(offset.x[0]),
        "joint_intercept": float(joint.x[0]),
        "joint_slope": float(joint.x[1]),
        "converged": bool(offset.success and joint.success),
    }


def _ranking(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    both = len(np.unique(y)) == 2
    return {
        "auroc": float(roc_auc_score(y, p)) if both else None,
        "average_precision": float(average_precision_score(y, p)) if both else None,
        "brier": float(brier_score_loss(y, p)),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _operating(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float | None]:
    predicted = p >= threshold
    tp = int(np.sum((y == 1) & predicted))
    fp = int(np.sum((y == 0) & predicted))
    tn = int(np.sum((y == 0) & ~predicted))
    fn = int(np.sum((y == 1) & ~predicted))
    return {
        "sensitivity": _ratio(tp, tp + fn),
        "specificity": _ratio(tn, tn + fp),
        "ppv": _ratio(tp, tp + fp),
        "npv": _ratio(tn, tn + fn),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
    }


def evaluate_models(
    bundles: dict[str, ModelBundle],
    X: pd.DataFrame,
    y: pd.Series,
    output: Path,
    bootstraps: int = 1000,
    seed: int = 2026,
) -> EvaluationResult:
    """Evaluate both models on the same held-out patients and bootstrap draws."""
    output.mkdir(parents=True, exist_ok=True)
    y_array = np.asarray(y, dtype=int)
    if not len(y_array) or not np.isin(y_array, [0, 1]).all():
        raise ValueError("Evaluation requires nonempty, complete binary outcomes.")
    results: EvaluationResult = {
        "n": len(y_array),
        "events": int(y_array.sum()),
        "prevalence": float(y_array.mean()),
        "models": {},
        "bootstrap_resamples": bootstraps,
        "seed": seed,
    }
    predictions: dict[str, dict[str, np.ndarray]] = {}
    fig, ax = plt.subplots(figsize=(7, 5), layout="constrained")
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Ideal calibration")
    for name, bundle in bundles.items():
        if bundle.threshold is None:
            raise ValueError("Threshold must be frozen before test evaluation.")
        p = probabilities(bundle, X)
        raw = probabilities(bundle, X, calibrated=False)
        predictions[name] = {"raw": raw, "calibrated": p}
        tn, fp, fn, tp = map(
            int, confusion_matrix(y_array, p >= bundle.threshold, labels=[0, 1]).ravel()
        )
        bins: list[CalibrationBin] = []
        for start, end in zip(np.linspace(0, 1, 6)[:-1], np.linspace(0, 1, 6)[1:], strict=True):
            mask = (p >= start) & ((p < end) if end < 1 else (p <= end))
            if mask.any():
                bins.append(
                    {
                        "n": int(mask.sum()),
                        "predicted": float(p[mask].mean()),
                        "observed": float(y_array[mask].mean()),
                    }
                )
        ax.plot([b["predicted"] for b in bins], [b["observed"] for b in bins], "o-", label=name)
        results["models"][name] = {
            "raw": _ranking(y_array, raw),
            "calibrated": _ranking(y_array, p),
            "training_prevalence_brier": float(
                brier_score_loss(y_array, np.full(len(y_array), bundle.training_prevalence))
            ),
            "raw_calibration": calibration_parameters(y_array, raw),
            "calibration": calibration_parameters(y_array, p),
            "bins": bins,
            "threshold": bundle.threshold,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "sensitivity": _ratio(tp, tp + fn),
            "specificity": _ratio(tn, tn + fp),
            "ppv": _ratio(tp, tp + fp),
            "npv": _ratio(tn, tn + fn),
            "f1": _ratio(2 * tp, 2 * tp + fp + fn),
            "missing_labs_mean": float(X[list(LABS)].isna().sum(axis=1).mean()),
        }
    ax.set(
        xlabel="Mean predicted risk (probability)",
        ylabel="Observed event fraction",
        title="Held-out probability calibration",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    ax.legend()
    fig.savefig(output / "calibration.png", dpi=160)
    plt.close(fig)
    rng = np.random.default_rng(seed)
    samples: dict[str, list[float]] = {}
    undefined: dict[str, int] = {}
    for _ in range(bootstraps):
        index = rng.integers(0, len(y_array), len(y_array))
        values: dict[str, float | None] = {}
        for name, variants in predictions.items():
            for variant, p in variants.items():
                for metric, value in _ranking(y_array[index], p[index]).items():
                    key = f"{name}.{variant}.{metric}"
                    if value is None:
                        undefined[key] = undefined.get(key, 0) + 1
                    else:
                        samples.setdefault(key, []).append(value)
                    values[key] = value
            threshold = bundles[name].threshold
            if threshold is None:
                raise ValueError("Frozen operating threshold is missing.")
            for metric, value in _operating(
                y_array[index], variants["calibrated"][index], threshold
            ).items():
                key = f"{name}.calibrated.{metric}"
                if value is None:
                    undefined[key] = undefined.get(key, 0) + 1
                else:
                    samples.setdefault(key, []).append(value)
        names = list(bundles)
        if len(names) == 2:
            for variant in ("raw", "calibrated"):
                for metric in ("auroc", "average_precision", "brier"):
                    left = values[f"{names[0]}.{variant}.{metric}"]
                    right = values[f"{names[1]}.{variant}.{metric}"]
                    key = f"paired_{names[1]}_minus_{names[0]}.{variant}.{metric}"
                    if left is None or right is None:
                        undefined[key] = undefined.get(key, 0) + 1
                    else:
                        samples.setdefault(key, []).append(right - left)
    results["intervals"] = {
        key: {
            "lower": float(np.quantile(vals, 0.025)),
            "upper": float(np.quantile(vals, 0.975)),
            "effective_resamples": len(vals),
            "undefined": undefined.get(key, 0),
        }
        for key, vals in samples.items()
    }
    results["undefined_resamples"] = undefined
    (output / "metrics.json").write_text(
        json.dumps(results, indent=2, allow_nan=False), encoding="utf-8"
    )
    np.savez_compressed(
        output / "predictions.npz",
        y=y_array,
        names=np.asarray(
            [f"{name}_{variant}" for name, variants in predictions.items() for variant in variants]
        ),
        probabilities=np.stack([p for variants in predictions.values() for p in variants.values()]),
    )
    return results
