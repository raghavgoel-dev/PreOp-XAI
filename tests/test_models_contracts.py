"""Scientific preprocessing and threshold regression checks."""

import numpy as np
import pandas as pd
import pytest

from preop_xai.calibration import calibrate_models, probabilities, sensitivity_threshold
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
    assert "intervals" in results
    paired = results["intervals"]["paired_second_minus_first.calibrated.brier"]
    assert paired["lower"] == paired["upper"] == 0
    assert paired["effective_resamples"] == 40


def test_nonpositive_calibration_is_not_returned_as_risk():
    # Given: a fitted model with an explicitly reversed recalibrator.
    from sklearn.linear_model import LogisticRegression

    frame = pd.concat([clinical_frame()] * 8, ignore_index=True)
    labels = pd.Series([0, 1, 0] * 8)
    bundle = fit_models(frame, labels, folds=2, quick=True)["lr"]
    bundle.calibrator = LogisticRegression().fit(np.array([-2, -1, 1, 2])[:, None], [0, 0, 1, 1])
    calibrator = bundle.calibrator
    assert calibrator is not None
    calibrator.coef_[:] = -1
    # When/Then: ordinary calibrated prediction must reject unreliable risks.
    with pytest.raises(ValueError, match="nonpositive-slope"):
        probabilities(bundle, frame)


def test_shuffled_labels_are_rejected_before_fitting():
    # Given: label positions no longer correspond to feature indices.
    frame = pd.concat([clinical_frame()] * 8, ignore_index=True)
    labels = pd.Series([0, 1, 0] * 8).iloc[::-1]
    # When/Then: a silent patient/label permutation must not fit a model.
    with pytest.raises(ValueError, match="aligned"):
        fit_models(frame, labels, folds=2, quick=True)


@pytest.mark.parametrize("value", [0.5, 2, np.nan])
def test_nonbinary_training_labels_are_not_truncated(value):
    # Given: an invalid label amongst otherwise binary events.
    frame = pd.concat([clinical_frame()] * 8, ignore_index=True)
    labels = pd.Series([0.0, 1.0, 0.0] * 8)
    labels.iloc[0] = value
    # When/Then: integer conversion cannot turn it into a different outcome.
    with pytest.raises(ValueError, match="binary"):
        fit_models(frame, labels, folds=2, quick=True)


def test_duplicate_feature_columns_are_rejected():
    # Given: the allowlist set is correct but one predictor appears twice.
    frame = clinical_frame()
    frame = pd.concat([frame, frame[["age"]]], axis=1)
    # When/Then: duplicated values cannot enter fitted preprocessing.
    with pytest.raises(ValueError, match="unique"):
        feature_matrix(frame)


@pytest.mark.parametrize("scenario", ["single-class", "constant-scores", "separated-scores"])
def test_unestimable_calibration_retains_raw_research_evaluation(tmp_path, scenario):
    # Given: a fitted base model and validation data without an estimable recalibrator.
    frame = pd.concat([clinical_frame()] * 8, ignore_index=True)
    labels = pd.Series([0, 1, 0] * 8)
    bundle = fit_models(frame, labels, folds=2, quick=True)["lr"]
    validation = frame.copy()
    outcomes = labels.copy()
    if scenario == "single-class":
        outcomes[:] = 0
        expected = "insufficient-events"
    elif scenario == "constant-scores":
        validation = pd.concat([frame.iloc[[0]]] * len(frame), ignore_index=True)
        expected = "constant-scores"
    else:
        from preop_xai.calibration import raw_scores

        scores = raw_scores(bundle, validation)
        outcomes = pd.Series((scores > np.median(scores)).astype(int))
        expected = "separated-scores"
    # When: calibration is attempted and the fixed raw model is evaluated diagnostically.
    with pytest.warns(RuntimeWarning, match="calibration unavailable"):
        calibrate_models({"lr": bundle}, validation, outcomes)
    result = evaluate_models({"lr": bundle}, validation, outcomes, tmp_path, bootstraps=8)
    # Then: no invented recalibrator, threshold or calibrated measure is supplied.
    assert bundle.calibrator is bundle.threshold is None
    assert bundle.diagnostics["calibration_status"] == expected
    assert result["models"]["lr"]["calibrated"] is None
    assert result["models"]["lr"]["tp"] is None
    assert result["models"]["lr"]["raw"]["brier"] is not None


def test_calibration_diagnostics_do_not_return_unconverged_estimates():
    # Given: perfect separation has no finite unpenalized calibration MLE.
    from preop_xai.evaluate import calibration_parameters

    # When: requesting descriptive held-out calibration parameters.
    result = calibration_parameters(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9]))
    # Then: numerical optimizer output cannot masquerade as a converged estimate.
    assert result["status"] == "separated-scores"
    assert result["joint_slope"] is None
    assert result["converged"] is False
