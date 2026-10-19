"""Real fitted inference contracts, CSV boundary failures and artifact compatibility."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import yaml
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from preop_xai.calibration import calibrate_models, raw_scores
from preop_xai.config import file_hash
from preop_xai.inference import predict_file, write_bundle_metadata
from preop_xai.preprocessing import FEATURES, LABS, get_column, make_preprocessor
from preop_xai.train import fit_models


@pytest.fixture(scope="module")
def fitted_models():
    rng = np.random.default_rng(602)
    n = 144
    frame = pd.DataFrame(
        {
            "age": rng.uniform(18, 90, n),
            "sex": rng.choice(["F", "M"], n),
            "asa": rng.choice(["1", "2", "3", "4", "5"], n),
            **{
                name: rng.normal(mean, deviation, n)
                for name, mean, deviation in zip(
                    LABS,
                    [13, 220, 1.1, 18, 140, 4, 110],
                    [2, 30, 0.2, 3, 3, 0.4, 20],
                    strict=True,
                )
            },
        }
    )
    frame.loc[[2, 11, 101], "bun"] = np.nan
    y = pd.Series((frame["age"] + rng.normal(0, 12, n) > 57).astype(int))
    models = fit_models(frame.iloc[:96], y.iloc[:96], folds=2, quick=True)
    calibrate_models(models, frame.iloc[96:], y.iloc[96:])
    assert all(
        model.calibrator is not None and model.calibrator.coef_[0, 0] > 0
        for model in models.values()
    )
    return models, frame


@pytest.fixture
def saved_bundle(tmp_path, fitted_models):
    models, frame = fitted_models
    destination = tmp_path / "mortality"
    destination.mkdir()
    joblib.dump(copy.deepcopy(models), destination / "models.joblib")
    with Path("configs/feature_map.yaml").open(encoding="utf-8") as handle:
        mapping = yaml.safe_load(handle)
    mapping["reviewed"] = True
    write_bundle_metadata(
        destination,
        endpoint="mortality",
        synthetic_only=True,
        review_status="synthetic-reviewed",
        feature_mapping=mapping,
    )
    # Independently constructed records, never used for training or calibration.
    sample = pd.DataFrame(
        {
            "age": [43.5, 72.5, 26.5],
            "sex": ["F", "M", "F"],
            "asa": ["2", "3", "1"],
            "hemoglobin": [12.7, 13.1, 14.2],
            "platelets": [210, 180, 240],
            "creatinine": [1.0, 1.2, 0.9],
            "bun": [np.nan, 19, 17],
            "sodium": [140, 138, 141],
            "potassium": [4.0, 4.3, 3.9],
            "glucose": [100, 125, 95],
        }
    )
    input_path = tmp_path / "input.csv"
    sample.to_csv(input_path, index=False)
    return destination, input_path, tmp_path / "predictions.csv", sample


def _metadata(destination):
    return json.loads((destination / "bundle.json").read_text(encoding="utf-8"))


def _replace_metadata(destination, payload):
    (destination / "bundle.json").write_text(json.dumps(payload), encoding="utf-8")


def _replace_models(destination, models):
    joblib.dump(models, destination / "models.joblib")
    metadata = _metadata(destination)
    metadata["models_sha256"] = file_hash(destination / "models.joblib")
    _replace_metadata(destination, metadata)


@pytest.mark.parametrize("name", ["lr", "xgboost"])
def test_real_predictions_match_frozen_pipeline_and_single_rows(
    saved_bundle, fitted_models, monkeypatch, name
):
    destination, input_path, output, frame = saved_bundle
    # The expectation comes from the in-memory objects BEFORE serialization.
    models, _ = fitted_models
    expected_score = raw_scores(models[name], frame)
    expected_probability = models[name].pipeline.predict_proba(frame)[:, 1]
    calibrator = models[name].calibrator
    expected_calibrated = expit(calibrator.intercept_[0] + calibrator.coef_[0, 0] * expected_score)
    before = file_hash(destination / "models.joblib")

    def forbid_fit(*args, **kwargs):
        raise AssertionError("Inference must never fit or refit a pipeline")

    for estimator in (
        Pipeline,
        ColumnTransformer,
        SimpleImputer,
        StandardScaler,
        OneHotEncoder,
        LogisticRegression,
        XGBClassifier,
    ):
        monkeypatch.setattr(estimator, "fit", forbid_fit)
        if hasattr(estimator, "fit_transform"):
            monkeypatch.setattr(estimator, "fit_transform", forbid_fit)
    predict_file(destination, input_path, output, name)
    batch = pd.read_csv(output)
    np.testing.assert_allclose(batch["raw_score"], expected_score, rtol=1e-14, atol=1e-14)
    np.testing.assert_allclose(batch["raw_probability"], expected_probability, rtol=1e-6)
    np.testing.assert_allclose(batch["calibrated_probability"], expected_calibrated, atol=1e-14)
    np.testing.assert_array_equal(
        batch["research_classification"],
        expected_calibrated >= models[name].threshold,
    )
    assert batch["row_position"].tolist() == [0, 1, 2]
    assert get_column(batch, "endpoint").eq("mortality").all()
    assert get_column(batch, "model").eq(name).all()
    assert get_column(batch, "synthetic_only").all()
    assert get_column(batch, "artifact_version").eq(1).all()
    assert get_column(batch, "internal_validation_status").eq("not-completed").all()
    assert get_column(batch, "clinical_use").eq("unsupported-research-only").all()
    assert get_column(batch, "timing_status").eq("not-verifiable-from-feature-only-input").all()
    assert get_column(batch, "data_review_status").eq("synthetic-reviewed").all()
    for position in range(len(frame)):
        frame.iloc[[position]].to_csv(input_path, index=False)
        single_output = output.with_name(f"single-{name}-{position}.csv")
        predict_file(destination, input_path, single_output, name)
        single = pd.read_csv(single_output)
        columns = ["raw_score", "raw_probability", "calibrated_probability"]
        np.testing.assert_allclose(
            single[columns].to_numpy(),
            batch.iloc[[position]][columns],
            rtol=0,
            atol=1e-14,
        )
    assert file_hash(destination / "models.joblib") == before


@pytest.mark.parametrize("name", ["lr", "xgboost"])
def test_categories_missing_labs_and_reordered_header(saved_bundle, name):
    destination, input_path, output, frame = saved_bundle
    frame["sex"] = ["never-seen", "", "NA"]
    frame["asa"] = ["2.0", "", "unknown"]
    frame.loc[0, list(LABS)] = np.nan
    frame.loc[:, list(reversed(FEATURES))].to_csv(input_path, index=False)
    predict_file(destination, input_path, output, name)
    result = pd.read_csv(output)
    normalized = frame.copy()
    normalized["sex"] = ["never-seen", "unknown", "NA"]
    normalized["asa"] = ["2", "unknown", "unknown"]
    model = joblib.load(destination / "models.joblib")[name]
    np.testing.assert_allclose(result["raw_score"], raw_scores(model, normalized), atol=1e-14)
    assert result["calibrated_probability"].between(0, 1).all()


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("age", "", "Age is required"),
        ("age", "17.99", "bounds"),
        ("age", "90.01", "bounds"),
        ("age", "inf", "Nonfinite"),
        ("age", "NaN", "Nonnumeric|Nonfinite"),
        ("age", "not-a-number", "Nonnumeric"),
        ("hemoglobin", "inf", "Nonfinite"),
        ("hemoglobin", "NaN", "Nonnumeric|Nonfinite"),
        ("hemoglobin", "13 g/dL", "Nonnumeric"),
        ("hemoglobin", "130", "bounds"),
        ("sodium", "69", "bounds"),
        ("potassium", "12.1", "bounds"),
        ("asa", "0", "ASA"),
        ("asa", "6", "ASA"),
        ("asa", "2.5", "ASA"),
        ("asa", "inf", "ASA"),
        ("asa", "NaN", "ASA"),
        ("asa", "II", "ASA"),
    ],
)
def test_invalid_feature_values_fail_without_output(saved_bundle, column, value, message):
    destination, input_path, output, frame = saved_bundle
    frame = frame.astype(object)
    frame.loc[0, column] = value
    frame.to_csv(input_path, index=False)
    with pytest.raises(ValueError, match=message):
        predict_file(destination, input_path, output, "lr")
    assert not output.exists()


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "header-only",
        "duplicate",
        "extra",
        "missing",
        "short",
        "long",
        "blank",
        "bad-quote",
    ],
)
def test_csv_structure_rejected_before_joblib_load(saved_bundle, monkeypatch, case):
    destination, input_path, output, frame = saved_bundle
    header = ",".join(FEATURES)
    row = ",".join(str(value) for value in frame.iloc[1])
    contents = {
        "empty": "",
        "header-only": header + "\n",
        "duplicate": header.replace("sex", "age") + "\n" + row,
        "extra": header + ",mortality\n" + row + ",0",
        "missing": header.replace(",sex", "") + "\n" + row,
        "short": header + "\n1,2",
        "long": header + "\n" + row + ",extra",
        "blank": header + "\n\n",
        "bad-quote": header + '\n"unterminated',
    }
    input_path.write_text(contents[case], encoding="utf-8")

    def forbid_load(*args, **kwargs):
        raise AssertionError("Invalid CSV must be rejected before model loading")

    monkeypatch.setattr(joblib, "load", forbid_load)
    with pytest.raises(ValueError):
        predict_file(destination, input_path, output, "lr")
    assert not output.exists()


@pytest.mark.parametrize(
    "case",
    [
        "version",
        "boolean-version",
        "runtime",
        "schema",
        "policy",
        "event",
        "hash",
        "unit",
        "review",
        "endpoint",
    ],
)
def test_incompatible_metadata_rejected_before_deserialization(saved_bundle, monkeypatch, case):
    destination, input_path, output, _ = saved_bundle
    metadata = _metadata(destination)
    if case == "version":
        metadata["artifact_version"] = 2
    elif case == "boolean-version":
        metadata["artifact_version"] = True
    elif case == "runtime":
        metadata["runtime"]["packages"]["scikit-learn"] = "0.invalid"
    elif case == "schema":
        metadata["schema"][0]["name"] = "patient_id"
    elif case == "policy":
        metadata["categorical_policy"]["unseen"] = "learn-at-inference"
    elif case == "event":
        metadata["positive_event"] = 0
    elif case == "hash":
        metadata["models_sha256"] = "0" * 64
    elif case == "unit":
        metadata["input_units"] = "guess"
    elif case == "review":
        metadata["feature_mapping"]["reviewed"] = False
    elif case == "endpoint":
        metadata["endpoint"] = "not-an-endpoint"
    _replace_metadata(destination, metadata)

    def forbid_load(*args, **kwargs):
        raise AssertionError("Incompatible artifacts must be rejected before joblib.load")

    monkeypatch.setattr(joblib, "load", forbid_load)
    with pytest.raises(ValueError):
        predict_file(destination, input_path, output, "lr")
    assert not output.exists()


@pytest.mark.parametrize(
    "case",
    ["none", "unfitted", "zero", "negative", "nan", "intercept", "classes"],
)
def test_invalid_calibration_fails_closed_and_explicit_raw_mode(saved_bundle, case):
    destination, input_path, output, _ = saved_bundle
    models = joblib.load(destination / "models.joblib")
    model = models["lr"]
    # Deliberately stale diagnostics must never overrule the actual fitted state.
    model.diagnostics["calibration_status"] = "fitted"
    if case == "none":
        model.calibrator = None
    elif case == "unfitted":
        model.calibrator = LogisticRegression()
    elif case == "zero":
        model.calibrator.coef_[0, 0] = 0
    elif case == "negative":
        model.calibrator.coef_[0, 0] = -1
    elif case == "nan":
        model.calibrator.coef_[0, 0] = np.nan
    elif case == "intercept":
        model.calibrator.intercept_[0] = np.inf
    elif case == "classes":
        model.calibrator.classes_ = np.array([1, 2])
    _replace_models(destination, models)
    with pytest.raises(ValueError, match="calibration is invalid"):
        predict_file(destination, input_path, output, "lr")
    assert not output.exists()
    predict_file(destination, input_path, output, "lr", research_only=True)
    result = pd.read_csv(output)
    assert result["raw_probability"].between(0, 1).all()
    assert get_column(result, "raw_score").notna().all()
    columns = ["calibrated_probability", "research_threshold", "research_classification"]
    assert np.asarray(result[columns].isna()).all()
    assert not get_column(result, "calibration_status").eq("fitted").any()


@pytest.mark.parametrize("threshold", [None, np.nan, np.inf, -0.1, 1.1, True])
def test_invalid_saved_threshold_rejected(saved_bundle, threshold):
    destination, input_path, output, _ = saved_bundle
    models = joblib.load(destination / "models.joblib")
    models["lr"].threshold = threshold
    _replace_models(destination, models)
    with pytest.raises(ValueError, match="saved research threshold"):
        predict_file(destination, input_path, output, "lr")


@pytest.mark.parametrize(
    "case",
    ["not-dict", "missing-model", "wrong-type", "wrong-family", "unfitted", "classes", "encoder"],
)
def test_incompatible_fitted_model_rejected(saved_bundle, case):
    destination, input_path, output, _ = saved_bundle
    models = joblib.load(destination / "models.joblib")
    if case == "not-dict":
        models = []
    elif case == "missing-model":
        del models["xgboost"]
    elif case == "wrong-type":
        models["lr"] = "not-a-model"
    elif case == "wrong-family":
        models["lr"].pipeline = models["xgboost"].pipeline
    elif case == "unfitted":
        models["lr"].pipeline = Pipeline(
            [
                ("preprocess", make_preprocessor(scale=True)),
                ("model", LogisticRegression()),
            ]
        )
    elif case == "classes":
        models["lr"].pipeline.named_steps["model"].classes_ = np.array([1, 2])
    elif case == "encoder":
        encoder = models["lr"].pipeline.named_steps["preprocess"].named_transformers_["categorical"]
        encoder.handle_unknown = "error"
    _replace_models(destination, models)
    with pytest.raises(ValueError):
        predict_file(destination, input_path, output, "lr")
    assert not output.exists()


@pytest.mark.parametrize("synthetic", [True, False])
def test_completion_marker_requires_exact_saved_hash(saved_bundle, synthetic):
    destination, input_path, output, _ = saved_bundle
    metadata = _metadata(destination)
    metadata["synthetic_only"] = synthetic
    _replace_metadata(destination, metadata)
    marker = destination / "evaluation_complete.json"
    marker.write_text(json.dumps({"completed": True, "models_sha256": metadata["models_sha256"]}))
    predict_file(destination, input_path, output, "lr")
    kind = "synthetic" if synthetic else "retrospective"
    expected = f"{kind}-internal-evaluation-complete"
    assert get_column(pd.read_csv(output), "internal_validation_status").eq(expected).all()
    marker.write_text(json.dumps({"completed": True, "models_sha256": "wrong"}))
    with pytest.raises(ValueError, match="marker model hash"):
        predict_file(destination, input_path, output, "lr")


def test_metadata_records_units_bounds_versions_and_preserves_models(saved_bundle):
    destination, _, _, _ = saved_bundle
    metadata = _metadata(destination)
    assert metadata["models_sha256"] == file_hash(destination / "models.joblib")
    assert [item["name"] for item in metadata["schema"]] == list(FEATURES)
    assert metadata["schema"][0]["min"] == 18
    assert metadata["schema"][0]["max"] == 90
    assert set(metadata["runtime"]["packages"]) == {
        "numpy",
        "scipy",
        "scikit-learn",
        "xgboost",
        "pandas",
        "joblib",
    }
    for spec in metadata["schema"][3:]:
        reviewed = metadata["feature_mapping"]["labs"][spec["name"]]
        assert reviewed["units"][spec["canonical_unit"]] == 1
        assert (spec["min"], spec["max"]) == (reviewed["min"], reviewed["max"])
    before = file_hash(destination / "models.joblib")
    write_bundle_metadata(
        destination,
        endpoint="mortality",
        synthetic_only=True,
        review_status="synthetic-reviewed",
        feature_mapping=metadata["feature_mapping"],
    )
    assert file_hash(destination / "models.joblib") == before
    (destination / "freeze.json").write_text("{}")
    with pytest.raises(ValueError, match="frozen"):
        write_bundle_metadata(
            destination,
            endpoint="mortality",
            synthetic_only=True,
            review_status="synthetic-reviewed",
            feature_mapping=metadata["feature_mapping"],
        )


def test_output_cannot_overwrite_input_or_models(saved_bundle):
    destination, input_path, _, _ = saved_bundle
    before = file_hash(destination / "models.joblib")
    for output in (input_path, destination / "models.joblib", destination / "bundle.json"):
        with pytest.raises(ValueError, match="overwrite"):
            predict_file(destination, input_path, output, "lr")
    assert file_hash(destination / "models.joblib") == before


@pytest.mark.parametrize("name", ["lr", "xgboost"])
def test_fresh_process_cli_predicts_from_saved_bundle(saved_bundle, fitted_models, name):
    destination, input_path, output, frame = saved_bundle
    models, _ = fitted_models
    before = raw_scores(models[name], frame)
    calibrator = models[name].calibrator
    expected = expit(calibrator.intercept_[0] + calibrator.coef_[0, 0] * before)
    command = [
        sys.executable,
        "-m",
        "preop_xai.cli",
        "predict",
        "--bundle",
        str(destination),
        "--input",
        str(input_path),
        "--output",
        str(output),
        "--model",
        name,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = pd.read_csv(output)
    assert len(result) == 3
    np.testing.assert_allclose(result["raw_score"], before, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(result["calibrated_probability"], expected, rtol=1e-12, atol=1e-12)


def test_canonical_inputs_are_not_normalized_twice(saved_bundle, fitted_models):
    # Given: the reviewed source conversion is nonidentity, but inputs are canonical.
    destination, input_path, output, frame = saved_bundle
    metadata = _metadata(destination)
    mapping = metadata["feature_mapping"]
    mapping["labs"]["hemoglobin"]["units"] = {"g/L": 0.1}
    write_bundle_metadata(
        destination,
        endpoint="mortality",
        synthetic_only=True,
        review_status="synthetic-reviewed",
        feature_mapping=mapping,
    )
    # When: applying saved preprocessing to already canonical g/dL values.
    predict_file(destination, input_path, output, "lr")
    # Then: no second conversion changes the expected original-model logit.
    model = fitted_models[0]["lr"]
    result = pd.read_csv(output)
    np.testing.assert_allclose(result["raw_score"], raw_scores(model, frame), atol=1e-12)
