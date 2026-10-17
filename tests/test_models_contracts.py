"""Scientific preprocessing and threshold regression checks."""

import numpy as np
import pandas as pd
import pytest

from preop_xai.calibration import calibrate_models, sensitivity_threshold
from preop_xai.evaluate import evaluate_models
from preop_xai.preprocessing import FEATURES, LABS, feature_matrix, make_preprocessor
from preop_xai.train import fit_models


def clinical_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [20.0, 30.0, 40.0],
            "sex": ["F", "M", "F"],
            "asa": ["1", "2", "1"],
            **{lab: [1.0, np.nan, 3.0] for lab in LABS},
        },
    )


def test_imputation_uses_training_median_not_validation() -> None:
    # Given: training median is two, validation contains extreme future values.
    training = clinical_frame()
    validation = training.copy()
    validation["hemoglobin"] = [1000.0, np.nan, 2000.0]
    preprocessor = make_preprocessor(scale=False).fit(training)
    # When: only transform validation.
    transformed = preprocessor.transform(validation)
    names = list(preprocessor.get_feature_names_out())
    # Then: missing value uses the frozen training median.
    assert transformed[1, names.index("numeric__hemoglobin")] == 2.0


def test_all_missing_lab_keeps_value_and_indicator() -> None:
    # Given: a lab is absent throughout training.
    training = clinical_frame()
    training["bun"] = np.nan
    # When: fitting the training preprocessor.
    preprocessor = make_preprocessor(scale=False).fit(training)
    transformed = preprocessor.transform(training)
    names = list(preprocessor.get_feature_names_out())
    # Then: dimensionality and explicit absence survive.
    assert "numeric__bun" in names
    indicators = [i for i, name in enumerate(names) if name.startswith("missing__")]
    assert len(indicators) == 7
    assert np.all(transformed[:, indicators[LABS.index("bun")]] == 1)


def test_outcome_cannot_enter_feature_boundary() -> None:
    # Given: accidental label leakage.
    frame = clinical_frame().assign(mortality=0)
    # When/Then: the boundary rejects it rather than silently fitting.
    with pytest.raises(ValueError, match="fixed clinical inputs"):
        feature_matrix(frame)


def test_highest_sensitivity_threshold_handles_ties() -> None:
    # Given: five positive events with tied risks.
    y = np.array([1, 1, 1, 1, 1, 0])
    p = np.array([0.1, 0.2, 0.2, 0.8, 0.9, 0.4])
    # When: choosing the prespecified operating point.
    threshold = sensitivity_threshold(y, p)
    # Then: 0.2 is the highest threshold retaining >=80% sensitivity.
    assert threshold == 0.2
    assert np.mean(p[y == 1] >= threshold) == 0.8


def test_allowlist_has_ten_clinical_concepts() -> None:
    # Given/When: a canonical clinical frame crosses the boundary.
    matrix = feature_matrix(clinical_frame())
    # Then: only intended clinical values survive in their specified order.
    assert list(matrix.columns) == list(FEATURES)


def test_calibration_keeps_base_models_fixed_and_bootstrap_keeps_pairing(tmp_path):
    # Given: real fitted pipelines and a held-out binary validation sample.
    rng = np.random.default_rng(31)
    frame = pd.concat([clinical_frame()] * 30, ignore_index=True)
    frame["age"] = rng.uniform(20, 85, len(frame))
    labels = pd.Series((frame["age"] + rng.normal(0, 20, len(frame)) > 55).astype(int))
    bundles = fit_models(frame.iloc[:60], labels.iloc[:60], folds=2, quick=True)
    before = bundles["lr"].pipeline.named_steps["model"].coef_.copy()
    # When: validation-only calibration and paired evaluation of identical fitted predictions.
    calibrate_models(bundles, frame.iloc[60:], labels.iloc[60:])
    results = evaluate_models(
        {"first": bundles["lr"], "second": bundles["lr"]},
        frame.iloc[60:],
        labels.iloc[60:],
        tmp_path,
        bootstraps=40,
    )
    # Then: base coefficients are unchanged and paired differences are exactly zero.
    np.testing.assert_array_equal(bundles["lr"].pipeline.named_steps["model"].coef_, before)
    paired = results["intervals"]["paired_second_minus_first.calibrated.brier"]
    assert paired["lower"] == paired["upper"] == 0
    assert paired["effective_resamples"] == 40
