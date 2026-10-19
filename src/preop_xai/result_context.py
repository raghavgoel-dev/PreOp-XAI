"""Select aggregate campaign context without reading source patient tables."""

from __future__ import annotations

import json
from pathlib import Path

from preop_xai.result_io import Row, aggregate_path, load_json


def explanation_figures(source: Path, endpoint: str) -> tuple[list[tuple[Path, str]], list[Row]]:
    """Select only safe existing aggregate explanation references."""
    path = source / endpoint / "explain.json"
    if not path.is_file():
        return [], [
            {
                "endpoint": endpoint,
                "role": "aggregate_explanation_figures",
                "reason": "source explain.json unavailable; no SHAP recomputation",
            }
        ]
    result = []
    unavailable: list[Row] = []
    for relative in load_json(path).get("figures", []):
        candidate = aggregate_path(source / endpoint, relative)
        if candidate.suffix.lower() != ".png":
            raise ValueError(f"Unsupported aggregate explanation figure: {relative}")
        if candidate.is_file():
            result.append((candidate, f"{endpoint}/source_figures/{relative}"))
        else:
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "role": relative,
                    "reason": "source aggregate figure unavailable",
                }
            )
    return result, unavailable


def campaign_summary(source: Path) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    consumed: list[str] = []

    def read(relative: str):
        path = source / relative
        if path.is_file():
            consumed.append(relative)
            return load_json(path)
        return {}

    def add(section: str, metric: str, value, denominator: str, unit: str = "count") -> None:
        rows.append(
            {
                "section": section,
                "metric": metric,
                "value": value,
                "denominator": denominator,
                "unit": unit,
                "availability": "available" if value is not None else "unavailable",
                "reason": None
                if value is not None
                else "not recorded in source aggregate evidence",
            }
        )

    audit = read("audit/audit.json")
    for table, data in audit.get("tables", {}).items():
        add("source-audit", f"{table}.rows", data.get("rows"), "source table rows")
        for key, counts in data.get("keys", {}).items():
            for metric in ("distinct", "nulls"):
                add("source-audit", f"{table}.{key}.{metric}", counts.get(metric), "source rows")
        for group in ("duplicate_operations", "timestamps"):
            for key, count in data.get(group, {}).items():
                add("source-audit", f"{table}.{group}.{key}", count, "overlapping source-row flags")
    cohort = read("cohort_flow.json")
    add("cohort", "information_rows", cohort.get("information_rows"), "source operation rows")
    add("cohort", "indexed_patients", cohort.get("indexed_patients"), "indexed patients")
    for reason, count in cohort.get("exclusions", {}).items():
        add(
            "cohort-exclusions", reason, count, "excluded operation rows; not a patient subtraction"
        )
    assessability = read("assessability.json")
    for endpoint in ("mortality", "respiratory"):
        for quantity in ("assessable", "unknown", "events"):
            add(
                endpoint,
                quantity,
                assessability.get(endpoint, {}).get(quantity),
                "indexed patients",
            )
    splits = read("split_counts.json")
    for partition in ("train", "validation", "test"):
        for endpoint in ("mortality", "respiratory"):
            for quantity in ("n", "events"):
                add(
                    endpoint,
                    f"{partition}.{quantity}",
                    splits.get(partition, {}).get(endpoint, {}).get(quantity),
                    f"{partition} assessable patients",
                )
    status = read("status.json")
    for key in ("pipeline_execution", "data_review", "clinical_use"):
        add("status", key, status.get(key), "campaign", "status")
    for endpoint, details in status.get("endpoints", {}).items():
        for key in ("review", "internal_validation", "predictive_reliability"):
            add(endpoint, key, details.get(key), "endpoint", "status")
        selection = read(f"{endpoint}/selection.json")
        for model, details in selection.items():
            add(
                endpoint,
                f"{model}.cv_average_precision",
                details.get("cv_score"),
                "training CV",
                "AP",
            )
            add(
                endpoint,
                f"{model}.selected_parameters",
                json.dumps(details.get("parameters"), sort_keys=True),
                "training CV",
                "settings",
            )
        calibration = read(f"{endpoint}/calibration.json")
        for model, diagnostic in calibration.items():
            for key in (
                "calibration_n",
                "calibration_events",
                "calibration_nonevents",
                "calibration_status",
                "calibration_intercept",
                "calibration_slope",
            ):
                add(
                    endpoint,
                    f"{model}.{key}",
                    diagnostic.get(key),
                    "validation patients",
                    "diagnostic",
                )
        explanation = read(f"{endpoint}/explain.json")
        for model, details in explanation.get("models", {}).items():
            for key in ("raw_additivity", "calibrated_logit_additivity"):
                add(endpoint, f"{model}.{key}", details.get(key), "explanation patients", "boolean")
        stability = read(f"{endpoint}/stability.json")
        for model, details in stability.get("models", {}).items():
            add(
                endpoint,
                f"{model}.successful_paired_refits",
                details.get("successful_refits"),
                "requested paired refits",
            )
        bundle = read(f"{endpoint}/bundle.json")
        for key in ("artifact_version", "data_review_status"):
            add(endpoint, f"bundle.{key}", bundle.get(key), "source bundle metadata", "status")
        mapping = bundle.get("feature_mapping", {})
        for key in ("availability", "proxy_lag_hours", "reviewed", "synthetic_only"):
            add(
                endpoint,
                f"feature_mapping.{key}",
                mapping.get(key),
                "source mapping metadata",
                "setting",
            )
        for feature in bundle.get("schema", []):
            add(
                endpoint,
                f"feature_unit.{feature['name']}",
                feature.get("canonical_unit"),
                "source feature schema",
                "unit",
            )
    for quantity in ("measured_runtime_seconds", "measured_peak_memory_bytes"):
        add("resources", quantity, None, "campaign", "unavailable without a measurement receipt")
    return rows, consumed
