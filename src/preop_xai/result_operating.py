"""Frozen operating-point arithmetic and consistency checks for report exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from preop_xai.result_io import Row

if TYPE_CHECKING:
    from preop_xai.evaluate import ModelEvaluation


def finite_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    return float(value)


def check_metric(actual, expected, label: str) -> None:
    if expected is None:
        if actual is not None:
            raise ValueError(f"{label} disagrees with saved predictions: expected null.")
    elif actual is None or not np.isclose(
        finite_number(actual, label), expected, rtol=1e-9, atol=1e-12
    ):
        raise ValueError(f"{label} disagrees with saved predictions: expected {expected}.")


def check_count(actual, expected, label: str) -> None:
    if type(actual) is not int or actual != expected:
        raise ValueError(f"{label} disagrees with saved predictions: expected integer {expected}.")


def operating_counts(y: np.ndarray, p: np.ndarray, threshold: float) -> Row:
    positive = p >= threshold
    tp = int(np.sum((y == 1) & positive))
    fp = int(np.sum((y == 0) & positive))
    tn = int(np.sum((y == 0) & ~positive))
    fn = int(np.sum((y == 1) & ~positive))

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "sensitivity": ratio(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "ppv": ratio(tp, tp + fp),
        "npv": ratio(tn, tn + fn),
        "accuracy": (tp + tn) / len(y),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "predicted_positives": tp + fp,
        "predicted_positive_fraction": (tp + fp) / len(y),
        "predicted_positives_per_10000": 10000 * (tp + fp) / len(y),
    }


def operating_tables(
    y: np.ndarray, p: np.ndarray, source: ModelEvaluation, identity: Row
) -> tuple[Row, list[Row]]:
    model = identity["model"]
    threshold = finite_number(source.get("threshold"), f"{model}.threshold")
    if not 0 <= threshold <= 1:
        raise ValueError(f"{model}: validation threshold must be in [0, 1].")
    operating = operating_counts(y, p, threshold)
    optional = {
        "accuracy",
        "predicted_positives",
        "predicted_positive_fraction",
        "predicted_positives_per_10000",
    }
    for key, expected in operating.items():
        if key not in source and key in optional:
            continue
        if key in {"tp", "fp", "tn", "fn", "predicted_positives"}:
            check_count(source.get(key), expected, f"{model}.{key}")
        else:
            check_metric(source.get(key), expected, f"{model}.{key}")
    n, events = len(y), int(y.sum())
    row: Row = {
        "endpoint": identity["endpoint"],
        "partition": identity["partition"],
        "model": model,
        "n": n,
        "events": events,
        "nonevents": n - events,
        "threshold": source["threshold"],
        "threshold_source": "validation",
        **operating,
        "calibration_status": source["calibration_status"],
        "classification_use": source["classification_use"],
        "evidence_kind": identity["evidence_kind"],
    }
    confusion: list[Row] = [
        {
            "endpoint": identity["endpoint"],
            "model": model,
            "true_class": true_class,
            "predicted_class": predicted_class,
            "count": operating[key],
            "threshold": source["threshold"],
            "calibration_status": source["calibration_status"],
        }
        for true_class, predicted_class, key in (
            (0, 0, "tn"),
            (0, 1, "fp"),
            (1, 0, "fn"),
            (1, 1, "tp"),
        )
    ]
    return row, confusion
