"""Read-only numerical report tables from completed evaluation artifacts."""

from pathlib import Path

import numpy as np

from preop_xai.result_bins import calibration_bins
from preop_xai.result_curves import curve_tables, ranking_row
from preop_xai.result_io import ArtifactTables, Json, Row, load_json
from preop_xai.result_operating import check_count, check_metric, operating_tables

_COLUMNS: dict[str, str] = {
    "discrimination_calibration.csv": (
        "endpoint,partition,model,variant,n,events,nonevents,prevalence,auroc,average_precision,"
        "brier,training_prevalence_brier,test_prevalence_brier_reference,offset_intercept,"
        "joint_intercept,joint_slope,calibration_diagnostic_status,calibration_status,"
        "probability_use,evidence_kind"
    ),
    "operating_point.csv": (
        "endpoint,partition,model,n,events,nonevents,threshold,threshold_source,tp,fp,tn,fn,"
        "sensitivity,specificity,ppv,npv,accuracy,f1,predicted_positives,"
        "predicted_positive_fraction,predicted_positives_per_10000,calibration_status,"
        "classification_use,evidence_kind"
    ),
    "confusion_counts.csv": (
        "endpoint,model,true_class,predicted_class,count,threshold,calibration_status"
    ),
    "roc_points.csv": "endpoint,model,variant,point_index,fpr,tpr,threshold,threshold_kind",
    "pr_points.csv": "endpoint,model,variant,point_index,recall,precision,threshold,threshold_kind",
    "calibration_bins_fixed.csv": (
        "endpoint,model,variant,bin_id,lower,upper,n,events,nonevents,mean_predicted,"
        "observed_fraction,empty,calibration_status"
    ),
    "calibration_bins_quantile.csv": (
        "endpoint,model,variant,bin_id,lower,upper,n,events,nonevents,mean_predicted,"
        "observed_fraction,empty,calibration_status"
    ),
}
TABLE_FIELDS: dict[str, list[str]] = {
    name: columns.split(",") for name, columns in _COLUMNS.items()
}


def numerical_tables(directory: Path, endpoint: str, evidence_kind: str) -> ArtifactTables:
    """Return aggregates without writing, refitting, or loading model/partition data."""
    metrics = load_json(directory / "metrics.json")
    with np.load(directory / "predictions.npz", allow_pickle=False) as archive:
        if not {"y", "names", "probabilities"}.issubset(archive.files):
            raise ValueError("predictions.npz requires y, names and probabilities arrays.")
        y, names, probability = archive["y"], archive["names"], archive["probabilities"]
    if y.ndim != 1 or not len(y) or y.dtype.kind not in "biuf" or not np.isin(y, [0, 1]).all():
        raise ValueError("Saved y must be a nonempty one-dimensional binary array.")
    if (
        names.ndim != 1
        or names.dtype.kind != "U"
        or any(not name for name in names)
        or len(set(names.tolist())) != len(names)
    ):
        raise ValueError("Saved names must be a one-dimensional array of unique nonempty strings.")
    if probability.shape != (len(names), len(y)):
        raise ValueError("Saved probability shapes must align with names and y.")
    if (
        probability.dtype.kind not in "iuf"
        or not np.isfinite(probability).all()
        or np.any((probability < 0) | (probability > 1))
    ):
        raise ValueError("Saved probabilities must be finite numbers in [0, 1].")
    n, events = len(y), int(y.sum())
    check_count(metrics.get("n"), n, "n")
    check_count(metrics.get("events"), events, "events")
    check_metric(metrics.get("prevalence"), events / n, "prevalence")
    if "endpoint" in metrics and metrics["endpoint"] != endpoint:
        raise ValueError("Requested endpoint disagrees with metrics endpoint.")
    partition = metrics.get("partition", "test")
    if partition != "test":
        raise ValueError("Completed numerical exports require the test partition.")
    models = metrics.get("models")
    if not isinstance(models, dict) or not models:
        raise ValueError("metrics.json requires a nonempty models mapping.")
    tables: dict[str, list[Row]] = {filename: [] for filename in TABLE_FIELDS}
    unavailable: list[Row] = []
    expected_names: set[str] = set()
    for model, source in models.items():
        if not isinstance(model, str) or not model or not isinstance(source, dict):
            raise ValueError("Each model must have a nonempty name and metric mapping.")
        expected_names.add(f"{model}_raw")
        status = source.get("calibration_status")
        available = status in {"fitted", "nonpositive-slope"}
        if available != (source.get("calibrated") is not None):
            raise ValueError(f"{model}: calibrated metrics disagree with calibration availability.")
        if available:
            expected_names.add(f"{model}_calibrated")
        else:
            if not isinstance(status, str) or not status:
                raise ValueError(f"{model}: calibration status is required.")
            for key in (
                "threshold",
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
                "calibration",
            ):
                if source.get(key) is not None:
                    raise ValueError(f"{model}: unavailable calibration has a nonnull {key}.")
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "model": model,
                    "variant": "calibrated",
                    "artifact": "calibrated",
                    "reason": status,
                }
            )
    if expected_names != set(names.tolist()):
        raise ValueError("Saved names do not match model/variant availability in metrics.json.")
    by_name = dict(zip(names.tolist(), probability, strict=True))
    quantile_metadata: dict[str, Json] = {}
    diagnostics: dict[str, Json] = {}
    interval_metadata: dict[str, Json] = {}
    operating_models: list[str] = []
    for model, source in models.items():
        status = source["calibration_status"]
        available = source["calibrated"] is not None
        for variant in ("raw", "calibrated"):
            if variant == "calibrated" and not available:
                continue
            name = f"{model}_{variant}"
            p = by_name[name]
            identity: Row = {"endpoint": endpoint, "model": model, "variant": variant}
            row, diagnostic = ranking_row(
                y,
                p,
                source,
                {**identity, "partition": partition, "evidence_kind": evidence_kind},
            )
            row["prevalence"] = metrics["prevalence"]
            tables["discrimination_calibration.csv"].append(row)
            diagnostics[name] = {
                "offset_intercept": diagnostic["offset_intercept"],
                "joint_intercept": diagnostic["joint_intercept"],
                "joint_slope": diagnostic["joint_slope"],
                "converged": diagnostic["converged"],
                "status": diagnostic["status"],
            }
            roc, pr, missing = curve_tables(y, p, identity)
            tables["roc_points.csv"].extend(roc)
            tables["pr_points.csv"].extend(pr)
            unavailable.extend(missing)
            fixed, quantile, bin_metadata = calibration_bins(
                y, p, {**identity, "calibration_status": status}
            )
            tables["calibration_bins_fixed.csv"].extend(fixed)
            tables["calibration_bins_quantile.csv"].extend(quantile)
            quantile_metadata[name] = bin_metadata
        if available:
            row, confusion = operating_tables(
                y,
                by_name[f"{model}_calibrated"],
                source,
                {
                    "endpoint": endpoint,
                    "partition": partition,
                    "model": model,
                    "evidence_kind": evidence_kind,
                },
            )
            tables["operating_point.csv"].append(row)
            tables["confusion_counts.csv"].extend(confusion)
            operating_models.append(model)
    expected_intervals = [f"{model}.calibrated.accuracy" for model in operating_models]
    if len(models) == len(operating_models) == 2:
        expected_intervals.append(
            f"paired_{operating_models[1]}_minus_{operating_models[0]}.calibrated.accuracy"
        )
    for key in expected_intervals:
        present = key in metrics.get("intervals", {})
        interval_metadata[key] = {
            "status": "available" if present else "unavailable",
            "reason": None if present else "Source has no accuracy interval; not reconstructed.",
        }
    metadata: dict[str, Json] = {
        "partition": partition,
        "fixed_bins": {
            "strategy": "fixed-width",
            "requested_bin_count": 5,
            "effective_bin_count": 5,
            "edges": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            "closure": "[lower, upper), except final [0.8, 1]",
            "retain_empty": True,
        },
        "quantile_bins": quantile_metadata,
        "calibration_diagnostics": diagnostics,
        "roc": {"drop_intermediate": False, "infinity_threshold": "null; positive_infinity"},
        "pr": {"summary": "average_precision", "terminal_threshold": "null; none"},
        "threshold_policy": "frozen validation threshold; predicted event when p >= threshold",
        "accuracy_intervals": interval_metadata,
        "intervals": "Copy source intervals.csv unchanged; no bootstrap in exporter.",
        "unavailable_reasons": [dict(row) for row in unavailable],
    }
    return {"tables": tables, "metadata": metadata, "unavailable": unavailable}
