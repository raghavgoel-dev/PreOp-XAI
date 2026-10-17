"""One-dimensional validation recalibration and prespecified operating point."""

import warnings

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from preop_xai.preprocessing import feature_matrix
from preop_xai.train import ModelBundle


def raw_scores(bundle: ModelBundle, X: pd.DataFrame) -> np.ndarray:
    """Return raw log odds, not probability-valued SHAP targets."""
    x = feature_matrix(X)
    if bundle.name == "lr":
        return np.asarray(bundle.pipeline.decision_function(x), dtype=float)
    transformed = bundle.pipeline.named_steps["preprocess"].transform(x)
    return np.asarray(
        bundle.pipeline.named_steps["model"].predict(transformed, output_margin=True),
        dtype=float,
    )


def probabilities(bundle: ModelBundle, X: pd.DataFrame, calibrated: bool = True) -> np.ndarray:
    scores = raw_scores(bundle, X)
    if calibrated:
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
    y = np.asarray(y_validation, dtype=int)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Validation calibration requires both outcome classes.")
    for bundle in bundles.values():
        scores = raw_scores(bundle, X_validation)
        calibrator = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=3000)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            calibrator.fit(scores.reshape(-1, 1), y)
        bundle.calibrator = calibrator
        slope = float(calibrator.coef_[0, 0])
        bundle.diagnostics["calibration_slope"] = slope
        bundle.diagnostics["calibration_status"] = "nonpositive-slope" if slope <= 0 else "fitted"
        if slope <= 0:
            warnings.warn(
                f"{bundle.name}: non-positive calibration slope; probabilities unreliable.",
                RuntimeWarning,
                stacklevel=2,
            )
        bundle.threshold = sensitivity_threshold(y, probabilities(bundle, X_validation))
