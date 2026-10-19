"""Adversarial saved-evidence and operating arithmetic export contracts."""

import numpy as np
import pytest

from preop_xai.evaluate import _operating as evaluation_operating
from preop_xai.result_numerics import numerical_tables
from preop_xai.result_operating import operating_counts
from tests.result_assertions import mapping, number
from tests.result_numeric_fixture import replace_metrics, saved_evaluation


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "unknown",
        "missing",
        "shape",
        "y-shape",
        "binary",
        "nan",
        "infinity",
        "negative",
        "above-one",
        "object",
    ],
)
def test_invalid_saved_arrays_are_rejected(tmp_path, case):
    _, arrays = saved_evaluation(tmp_path)
    if case == "duplicate":
        arrays["names"][:] = "lr_raw"
    elif case == "unknown":
        arrays["names"][0] = "unknown"
    elif case == "missing":
        arrays["names"] = arrays["names"][:1]
        arrays["probabilities"] = arrays["probabilities"][:1]
    elif case == "shape":
        arrays["probabilities"] = arrays["probabilities"].T
    elif case == "y-shape":
        arrays["y"] = arrays["y"][:, None]
    elif case == "binary":
        arrays["y"] = arrays["y"].astype(float)
        arrays["y"][0] = 0.5
    elif case == "object":
        arrays["names"] = arrays["names"].astype(object)
    else:
        arrays["probabilities"][0, 0] = {
            "nan": np.nan,
            "infinity": np.inf,
            "negative": -0.01,
            "above-one": 1.01,
        }[case]
    np.savez(
        tmp_path / "predictions.npz",
        y=arrays["y"],
        names=arrays["names"],
        probabilities=arrays["probabilities"],
    )
    with pytest.raises(ValueError):
        numerical_tables(tmp_path, "mortality", "synthetic")


@pytest.mark.parametrize(
    "field",
    [
        "n",
        "events",
        "prevalence",
        "auroc",
        "average_precision",
        "brier",
        "tp",
        "fp",
        "tn",
        "fn",
        "sensitivity",
        "specificity",
        "ppv",
        "npv",
        "f1",
        "accuracy",
        "predicted_positives",
        "predicted_positive_fraction",
        "predicted_positives_per_10000",
    ],
)
def test_source_metrics_and_operating_counts_must_agree_with_arrays(tmp_path, field):
    metrics, _ = saved_evaluation(tmp_path)
    if field in {"n", "events", "prevalence"}:
        value = metrics[field]
        assert isinstance(value, (int, float))
        metrics[field] = value + 1
    elif field in {"auroc", "average_precision", "brier"}:
        raw = mapping(mapping(mapping(metrics["models"])["lr"])["raw"])
        raw[field] = number(raw[field]) + 0.01
    else:
        model = mapping(mapping(metrics["models"])["lr"])
        model[field] = number(model.get(field, 0)) + 1
    replace_metrics(tmp_path, metrics)
    with pytest.raises(ValueError, match="disagrees"):
        numerical_tables(tmp_path, "mortality", "synthetic")


@pytest.mark.parametrize(
    "case", ["availability", "invalid-label", "fallback", "threshold", "endpoint", "nonfinite-json"]
)
def test_invalid_calibration_policy_and_source_metadata_are_rejected(tmp_path, case):
    metrics, _ = saved_evaluation(tmp_path)
    model = mapping(mapping(metrics["models"])["lr"])
    if case == "availability":
        model["calibrated"] = None
    elif case == "invalid-label":
        model["calibration_status"] = "nonpositive-slope"
    elif case == "fallback":
        model["calibration_status"] = "constant-scores"
    elif case == "threshold":
        model["threshold"] = 1.01
    elif case == "endpoint":
        metrics["endpoint"] = "respiratory"
    else:
        mapping(model["raw"])["brier"] = float("nan")
    replace_metrics(tmp_path, metrics)
    with pytest.raises(ValueError):
        numerical_tables(tmp_path, "mortality", "synthetic")


def test_non_test_partition_is_rejected_and_legacy_defaults_to_test(tmp_path):
    metrics, _ = saved_evaluation(tmp_path)
    assert numerical_tables(tmp_path, "mortality", "synthetic")["metadata"]["partition"] == "test"
    metrics["partition"] = "validation"
    replace_metrics(tmp_path, metrics)
    with pytest.raises(ValueError, match="test partition"):
        numerical_tables(tmp_path, "mortality", "synthetic")


def test_exporter_never_fits_loads_models_or_reads_partitions(tmp_path, monkeypatch):
    saved_evaluation(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("export attempted fitting or reading models/partitions")

    monkeypatch.setattr("joblib.load", forbidden)
    monkeypatch.setattr("pandas.read_parquet", forbidden)
    monkeypatch.setattr("sklearn.linear_model.LogisticRegression.fit", forbidden)
    monkeypatch.setattr("preop_xai.evaluate.calibration_parameters", forbidden)
    original_load = np.load
    calls = []

    def safe_load(*args, **kwargs):
        calls.append(kwargs["allow_pickle"])
        return original_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", safe_load)
    assert numerical_tables(tmp_path, "mortality", "synthetic")["tables"]["roc_points.csv"]
    assert calls == [False]


@pytest.mark.parametrize(
    "counts,rates,alerts",
    [
        ((89, 3188, 6712, 11), (0.8900, 0.6780, 0.0272, 0.9984, 0.6801, 0.0527), 3277),
        ((80, 1842, 8058, 20), (0.8000, 0.8139, 0.0416, 0.9975, 0.8138, 0.0791), 1922),
        ((619, 2267, 6933, 181), (0.7738, 0.7536, 0.2145, 0.9746, 0.7552, 0.3359), 2886),
        ((628, 1890, 7310, 172), (0.7850, 0.7946, 0.2494, 0.9770, 0.7938, 0.3785), 2518),
    ],
)
def test_four_report_illustrations_are_arithmetic_only(counts, rates, alerts):
    # These are confusion-arithmetic checks, not saved project performance fixtures.
    tp, fp, tn, fn = counts
    y = np.r_[np.ones(tp), np.zeros(fp), np.zeros(tn), np.ones(fn)]
    probability = np.r_[np.ones(tp + fp), np.zeros(tn + fn)]
    actual = operating_counts(y, probability, 0.5)
    evaluation = evaluation_operating(y, probability, 0.5)
    assert tuple(actual[k] for k in ("tp", "fp", "tn", "fn")) == counts
    for key, expected in zip(
        ("sensitivity", "specificity", "ppv", "npv", "accuracy", "f1"), rates, strict=True
    ):
        assert round(number(actual[key]), 4) == expected
        assert evaluation[key] == actual[key]
    assert actual["predicted_positives"] == alerts
    assert actual["predicted_positives_per_10000"] == alerts
    assert actual["predicted_positive_fraction"] == alerts / 10000
