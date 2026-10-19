"""Inspect a trusted synthetic campaign without refitting models or opening test data."""

import json
from pathlib import Path
from typing import NotRequired, TypedDict

import joblib
import numpy as np
import pandas as pd
import typer
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import roc_auc_score

from preop_xai.calibration import raw_scores
from preop_xai.config import write_json
from preop_xai.demo import synthetic_tables
from preop_xai.preprocessing import FEATURES, get_column


class ModelDiagnostic(TypedDict):
    classes: list[int]
    raw_auroc: float
    sigmoid_vs_predict_proba_max_error: float
    score_event_covariance: float
    intercept: NotRequired[float]
    slope: NotRequired[float]
    threshold: NotRequired[float | None]
    calibrated_auroc: NotRequired[float]
    independent_intercept: NotRequired[float]
    independent_slope: NotRequired[float]
    independent_success: NotRequired[bool]
    independent_gradient_max: NotRequired[float]
    saved_gradient_max: NotRequired[float]


class PartitionDiagnostic(TypedDict):
    n: int
    positive: int
    negative: int
    label_mismatches: int
    generating_score_auroc: float
    generating_probability_range: list[float]
    models: dict[str, ModelDiagnostic]


def inspect(campaign: Path, seed: int = 2026, output: Path | None = None) -> None:
    """Print identity checks and independent validation likelihood diagnostics."""
    information, complications, _, _, _ = synthetic_tables(seed)
    expected = information[["patient_id", "operation_id"]].assign(
        mortality=information.disposition.eq("Synthetic death").astype(int),
        respiratory=complications.value.eq("Synthetic yes").astype(int),
    )
    result: dict[str, dict[str, PartitionDiagnostic]] = {}
    for endpoint in ("mortality", "respiratory"):
        models = joblib.load(campaign / endpoint / "models.joblib")
        endpoint_result: dict[str, PartitionDiagnostic] = {}
        for partition in ("train", "validation"):
            frame = pd.read_parquet(campaign / f"{partition}.parquet")
            linked = frame.merge(
                expected,
                on=["patient_id", "operation_id"],
                validate="one_to_one",
                suffixes=("", "_expected"),
                how="left",
            )
            if get_column(linked, f"{endpoint}_expected").isna().any():
                raise ValueError("Campaign identities do not match synthetic generating records.")
            y = get_column(frame, endpoint).to_numpy(dtype=int)
            x = frame.loc[:, list(FEATURES)]
            generating_score = (
                -2.5 + 0.04 * (x.age - 50) + 0.55 * (x.asa.astype(float) - 2)
                if endpoint == "mortality"
                else -2.2 + 0.5 * (x.asa.astype(float) - 2)
            )
            measurements: PartitionDiagnostic = {
                "n": len(y),
                "positive": int(y.sum()),
                "negative": int((1 - y).sum()),
                "label_mismatches": int(
                    np.sum(y != get_column(linked, f"{endpoint}_expected").to_numpy(dtype=int))
                ),
                "generating_score_auroc": float(roc_auc_score(y, generating_score)),
                "generating_probability_range": [
                    float(expit(generating_score).min()),
                    float(expit(generating_score).max()),
                ],
                "models": {},
            }
            for name, bundle in models.items():
                z = raw_scores(bundle, x)
                p = bundle.pipeline.predict_proba(x)[:, 1]
                model_result: ModelDiagnostic = {
                    "classes": bundle.pipeline.classes_.tolist(),
                    "raw_auroc": float(roc_auc_score(y, z)),
                    "sigmoid_vs_predict_proba_max_error": float(np.max(np.abs(expit(z) - p))),
                    "score_event_covariance": float(np.mean((z - z.mean()) * (y - y.mean()))),
                }
                if partition == "validation":
                    design = np.column_stack([np.ones(len(z)), z])

                    def loss(
                        theta: np.ndarray, design: np.ndarray = design, y: np.ndarray = y
                    ) -> float:
                        eta = design @ theta
                        return float(np.sum(np.logaddexp(0, eta) - y * eta))

                    def gradient(
                        theta: np.ndarray, design: np.ndarray = design, y: np.ndarray = y
                    ) -> np.ndarray:
                        return design.T @ (expit(design @ theta) - y)

                    fitted = minimize(
                        loss,
                        np.array([0.0, 1.0]),
                        jac=gradient,
                        method="BFGS",
                        options={"gtol": 1e-8},
                    )
                    a = float(bundle.calibrator.intercept_[0])
                    b = float(bundle.calibrator.coef_[0, 0])
                    calibrated = expit(a + b * z)
                    model_result.update(
                        intercept=a,
                        slope=b,
                        threshold=bundle.threshold,
                        calibrated_auroc=float(roc_auc_score(y, calibrated)),
                        independent_intercept=float(fitted.x[0]),
                        independent_slope=float(fitted.x[1]),
                        independent_success=bool(fitted.success),
                        independent_gradient_max=float(np.max(np.abs(gradient(fitted.x)))),
                        saved_gradient_max=float(np.max(np.abs(gradient(np.array([a, b]))))),
                    )
                measurements["models"][name] = model_result
            endpoint_result[partition] = measurements
        result[endpoint] = endpoint_result
    typer.echo(json.dumps(result, indent=2, allow_nan=False))
    if output is not None:
        if output.exists():
            raise ValueError("Diagnostic output exists; preserve the prior evidence.")
        write_json(output, result)


if __name__ == "__main__":
    typer.run(inspect)
