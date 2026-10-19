"""Interventional SHAP explanations on raw and calibrated log-odds scales."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import NotRequired, TypedDict, TypeVar

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from scipy.special import expit
from shap.maskers import Independent

from .calibration import calibration_status, probabilities, raw_scores
from .preprocessing import FEATURES


class RawExplanation(TypedDict):
    values: np.ndarray
    baseline: np.ndarray
    scores: np.ndarray
    names: list[str]
    groups: list[str]
    missing: np.ndarray
    transformed: np.ndarray
    grouped: np.ndarray


class ExplanationCalibration(TypedDict):
    intercept: float | None
    slope: float | None
    fitted: bool
    status: str
    use: str


class LocalGroup(TypedDict):
    n: int
    status: str
    selection_rule: NotRequired[str]
    figure: NotRequired[str]


class DependenceLookup(TypedDict):
    status: str
    rule: str
    transformed_feature: NotRequired[str]


class ExplanationSummary(TypedDict):
    raw_additivity: bool
    calibrated_logit_additivity: bool | None
    calibration: ExplanationCalibration
    clinical_features: list[str]
    global_mean_absolute_raw: dict[str, float]
    global_mean_absolute_calibrated: dict[str, float] | None
    missingness_mean_absolute_raw: dict[str, float]
    transformed_mean_absolute_raw: dict[str, float]
    baseline_raw_mean: float
    baseline_calibrated_mean: float | None
    local_groups: dict[str, LocalGroup]
    dependence_lookup: dict[str, DependenceLookup]


class ExplanationResult(TypedDict):
    seed: int
    n_explained: int
    background_n: int
    shap_version: str
    dependence_assumption: str
    scale: str
    models: dict[str, ExplanationSummary]
    figures: list[str]
    private_figures: list[str]


_JsonValue = TypeVar("_JsonValue")


def _write_json(path: Path, value: _JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _private_directory(output: Path) -> Path:
    directory = output / "private"
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    return directory


def _save_private(path: Path, **arrays) -> None:
    # Create with restrictive permissions, including while the file is written.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        np.savez_compressed(handle, **arrays)


def _validate_features(X: pd.DataFrame, *, allow_empty: bool = False) -> None:
    if not isinstance(X, pd.DataFrame):
        raise TypeError("Feature matrices must be pandas DataFrames.")
    if tuple(X.columns) != tuple(FEATURES):
        raise ValueError(f"Expected exactly the ordered feature columns {FEATURES}.")
    if not allow_empty and X.empty:
        raise ValueError("An explanation cohort/background cannot be empty.")


def _background(X: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    positions = np.random.default_rng(seed).choice(len(X), size=min(64, len(X)), replace=False)
    return X.iloc[positions].copy(), positions


def _dense(value) -> np.ndarray:
    if hasattr(value, "toarray"):
        value = value.toarray()
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or not np.isfinite(result).all():
        raise ValueError("Preprocessing must produce a finite two-dimensional matrix.")
    return result


def _feature_groups(names) -> tuple[list[str], np.ndarray]:
    """Resolve sklearn transformer prefixes, one-hot suffixes and missing flags."""
    groups: list[str] = []
    missing: list[bool] = []
    for original in names:
        name = str(original).split("__")[-1].lower()
        matches = [
            feature for feature in FEATURES if re.search(rf"(^|_){re.escape(feature)}($|_)", name)
        ]
        if len(matches) != 1:
            raise ValueError(f"Cannot uniquely map transformed feature {original!r}.")
        groups.append(matches[0])
        missing.append("missing" in name or "indicator" in name or name.endswith("_isna"))
    return groups, np.asarray(missing, dtype=bool)


def _group(values: np.ndarray, groups: list[str]) -> np.ndarray:
    return np.column_stack(
        [values[:, np.asarray(groups) == feature].sum(axis=1) for feature in FEATURES]
    )


def _explain_raw(bundle, background: pd.DataFrame, X: pd.DataFrame) -> RawExplanation:
    preprocessor = bundle.pipeline.named_steps["preprocess"]
    model = bundle.pipeline.named_steps["model"]
    names = [str(name) for name in preprocessor.get_feature_names_out()]
    groups, missing = _feature_groups(names)
    transformed_background = _dense(preprocessor.transform(background))
    transformed = _dense(preprocessor.transform(X))
    if transformed.shape[1] != len(names):
        raise ValueError("Transformed feature names do not match the matrix.")

    if hasattr(model, "coef_"):
        explainer = shap.LinearExplainer(
            model,
            Independent(transformed_background),
        )
    else:
        explainer = shap.TreeExplainer(
            model,
            data=transformed_background,
            feature_perturbation="interventional",
            model_output="raw",
        )

    explanation = explainer(transformed)
    if not isinstance(explanation, shap.Explanation):
        raise ValueError("Only binary, single-output logit explanations are supported.")
    values = np.asarray(explanation.values, dtype=float)
    baseline = np.asarray(explanation.base_values, dtype=float)
    if values.shape != transformed.shape:
        raise ValueError("Only binary, single-output logit explanations are supported.")
    baseline = np.broadcast_to(np.squeeze(baseline), (len(X),)).copy()
    scores = np.asarray(raw_scores(bundle, X), dtype=float).reshape(-1)
    if not np.isfinite(values).all() or not np.isfinite(baseline).all():
        raise ValueError("SHAP produced non-finite contributions.")
    if not np.allclose(baseline + values.sum(axis=1), scores, rtol=1e-5, atol=1e-5):
        raise ValueError("Raw-logit SHAP additivity failed.")
    return {
        "values": values,
        "baseline": baseline,
        "scores": scores,
        "names": names,
        "groups": groups,
        "missing": missing,
        "transformed": transformed,
        "grouped": _group(values, groups),
    }


def _calibration_parameters(bundle) -> tuple[float, float]:
    calibrator = bundle.calibrator
    if calibrator is None:
        return 0.0, 1.0
    coefficient = np.asarray(calibrator.coef_, dtype=float)
    intercept = np.asarray(calibrator.intercept_, dtype=float)
    if coefficient.size != 1 or intercept.size != 1:
        raise ValueError("Expected a fitted one-dimensional logistic recalibrator.")
    a, b = float(intercept.item()), float(coefficient.item())
    if not np.isfinite([a, b]).all():
        raise ValueError("Non-finite recalibration parameters.")
    return a, b


def _bar(values, labels, title: str, path: Path) -> None:
    values = np.asarray(values)
    order = np.argsort(np.abs(values), kind="stable")
    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.3)))
    ax.barh(
        np.asarray(labels)[order],
        values[order],
        color=np.where(values[order] < 0, "#4477aa", "#cc6677"),
    )
    ax.set_title(title)
    ax.set_xlabel("SHAP contribution (log-odds)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _model_key(key: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ValueError("Model keys must be safe filename components.")
    return key


def explain_models(
    bundles, X_train, X_explain, y_explain, output: Path, seed=2026
) -> ExplanationResult:
    """Write aggregate JSON, figures and restricted patient-level NPZ artifacts."""
    _validate_features(X_train)
    _validate_features(X_explain)
    y = np.asarray(y_explain)
    if y.shape != (len(X_explain),) or not np.isin(y, [0, 1]).all():
        raise ValueError("Explanation outcomes must be complete binary labels.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    private = _private_directory(output)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    background, positions = _background(X_train, seed)
    result: ExplanationResult = {
        "seed": seed,
        "n_explained": len(X_explain),
        "background_n": len(background),
        "shap_version": shap.__version__,
        "dependence_assumption": "interventional",
        "scale": "log-odds; not additive probability effects",
        "models": {},
        "figures": [],
        "private_figures": [],
    }
    for key, bundle in bundles.items():
        key = _model_key(key)
        data = _explain_raw(bundle, background, X_explain)
        status = calibration_status(bundle)
        available = status in {"fitted", "nonpositive-slope"}
        a, b = _calibration_parameters(bundle)
        calibrated_values = b * data["values"]
        calibrated_base = a + b * data["baseline"]
        calibrated_scores = a + b * data["scores"]
        if not np.allclose(
            calibrated_base + calibrated_values.sum(axis=1),
            calibrated_scores,
            rtol=1e-5,
            atol=1e-5,
        ):
            raise ValueError("Calibrated-logit SHAP additivity failed.")
        risk = np.asarray(
            probabilities(bundle, X_explain, calibrated=available, allow_invalid=True)
        ).reshape(-1)
        if available and not np.allclose(expit(calibrated_scores), risk, rtol=1e-5, atol=1e-7):
            raise ValueError("Recalibrated logits disagree with model probabilities.")
        grouped = data["grouped"]
        missing_values = data["values"][:, data["missing"]]
        missing_groups = np.asarray(data["groups"])[data["missing"]].tolist()
        missing_grouped = _group(missing_values, missing_groups)
        global_raw = np.abs(grouped).mean(axis=0)
        global_calibrated = np.abs(b * grouped).mean(axis=0)
        summary: ExplanationSummary = {
            "raw_additivity": True,
            "calibrated_logit_additivity": True if available else None,
            "calibration": {
                "intercept": a if available else None,
                "slope": b if available else None,
                "fitted": available,
                "status": status,
                "use": "research-only" if status == "fitted" else "invalid-diagnostic-only",
            },
            "clinical_features": list(FEATURES),
            "global_mean_absolute_raw": dict(zip(FEATURES, global_raw.tolist(), strict=True)),
            "global_mean_absolute_calibrated": dict(
                zip(FEATURES, global_calibrated.tolist(), strict=True)
            )
            if available
            else None,
            "missingness_mean_absolute_raw": dict(
                zip(FEATURES, np.abs(missing_grouped).mean(axis=0).tolist(), strict=True)
            ),
            "transformed_mean_absolute_raw": dict(
                zip(data["names"], np.abs(data["values"]).mean(axis=0).tolist(), strict=True)
            ),
            "baseline_raw_mean": float(data["baseline"].mean()),
            "baseline_calibrated_mean": float(calibrated_base.mean()) if available else None,
            "local_groups": {},
            "dependence_lookup": {},
        }
        relative = f"figures/{key}_global.png"
        _bar(global_raw, FEATURES, f"{key}: grouped raw-logit SHAP", output / relative)
        result["figures"].append(relative)

        if not hasattr(bundle.pipeline.named_steps["model"], "coef_"):
            explanation = shap.Explanation(
                values=data["values"],
                base_values=data["baseline"],
                data=data["transformed"],
                feature_names=data["names"],
            )
            shap.plots.beeswarm(explanation, show=False)
            relative = f"figures/{key}_beeswarm.png"
            plt.gcf().savefig(output / relative, dpi=160, bbox_inches="tight")
            plt.close()
            result["figures"].append(relative)
            for concept in ("age", "creatinine", "hemoglobin"):
                indices = [
                    i
                    for i, group in enumerate(data["groups"])
                    if group == concept and not data["missing"][i]
                ]
                if not indices:
                    summary["dependence_lookup"][concept] = {
                        "status": "unavailable",
                        "rule": "omit; no substitute selected after inspecting results",
                    }
                    continue
                # A continuous lab/age normally has one value column. If an
                # encoding expands it, choose the first declared non-flag column.
                index = indices[0]
                summary["dependence_lookup"][concept] = {
                    "status": "available",
                    "transformed_feature": data["names"][index],
                    "rule": "first non-missingness transformed column in schema order",
                }
                fig, ax = plt.subplots()
                ax.scatter(
                    data["transformed"][:, index],
                    data["values"][:, index],
                    s=12,
                    alpha=0.5,
                )
                ax.set_xlabel(data["names"][index] + " (transformed)")
                ax.set_ylabel("Raw SHAP (log-odds)")
                fig.tight_layout()
                relative = f"figures/{key}_dependence_{concept}.png"
                fig.savefig(output / relative, dpi=160)
                plt.close(fig)
                result["figures"].append(relative)

        threshold = bundle.threshold
        if available and (threshold is None or not np.isfinite(threshold)):
            raise ValueError("Local error groups require a fixed finite threshold.")
        predicted = risk >= threshold if threshold is not None else np.zeros(len(risk), dtype=bool)
        selected = np.full(4, -1, dtype=int)
        for number, (label, truth, prediction) in enumerate(
            [("TP", 1, True), ("FP", 0, True), ("TN", 0, False), ("FN", 1, False)]
        ):
            if not available:
                summary["local_groups"][label] = {"n": 0, "status": "calibration-unavailable"}
                continue
            candidates = np.flatnonzero((y == truth) & (predicted == prediction))
            if not len(candidates):
                summary["local_groups"][label] = {"n": 0, "status": "empty"}
                continue
            median = np.median(risk[candidates])
            position = candidates[np.argmin(np.abs(risk[candidates] - median))]
            selected[number] = position
            relative = f"private/{key}_local_{label}.png"
            _bar(
                b * grouped[position],
                FEATURES,
                f"{key} {label}: calibrated logit ({status}; research only)",
                output / relative,
            )
            (output / relative).chmod(0o600)
            result["private_figures"].append(relative)
            summary["local_groups"][label] = {
                "n": int(len(candidates)),
                "status": "selected",
                "selection_rule": (
                    "nearest within-group median calibrated risk; first row breaks ties"
                ),
                "figure": relative,
            }
        _save_private(
            private / f"{key}_explanations.npz",
            raw_values=data["values"],
            raw_baseline=data["baseline"],
            calibrated_values=calibrated_values if available else np.empty((len(X_explain), 0)),
            calibrated_baseline=calibrated_base if available else np.empty(0),
            calibration_status=np.asarray(status),
            grouped_raw=grouped,
            transformed_names=np.asarray(data["names"]),
            background_positions=positions,
            selected_local_positions=selected,
            probabilities=risk,
            probability_scale=np.asarray("calibrated" if available else "raw-only"),
        )
        result["models"][key] = summary
    _write_json(output / "explain.json", result)
    return result
