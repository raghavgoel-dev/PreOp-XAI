"""Numerical tables curves and calibration bins from saved evidence."""

import json

import numpy as np
import pytest

from preop_xai.result_numerics import TABLE_FIELDS, numerical_tables
from tests.result_assertions import mapping, number
from tests.result_numeric_fixture import DIAGNOSTIC, inventory, replace_metrics, saved_evaluation


def test_known_coordinates_operating_schemas_and_source_immutability(tmp_path):
    metrics, _ = saved_evaluation(tmp_path)
    before = inventory(tmp_path)
    result = numerical_tables(tmp_path, "mortality", "synthetic")
    assert inventory(tmp_path) == before
    assert set(result["tables"]) == {
        "discrimination_calibration.csv",
        "operating_point.csv",
        "confusion_counts.csv",
        "roc_points.csv",
        "pr_points.csv",
        "calibration_bins_fixed.csv",
        "calibration_bins_quantile.csv",
    }
    for filename, rows in result["tables"].items():
        assert all(list(row) == TABLE_FIELDS[filename] for row in rows)
    scores = result["tables"]["discrimination_calibration.csv"]
    assert list(scores[0]) == (
        "endpoint,partition,model,variant,n,events,nonevents,prevalence,auroc,"
        "average_precision,brier,training_prevalence_brier,test_prevalence_brier_reference,"
        "offset_intercept,joint_intercept,joint_slope,calibration_diagnostic_status,"
        "calibration_status,probability_use,evidence_kind"
    ).split(",")
    assert len(scores) == 2
    assert scores[0]["auroc"] == 0.875
    assert scores[0]["average_precision"] == pytest.approx(5 / 6)
    assert scores[0]["brier"] == 0.125
    assert scores[0]["training_prevalence_brier"] != 0.25
    assert scores[0]["test_prevalence_brier_reference"] == 0.25
    assert scores[0]["offset_intercept"] is None
    assert mapping(result["metadata"]["calibration_diagnostics"])["lr_raw"] == DIAGNOSTIC
    operating = result["tables"]["operating_point.csv"][0]
    assert list(operating) == (
        "endpoint,partition,model,n,events,nonevents,threshold,threshold_source,tp,fp,tn,fn,"
        "sensitivity,specificity,ppv,npv,accuracy,f1,predicted_positives,"
        "predicted_positive_fraction,predicted_positives_per_10000,calibration_status,"
        "classification_use,evidence_kind"
    ).split(",")
    assert [operating[k] for k in ("tp", "fp", "tn", "fn")] == [2, 1, 1, 0]
    assert operating["accuracy"] == 0.75
    assert operating["predicted_positives"] == 3
    assert operating["predicted_positive_fraction"] == 0.75
    assert operating["predicted_positives_per_10000"] == 7500
    assert operating["threshold_source"] == "validation"
    confusion = result["tables"]["confusion_counts.csv"]
    assert [(r["true_class"], r["predicted_class"], r["count"]) for r in confusion] == [
        (0, 0, 1),
        (0, 1, 1),
        (1, 0, 0),
        (1, 1, 2),
    ]
    roc = [r for r in result["tables"]["roc_points.csv"] if r["variant"] == "raw"]
    assert [r["fpr"] for r in roc] == [0.0, 0.0, 0.5, 1.0]
    assert [r["tpr"] for r in roc] == [0.0, 0.5, 1.0, 1.0]
    assert [r["threshold"] for r in roc] == [None, 1.0, 0.5, 0.0]
    assert roc[0]["threshold_kind"] == "positive_infinity"
    pr = [r for r in result["tables"]["pr_points.csv"] if r["variant"] == "raw"]
    assert [r["recall"] for r in pr] == [1.0, 1.0, 0.5, 0.0]
    assert [r["precision"] for r in pr] == pytest.approx([0.5, 2 / 3, 1.0, 1.0])
    assert pr[-1]["threshold"] is None
    assert pr[-1]["threshold_kind"] == "none"
    assert metrics["intervals"] == {}
    interval = mapping(mapping(result["metadata"]["accuracy_intervals"])["lr.calibrated.accuracy"])
    assert interval["status"] == "unavailable"
    json.dumps(result, allow_nan=False)


def test_named_array_permutation_preserves_models_and_variants(tmp_path):
    metrics, arrays = saved_evaluation(tmp_path, calibrated=[0.2, 0.4, 0.6, 0.8])
    second, other = saved_evaluation(
        tmp_path / "second", raw=[0.9, 0.6, 0.4, 0.1], calibrated=[0.8, 0.7, 0.3, 0.2]
    )
    metrics["models"] = {
        "second_model": mapping(second["models"])["lr"],
        "lr": mapping(metrics["models"])["lr"],
    }
    replace_metrics(tmp_path, metrics)
    probabilities = np.concatenate([arrays["probabilities"], other["probabilities"]])
    names = np.array(["lr_raw", "lr_calibrated", "second_model_raw", "second_model_calibrated"])
    np.savez(tmp_path / "predictions.npz", y=arrays["y"], names=names, probabilities=probabilities)
    expected = numerical_tables(tmp_path, "mortality", "synthetic")
    order = [3, 0, 2, 1]
    np.savez(
        tmp_path / "predictions.npz",
        y=arrays["y"],
        names=names[order],
        probabilities=probabilities[order],
    )
    assert numerical_tables(tmp_path, "mortality", "synthetic") == expected


@pytest.mark.parametrize(
    "probability",
    [np.linspace(0, 1, 101), np.repeat([0.0, 0.5, 1.0], [20, 60, 20]), np.full(20, 0.2)],
)
def test_bins_conserve_events_keep_empty_rows_and_ties_together(tmp_path, probability):
    y = np.arange(len(probability)) % 2
    saved_evaluation(tmp_path, y=y, raw=probability)
    result = numerical_tables(tmp_path, "mortality", "synthetic")
    for filename in ("calibration_bins_fixed.csv", "calibration_bins_quantile.csv"):
        for variant in ("raw", "calibrated"):
            rows = [r for r in result["tables"][filename] if r["variant"] == variant]
            assert sum(number(r["n"]) for r in rows) == len(y)
            assert sum(number(r["events"]) for r in rows) == int(y.sum())
            assert sum(number(r["nonevents"]) for r in rows) == len(y) - int(y.sum())
            for row in rows:
                assert row["empty"] == (row["n"] == 0)
                if row["empty"]:
                    assert row["mean_predicted"] is row["observed_fraction"] is None
            if filename.endswith("fixed.csv"):
                assert len(rows) == 5
                assert [r["lower"] for r in rows] == pytest.approx([0, 0.2, 0.4, 0.6, 0.8])
                assert rows[-1]["upper"] == 1.0
            else:
                if len(np.unique(probability)) == 1:
                    assert len(rows) == 1
                    assert rows[0]["lower"] == rows[0]["upper"] == 0.2
                for value in np.unique(probability):
                    containing = [
                        r
                        for r in rows
                        if (value >= r["lower"] if r["bin_id"] == 0 else value > r["lower"])
                        and value <= r["upper"]
                    ]
                    assert len(containing) == 1
    metadata = mapping(mapping(result["metadata"]["quantile_bins"])["lr_raw"])
    edges = metadata["edges"]
    assert isinstance(edges, list)
    assert metadata["requested_bin_count"] == 10
    assert metadata["effective_bin_count"] == max(1, len(edges) - 1)
    assert metadata["collapsed_edge_count"] == 11 - len(edges)


def test_fixed_probability_boundaries_and_null_empty_means(tmp_path):
    p = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    saved_evaluation(tmp_path, y=[0, 1, 0, 1, 0, 1], raw=p)
    rows = numerical_tables(tmp_path, "mortality", "synthetic")["tables"][
        "calibration_bins_fixed.csv"
    ]
    assert [r["n"] for r in rows if r["variant"] == "raw"] == [1, 1, 1, 1, 2]
    saved_evaluation(tmp_path, raw=np.full(4, 0.1))
    rows = numerical_tables(tmp_path, "mortality", "synthetic")["tables"][
        "calibration_bins_fixed.csv"
    ]
    assert [r["n"] for r in rows if r["variant"] == "raw"] == [4, 0, 0, 0, 0]


@pytest.mark.parametrize(
    "status", ["constant-scores", "insufficient-events", "separated-scores", "not-fitted"]
)
def test_unestimable_calibration_is_raw_only_without_identity_fallback(tmp_path, status):
    saved_evaluation(tmp_path, status=status)
    result = numerical_tables(tmp_path, "mortality", "synthetic")
    assert result["tables"]["operating_point.csv"] == []
    assert result["tables"]["confusion_counts.csv"] == []
    assert {r["variant"] for r in result["tables"]["roc_points.csv"]} == {"raw"}
    assert result["unavailable"] == [
        {
            "endpoint": "mortality",
            "model": "lr",
            "variant": "calibrated",
            "artifact": "calibrated",
            "reason": status,
        }
    ]


def test_nonpositive_calibration_retains_raw_and_invalid_calibrated_evidence(tmp_path):
    saved_evaluation(tmp_path, calibrated=[1.0, 0.5, 0.5, 0.0], status="nonpositive-slope")
    result = numerical_tables(tmp_path, "mortality", "synthetic")
    rows = result["tables"]["discrimination_calibration.csv"]
    assert rows[0]["auroc"] == 0.875
    assert rows[1]["auroc"] == 0.125
    assert rows[1]["calibration_status"] == "nonpositive-slope"
    assert rows[1]["probability_use"] == "invalid-diagnostic-only"
    assert result["tables"]["operating_point.csv"][0]["calibration_status"] == "nonpositive-slope"


@pytest.mark.parametrize("event", [0, 1])
def test_single_class_curves_are_unavailable_and_zero_denominators_are_null(tmp_path, event):
    saved_evaluation(tmp_path, y=np.full(4, event), raw=np.zeros(4))
    result = numerical_tables(tmp_path, "mortality", "synthetic")
    assert result["tables"]["roc_points.csv"] == result["tables"]["pr_points.csv"] == []
    assert len(result["unavailable"]) == 4
    assert {r["reason"] for r in result["unavailable"]} == {"single-class"}
    assert TABLE_FIELDS["roc_points.csv"] == (
        "endpoint,model,variant,point_index,fpr,tpr,threshold,threshold_kind"
    ).split(",")
    operating = result["tables"]["operating_point.csv"][0]
    assert operating["ppv"] is None
    assert operating["sensitivity" if event == 0 else "specificity"] is None
    assert operating["accuracy"] == 1 - event
    assert result["tables"]["discrimination_calibration.csv"][0]["auroc"] is None
    json.dumps(result, allow_nan=False)
