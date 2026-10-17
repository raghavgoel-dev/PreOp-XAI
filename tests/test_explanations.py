"""Small direct scientific tests; all observations are synthetic."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import xgboost
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from preop_xai.explain import (
    _background,
    _calibration_parameters,
    _explain_raw,
    _feature_groups,
    _group,
    explain_models,
)
from preop_xai.preprocessing import FEATURES
from preop_xai.reporting import build_report
from preop_xai.stability import _rank_correlation, _summarize, run_stability


@pytest.fixture
def synthetic():
    rng = np.random.default_rng(41)
    X = pd.DataFrame(rng.normal(size=(100, len(FEATURES))), columns=FEATURES)
    y = (X["age"].to_numpy() + rng.normal(size=len(X)) > 0).astype(int)
    return X.iloc[:72].copy(), y[:72], X.iloc[72:].copy(), y[72:]


def make_bundle(X, y, tree=False):
    if tree:
        model = xgboost.XGBClassifier(
            n_estimators=8,
            max_depth=2,
            learning_rate=0.15,
            n_jobs=1,
            random_state=19,
            eval_metric="logloss",
        )
    else:
        model = LogisticRegression(C=0.7, max_iter=500)
    preprocessing = ColumnTransformer(
        [
            (
                "values",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                list(FEATURES),
            )
        ]
    )
    pipeline = Pipeline([("preprocess", preprocessing), ("model", model)])
    pipeline.fit(X, y)
    calibrator = LogisticRegression().fit(np.array([-2, -1, 1, 2])[:, None], [0, 0, 1, 1])
    # Deliberately nonidentity calibration verifies intercept and slope handling.
    calibrator.coef_[:] = 0.6
    calibrator.intercept_[:] = -0.4
    return SimpleNamespace(
        pipeline=pipeline,
        calibrator=calibrator,
        threshold=0.5,
        name="xgboost" if tree else "lr",
        parameters={},
        cv_score=0.5,
        training_prevalence=float(np.mean(y)),
    )


@pytest.mark.parametrize("tree", [False, True])
def test_raw_and_calibrated_logit_additivity(synthetic, tree):
    train, y, validation, _ = synthetic
    bundle = make_bundle(train, y, tree)
    background, positions = _background(train, 26)
    data = _explain_raw(bundle, background, validation)
    transformed = bundle.pipeline.named_steps["preprocess"].transform(validation)
    model = bundle.pipeline.named_steps["model"]
    expected = np.asarray(
        (
            model.predict(transformed, output_margin=True)
            if tree
            else model.decision_function(transformed)
        ),
        dtype=float,
    )
    np.testing.assert_allclose(data["baseline"] + data["values"].sum(axis=1), expected, atol=1e-5)
    a, b = _calibration_parameters(bundle)
    np.testing.assert_allclose(
        a + b * data["baseline"] + (b * data["values"]).sum(axis=1),
        a + b * expected,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        expit(a + b * expected),
        bundle.calibrator.predict_proba(np.asarray(expected)[:, None])[:, 1],
    )
    assert len(positions) == 64
    np.testing.assert_array_equal(positions, _background(train, 26)[1])


def test_grouping_preserves_sums_and_exposes_missingness():
    groups, missing = _feature_groups(
        ["numeric__creatinine", "flags__creatinine_missing", "cat__sex_F", "cat__sex_M"]
    )
    values = np.array([[0.4, -0.2, 0.1, 0.3], [-0.3, 0.2, -0.1, -0.2]])
    grouped = _group(values, groups)
    np.testing.assert_allclose(grouped.sum(axis=1), values.sum(axis=1))
    assert missing.tolist() == [False, True, False, False]
    np.testing.assert_allclose(grouped[:, list(FEATURES).index("creatinine")], [0.2, -0.1])


def test_undefined_ranks_are_null_without_warnings():
    with __import__("warnings").catch_warnings(record=True) as caught:
        assert _rank_correlation(np.zeros(10), np.arange(10)) is None
        summary = _summarize(np.zeros((3, 4, len(FEATURES))), np.zeros((3, 4)))
    assert not caught
    assert summary["spearman_mean"] is None
    assert summary["spearman_undefined_pairs"] == 3
    assert summary["top5_jaccard_mean"] == 1.0


def test_stability_does_not_mutate_original_and_is_reproducible(synthetic, tmp_path):
    train, y, validation, _ = synthetic
    bundle = make_bundle(train, y)
    coefficient = bundle.pipeline.named_steps["model"].coef_.copy()
    calibration = deepcopy(bundle.calibrator.coef_)
    first = run_stability({"lr": bundle}, train, y, validation, tmp_path / "first", refits=3)
    second = run_stability({"lr": bundle}, train, y, validation, tmp_path / "second", refits=3)
    assert first == second
    assert first["models"]["lr"]["successful_refits"] == 3
    np.testing.assert_array_equal(bundle.pipeline.named_steps["model"].coef_, coefficient)
    np.testing.assert_array_equal(bundle.calibrator.coef_, calibration)
    arrays = np.load(tmp_path / "first/private/lr_stability.npz")
    np.testing.assert_allclose(arrays["centered_contributions"].mean(axis=0), 0, atol=1e-14)


def test_artifacts_empty_groups_and_report(synthetic, tmp_path):
    train, y, validation, labels = synthetic
    bundle = make_bundle(train, y)
    bundle.threshold = 1.0
    result = explain_models({"lr": bundle}, train, validation, labels, tmp_path)
    assert result["models"]["lr"]["local_groups"]["TP"]["status"] == "empty"
    assert result["models"]["lr"]["local_groups"]["FP"]["status"] == "empty"
    assert build_report(tmp_path).is_file()
    assert (tmp_path / "private/lr_explanations.npz").exists()


def test_identity_columns_are_rejected(synthetic, tmp_path):
    train, y, validation, labels = synthetic
    bundle = make_bundle(train, y)
    with pytest.raises(ValueError, match="feature columns"):
        explain_models(
            {"lr": bundle},
            train.assign(patient_id=np.arange(len(train))),
            validation,
            labels,
            tmp_path,
        )
