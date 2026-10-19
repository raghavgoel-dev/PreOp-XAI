"""One-dimensional validation recalibration and prespecified operating point."""

import warnings

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from preop_xai.preprocessing import binary_outcomes, feature_matrix
from preop_xai.train import ModelBundle


def raw_scores(bundle: ModelBundle, X: pd.DataFrame) -> np.ndarray:
    """Return raw log odds, not probability-valued SHAP targets."""
    x = feature_matrix(X)
    if not np.array_equal(bundle.pipeline.classes_, [0, 1]):
        raise ValueError("Model classes must be [0, 1], with event class 1.")
    if bundle.name == "lr":
        return np.asarray(bundle.pipeline.decision_function(x), dtype=float)
    transformed = bundle.pipeline.named_steps["preprocess"].transform(x)
    return np.asarray(
        bundle.pipeline.named_steps["model"].predict(transformed, output_margin=True),
        dtype=float,
    )


def calibration_status(bundle: ModelBundle) -> str:
    """Inspect actual parameters; a positive slope is necessary, not clinical validation."""
    if bundle.calibrator is None:
        return str(bundle.diagnostics.get("calibration_status", "not-fitted"))
    parameters = np.r_[bundle.calibrator.intercept_, bundle.calibrator.coef_.reshape(-1)]
    if parameters.shape != (2,) or not np.isfinite(parameters).all():
        return "nonfinite-parameters"
    return "fitted" if parameters[1] > 0 else "nonpositive-slope"


def probabilities(
    bundle: ModelBundle, X: pd.DataFrame, calibrated: bool = True, *, allow_invalid: bool = False
) -> np.ndarray:
    """Reject invalid risk calibration unless explicitly requesting research diagnostics."""
    scores = raw_scores(bundle, X)
    if calibrated:
        status = calibration_status(bundle)
        if status != "fitted" and not (allow_invalid and status == "nonpositive-slope"):
            raise ValueError(f"Calibrated risk unavailable: {status}.")
        if bundle.calibrator is None:
            raise ValueError("Validation calibration has not been fitted.")
        intercept = np.asarray(bundle.calibrator.intercept_).reshape(-1)[0]
        scores = intercept + bundle.calibrator.coef_[0, 0] * scores
    return expit(scores)


def sensitivity_threshold(y: np.ndarray, probability: np.ndarray) -> float:
    """Highest observed threshold with sensitivity >= 0.8, including score ties."""
    positives = np.asarray(probability)[np.asarray(y) == 1]
    if not len(positives):
        raise ValueError("Validation sensitivity is undefined without positive events.")
    return float(np.sort(positives)[len(positives) - int(np.ceil(0.8 * len(positives)))])


def calibrate_models(
    bundles: dict[str, ModelBundle],
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
) -> None:
    y = binary_outcomes(X_validation, y_validation)
    for bundle in bundles.values():
        bundle.calibrator, bundle.threshold = None, None
        for key in list(bundle.diagnostics):
            if key.startswith("calibration_"):
                del bundle.diagnostics[key]
        events = int(y.sum())
        bundle.diagnostics.update(
            calibration_n=len(y),
            calibration_events=events,
            calibration_nonevents=len(y) - events,
            calibration_policy="reject-risk; explicit raw-only research inference",
        )
        scores = raw_scores(bundle, X_validation)
        reason = ""
        if min(events, len(y) - events) < 2:
            reason = "insufficient-events"
        elif not np.isfinite(scores).all():
            reason = "nonfinite-scores"
        elif np.ptp(scores) <= np.finfo(float).eps * max(1.0, float(np.max(np.abs(scores)))):
            reason = "constant-scores"
        elif (
            scores[y == 0].max() <= scores[y == 1].min()
            or scores[y == 1].max() <= scores[y == 0].min()
        ):
            reason = "separated-scores"
        if reason:
            bundle.diagnostics["calibration_status"] = reason
            warnings.warn(
                f"{bundle.name}: calibration unavailable ({reason}); raw research scores only.",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        calibrator = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=3000, tol=1e-8)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                calibrator.fit(scores.reshape(-1, 1), y)
        except ConvergenceWarning as error:
            bundle.diagnostics["calibration_status"] = "optimizer-not-converged"
            bundle.diagnostics["calibration_optimizer_message"] = str(error)
            warnings.warn(
                f"{bundle.name}: calibration optimizer did not converge; raw research scores only.",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        bundle.calibrator = calibrator
        slope = float(calibrator.coef_[0, 0])
        bundle.diagnostics["calibration_intercept"] = float(
            np.asarray(calibrator.intercept_).reshape(-1)[0]
        )
        bundle.diagnostics["calibration_slope"] = slope
        status = calibration_status(bundle)
        bundle.diagnostics["calibration_status"] = status
        if status == "nonfinite-parameters":
            bundle.calibrator = None
            warnings.warn(
                f"{bundle.name}: nonfinite calibration parameters; raw research scores only.",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        if slope <= 0:
            warnings.warn(
                f"{bundle.name}: non-positive calibration slope; probabilities unreliable.",
                RuntimeWarning,
                stacklevel=2,
            )
        # This is a research diagnostic operating point, including invalid fits.
        # Inference withholds both this classification and invalid probabilities.
        bundle.threshold = sensitivity_threshold(
            y, probabilities(bundle, X_validation, allow_invalid=True)
        )
