"""Ranking checks and complete ROC/PR coordinates from saved probabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from preop_xai.result_io import Row
from preop_xai.result_operating import check_metric, finite_number

if TYPE_CHECKING:
    from preop_xai.evaluate import CalibrationParameters, ModelEvaluation


def ranking_row(
    y: np.ndarray, p: np.ndarray, source: ModelEvaluation, identity: Row
) -> tuple[Row, CalibrationParameters]:
    variant = identity["variant"]
    name = f"{identity['model']}_{variant}"
    ranking = source.get("raw") if variant == "raw" else source["calibrated"]
    if not isinstance(ranking, dict):
        raise ValueError(f"{name}: ranking metrics are required.")
    both_classes = len(np.unique(y)) == 2
    expected_scores = {
        "auroc": float(roc_auc_score(y, p)) if both_classes else None,
        "average_precision": float(average_precision_score(y, p)) if both_classes else None,
        "brier": float(brier_score_loss(y, p)),
    }
    for metric, expected in expected_scores.items():
        check_metric(ranking.get(metric), expected, f"{name}.{metric}")
    diagnostic = source.get("raw_calibration") if variant == "raw" else source["calibration"]
    if not isinstance(diagnostic, dict) or not isinstance(diagnostic.get("status"), str):
        raise ValueError(f"{name}: calibration diagnostic status is required.")
    for value, key in (
        (diagnostic["offset_intercept"], "offset_intercept"),
        (diagnostic["joint_intercept"], "joint_intercept"),
        (diagnostic["joint_slope"], "joint_slope"),
    ):
        if value is not None:
            finite_number(value, f"{name}.{key}")
    status = source["calibration_status"]
    use = "raw-research-only" if variant == "raw" else source.get("probability_use")
    if variant == "calibrated" and use != (
        "research-only" if status == "fitted" else "invalid-diagnostic-only"
    ):
        raise ValueError(f"{name}: probability_use disagrees with calibration status.")
    training_brier = finite_number(
        source.get("training_prevalence_brier"), f"{identity['model']}.training_prevalence_brier"
    )
    if not 0 <= training_brier <= 1:
        raise ValueError(f"{name}: training_prevalence_brier must be in [0, 1].")
    n, events = len(y), int(y.sum())
    prevalence = events / n
    row: Row = {
        "endpoint": identity["endpoint"],
        "partition": identity["partition"],
        "model": identity["model"],
        "variant": variant,
        "n": n,
        "events": events,
        "nonevents": n - events,
        "prevalence": prevalence,
        **{key: ranking[key] for key in expected_scores},
        "training_prevalence_brier": source["training_prevalence_brier"],
        "test_prevalence_brier_reference": prevalence * (1 - prevalence),
        "offset_intercept": diagnostic["offset_intercept"],
        "joint_intercept": diagnostic["joint_intercept"],
        "joint_slope": diagnostic["joint_slope"],
        "calibration_diagnostic_status": diagnostic["status"],
        "calibration_status": status,
        "probability_use": use,
        "evidence_kind": identity["evidence_kind"],
    }
    return row, diagnostic


def curve_tables(
    y: np.ndarray, p: np.ndarray, identity: Row
) -> tuple[list[Row], list[Row], list[Row]]:
    if len(np.unique(y)) != 2:
        unavailable = [
            {**identity, "artifact": artifact, "reason": "single-class"}
            for artifact in ("roc_points.csv", "pr_points.csv")
        ]
        return [], [], unavailable
    fpr, tpr, thresholds = roc_curve(y, p, drop_intermediate=False)
    roc: list[Row] = [
        {
            **identity,
            "point_index": index,
            "fpr": float(x),
            "tpr": float(z),
            "threshold": None if np.isposinf(threshold) else float(threshold),
            "threshold_kind": "positive_infinity" if np.isposinf(threshold) else "finite",
        }
        for index, (x, z, threshold) in enumerate(zip(fpr, tpr, thresholds, strict=True))
    ]
    precision, recall, thresholds = precision_recall_curve(y, p)
    pr: list[Row] = [
        {
            **identity,
            "point_index": index,
            "recall": float(x),
            "precision": float(z),
            "threshold": None if index == len(thresholds) else float(thresholds[index]),
            "threshold_kind": "none" if index == len(thresholds) else "finite",
        }
        for index, (x, z) in enumerate(zip(recall, precision, strict=True))
    ]
    return roc, pr, []
