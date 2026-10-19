"""Paired fixed-parameter bootstrap stability of raw-model SHAP explanations."""

from __future__ import annotations

import copy
import warnings
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import NotRequired, TypedDict

import numpy as np
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning

from .explain import (
    _background,
    _explain_raw,
    _model_key,
    _private_directory,
    _save_private,
    _validate_features,
    _write_json,
)
from .preprocessing import FEATURES


class StabilityPair(TypedDict):
    first_successful_refit: int
    second_successful_refit: int
    spearman: float | None
    top5_jaccard: float


class StabilitySummary(TypedDict):
    pairwise: list[StabilityPair]
    spearman_mean: float | None
    spearman_defined_pairs: int
    spearman_undefined_pairs: int
    top5_jaccard_mean: float | None
    top5_tie_rule: str
    top5_inclusion_frequency: dict[str, float]
    mean_absolute_importance: dict[str, float]
    centered_contribution_rms_mean_over_patients: dict[str, float]
    centering: str
    baseline_mean_by_successful_refit: list[float]
    baseline_shift_rms: float
    status: NotRequired[str]
    successful_refits: NotRequired[int]


class InsufficientStability(TypedDict):
    status: str
    successful_refits: int


class StabilityResult(TypedDict):
    seed: int
    requested_refits: int
    validation_n: int
    background_n: int
    paired_draws: bool
    scale: str
    background_convention: str
    grouping: str
    models: dict[str, StabilitySummary | InsufficientStability]
    limitations: list[str]
    single_class_draws: NotRequired[list[int]]
    failures: NotRequired[list[str]]
    successful_paired_draws: NotRequired[list[int]]


def _rank_correlation(first, second) -> float | None:
    """A constant importance vector has no defined rank correlation."""
    first, second = np.asarray(first), np.asarray(second)
    if np.ptp(first) == 0 or np.ptp(second) == 0:
        return None
    value = float(np.asarray(spearmanr(first, second), dtype=float).reshape(-1)[0])
    return value if np.isfinite(value) else None


def _top_five(importance: np.ndarray) -> set[int]:
    # Stable schema-order tie rule is shared by every refit and model.
    return set(np.argsort(-importance, kind="stable")[: min(5, len(importance))])


def _mean_defined(values: Iterable[float | None]) -> float | None:
    defined = [value for value in values if value is not None]
    return float(np.mean(defined)) if defined else None


def _summarize(contributions: np.ndarray, baselines: np.ndarray) -> StabilitySummary:
    importance = np.abs(contributions).mean(axis=1)
    top_sets = [_top_five(row) for row in importance]
    correlations: list[float | None] = []
    jaccards: list[float] = []
    pairs: list[StabilityPair] = []
    for first, second in combinations(range(len(importance)), 2):
        correlation = _rank_correlation(importance[first], importance[second])
        jaccard = len(top_sets[first] & top_sets[second]) / len(top_sets[first] | top_sets[second])
        correlations.append(correlation)
        jaccards.append(jaccard)
        pairs.append(
            {
                "first_successful_refit": first,
                "second_successful_refit": second,
                "spearman": correlation,
                "top5_jaccard": jaccard,
            }
        )

    # Center each patient's contribution across refits. Baseline differences
    # are not assigned to clinical features and are reported independently.
    centered = contributions - contributions.mean(axis=0, keepdims=True)
    variability = np.sqrt(np.mean(centered**2, axis=0))
    baseline_shifts = baselines - baselines.mean(axis=0, keepdims=True)
    return {
        "pairwise": pairs,
        "spearman_mean": _mean_defined(correlations),
        "spearman_defined_pairs": sum(v is not None for v in correlations),
        "spearman_undefined_pairs": sum(v is None for v in correlations),
        "top5_jaccard_mean": _mean_defined(jaccards),
        "top5_tie_rule": "clinical schema order",
        "top5_inclusion_frequency": {
            feature: float(np.mean([i in top for top in top_sets]))
            for i, feature in enumerate(FEATURES)
        },
        "mean_absolute_importance": dict(
            zip(FEATURES, importance.mean(axis=0).tolist(), strict=True)
        ),
        "centered_contribution_rms_mean_over_patients": dict(
            zip(FEATURES, variability.mean(axis=0).tolist(), strict=True)
        ),
        "centering": "subtract each validation patient's across-refit mean contribution",
        "baseline_mean_by_successful_refit": baselines.mean(axis=1).tolist(),
        "baseline_shift_rms": float(np.sqrt(np.mean(baseline_shifts**2))),
    }


def run_stability(
    bundles, X_train, y_train, X_validation, output: Path, refits=10, seed=2026
) -> StabilityResult:
    """Refit cloned pipelines on paired patient draws; never retune or recalibrate.

    Input rows must represent distinct indexed patients. Identity fields are
    deliberately excluded from feature matrices and from aggregate artifacts.
    """
    _validate_features(X_train)
    _validate_features(X_validation)
    y = np.asarray(y_train)
    if y.shape != (len(X_train),) or not np.isin(y, [0, 1]).all():
        raise ValueError("Training labels must be complete binary labels.")
    if not isinstance(refits, int) or refits < 2:
        raise ValueError("At least two bootstrap refits are required.")
    if not bundles:
        raise ValueError("At least one model bundle is required.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    private = _private_directory(output)
    background, background_positions = _background(X_train, seed)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(X_train), size=(refits, len(X_train)))
    _save_private(
        private / "stability_draws.npz",
        draws=draws,
        background_positions=background_positions,
    )
    result: StabilityResult = {
        "seed": seed,
        "requested_refits": refits,
        "validation_n": len(X_validation),
        "background_n": len(background),
        "paired_draws": True,
        "scale": "raw model log-odds; calibrator uncertainty excluded",
        "background_convention": "same original raw training rows, transformed by each refit",
        "grouping": "clinical concepts including their missingness contributions",
        "models": {},
        "limitations": [
            "Exploratory bootstrap stability, not a confidence interval for clinical effects.",
            "Rows must be distinct indexed training patients.",
            "Fixed validation patients and original background are not resampled.",
            "No retuning, recalibration or threshold selection is performed.",
        ],
    }
    # Single-class samples are excluded for BOTH models to preserve pairing.
    eligible = [i for i, draw in enumerate(draws) if len(np.unique(y[draw])) == 2]
    result["single_class_draws"] = [i for i in range(refits) if i not in eligible]

    # A failure for either model excludes that draw for both summaries.
    collected: dict[str, dict[int, tuple[np.ndarray, np.ndarray]]] = {
        _model_key(key): {} for key in bundles
    }
    failures: list[str] = []
    for index in eligible:
        draw_results: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for key, bundle in bundles.items():
            candidate = copy.copy(bundle)
            candidate.pipeline = clone(bundle.pipeline)
            candidate.calibrator = None
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                candidate.pipeline.fit(X_train.iloc[draws[index]], y[draws[index]])
            data = _explain_raw(candidate, background, X_validation)
            draw_results[key] = (data["grouped"], data["baseline"])
        if len(draw_results) == len(bundles):
            for key, data in draw_results.items():
                collected[key][index] = data

    result["failures"] = failures
    successful = sorted(next(iter(collected.values())))
    result["successful_paired_draws"] = successful
    for key, values in collected.items():
        if len(successful) < 2:
            result["models"][key] = {
                "status": "insufficient_successful_paired_refits",
                "successful_refits": len(successful),
            }
            continue
        contributions = np.stack([values[i][0] for i in successful])
        baselines = np.stack([values[i][1] for i in successful])
        summary = _summarize(contributions, baselines)
        summary["status"] = "complete" if len(successful) == refits else "partial"
        summary["successful_refits"] = len(successful)
        result["models"][key] = summary
        _save_private(
            private / f"{key}_stability.npz",
            successful_draws=np.asarray(successful),
            grouped_contributions=contributions,
            baselines=baselines,
            centered_contributions=contributions - contributions.mean(axis=0, keepdims=True),
            baseline_shifts=baselines - baselines.mean(axis=0, keepdims=True),
        )
    _write_json(output / "stability.json", result)
    return result
