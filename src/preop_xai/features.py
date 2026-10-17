"""Preoperative laboratory selection with candidate-level provenance."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from .audit import _get_column, _numeric_series, scan_strings
from .cohort import IDENTITY, require_columns, validate_identity

LABS = (
    "hemoglobin",
    "platelets",
    "creatinine",
    "bun",
    "sodium",
    "potassium",
    "glucose",
)
FEATURES = ("age", "sex", "asa") + LABS
DEFAULT_COLUMNS = {
    "patient_id": "MRN",
    "operation_id": "LOG_ID",
    "collection_time": "RESULT_TIME",
    "lab_name": "LAB_NAME",
    "value": "ORD_VALUE",
    "unit": "RESULT_UNIT",
}
PROVENANCE_COLUMNS = IDENTITY + [
    "concept",
    "lab_name",
    "raw_value",
    "unit",
    "collection_time",
    "result_time",
    "normalized_value",
    "reason",
    "selected",
]


def _validate_config(config):
    if config.get("reviewed") is not True:
        raise ValueError("Lab identity, specimen, unit and plausibility maps need review")
    availability = config.get("availability")
    if availability not in ("strict", "collection_proxy"):
        raise ValueError("availability must be strict or collection_proxy")
    if availability == "collection_proxy" and config.get("proxy_lag_hours") != 24:
        raise ValueError("Explicit proxy_lag_hours: 24 is required")
    mapping = config.get("labs", {})
    if set(mapping) != set(LABS):
        raise ValueError(f"labs must contain exactly {LABS}")
    owners = {}
    for concept, spec in mapping.items():
        if not spec.get("names") or not spec.get("units"):
            raise ValueError(f"{concept} requires exact names and unit factors")
        if not np.isfinite([spec["min"], spec["max"]]).all():
            raise ValueError(f"{concept}: finite plausibility bounds required")
        if spec["min"] >= spec["max"]:
            raise ValueError(f"{concept}: invalid plausibility bounds")
        for factor in spec["units"].values():
            if not np.isfinite(factor) or factor <= 0:
                raise ValueError(f"{concept}: unit factors must be positive and finite")
        for name in spec["names"]:
            if name in owners:
                raise ValueError(f"Ambiguous or repeated lab name: {name}")
            owners[name] = concept
    return owners


def load_labs(raw_dir: Path, cohort, feature_config) -> pd.DataFrame:
    """Project and semi-join lazily before collecting the compact candidate table.

    Rejected timestamps remain available for provenance. RESULT_TIME is only a
    collection proxy by default, never silently treated as release time.
    """
    owners = _validate_config(feature_config)
    validate_identity(cohort)
    columns = DEFAULT_COLUMNS | feature_config.get("columns", {})
    if feature_config["availability"] == "strict" and "result_time" not in columns:
        raise ValueError("Strict mode requires an explicit release-time column map")
    lf = scan_strings(Path(raw_dir) / feature_config.get("file", "patient_labs.csv"))
    missing = set(columns.values()) - set(lf.collect_schema().names())
    if missing:
        raise ValueError(f"Inspect lab headers and configure columns; missing {sorted(missing)}")
    lf = lf.select([pl.col(source).alias(target) for target, source in columns.items()])
    keys = pl.from_pandas(cohort[IDENTITY]).lazy()
    candidates = (
        lf.filter(pl.col("lab_name").is_in(list(owners)))
        .join(keys, on=["patient_id", "operation_id"], how="inner")
        .with_columns(
            pl.coalesce(
                [
                    pl.col("collection_time").str.strptime(pl.Datetime, fmt, strict=False)
                    for fmt in (
                        "%m/%d/%y %H:%M",
                        "%m/%d/%y %H:%M:%S",
                        "%Y-%m-%d %H:%M:%S%.f",
                        "%Y-%m-%dT%H:%M:%S%.f",
                        "%Y-%m-%d",
                    )
                ]
            ).alias("_collection")
        )
    )
    upper = pl.col("t0")
    if feature_config["availability"] == "collection_proxy":
        upper = upper - pl.duration(hours=24)
    candidates = candidates.with_columns(
        pl.col("_collection")
        .is_between(pl.col("t0") - pl.duration(days=30), upper, closed="both")
        .fill_null(False)
        .alias("_in_window")
    )
    counts = (
        candidates.select(
            pl.len().alias("mapped_candidates"),
            (~pl.col("_in_window")).sum().alias("rejected_time_window"),
        )
        .collect(engine="streaming")
        .to_dicts()[0]
    )
    result = (
        candidates.filter(pl.col("_in_window"))
        .drop("t0", "_collection", "_in_window")
        .collect(engine="streaming")
        .to_pandas()
    )
    result.attrs["raw_selection_counts"] = counts
    return result


def build_features(cohort, labs, feature_config) -> tuple[pd.DataFrame, pd.DataFrame]:
    owners = _validate_config(feature_config)
    validate_identity(cohort)
    require_columns(cohort, list(FEATURES[:3]))
    require_columns(
        labs, ["patient_id", "operation_id", "collection_time", "lab_name", "value", "unit"]
    )
    strict = feature_config["availability"] == "strict"
    if strict:
        require_columns(labs, ["result_time"])
    wide = cohort[IDENTITY + list(FEATURES[:3])].copy().reset_index(drop=True)
    # Cohort exclusions are a separate private table, not serializable model metadata.
    wide.attrs = {}
    for concept in LABS:
        wide[concept] = np.nan

    candidates = labs.merge(
        cohort[IDENTITY],
        on=["patient_id", "operation_id"],
        how="inner",
        validate="many_to_one",
    )
    records = []
    for row in candidates.to_dict("records"):
        concept = owners.get(row["lab_name"])
        if concept is None:
            continue
        spec = feature_config["labs"][concept]
        collection = pd.to_datetime(row["collection_time"], errors="coerce")
        release = pd.to_datetime(row.get("result_time"), errors="coerce")
        value = _numeric_series(pd.Series([row["value"]]), errors="coerce").iloc[0]
        factor = spec["units"].get(row["unit"])
        normalized = value * factor if factor is not None else np.nan
        cutoff = row["t0"]
        reason = "eligible"
        if pd.isna(collection):
            reason = "missing_collection_time"
        elif collection < cutoff - pd.Timedelta(days=30):
            reason = "before_lookback"
        elif collection > cutoff:
            reason = "future_collection"
        elif not strict and collection > cutoff - pd.Timedelta(hours=24):
            reason = "proxy_lag"
        elif strict and pd.isna(release):
            reason = "missing_release_time"
        elif strict and release < collection:
            reason = "release_before_collection"
        elif strict and release > cutoff:
            reason = "future_release"
        elif factor is None:
            reason = "unknown_unit"
        elif not np.isfinite(value):
            reason = "nonnumeric_or_nonfinite"
        elif not spec["min"] <= normalized <= spec["max"]:
            reason = "implausible"
        records.append(
            {
                **{key: row[key] for key in IDENTITY},
                "concept": concept,
                "lab_name": row["lab_name"],
                "raw_value": row["value"],
                "unit": row["unit"],
                "collection_time": collection,
                "result_time": release,
                "normalized_value": normalized,
                "reason": reason,
                "selected": False,
            }
        )
    provenance = pd.DataFrame(records, columns=PROVENANCE_COLUMNS)
    if len(provenance):
        eligible = provenance.loc[provenance["reason"].eq("eligible")]
        for (patient, operation, concept), group in eligible.groupby(
            ["patient_id", "operation_id", "concept"], sort=True
        ):
            latest = group["collection_time"].max()
            tied = group.loc[group["collection_time"].eq(latest)]
            provenance.loc[group.index, "reason"] = "older_eligible"
            if tied["normalized_value"].nunique() != 1:
                provenance.loc[tied.index, "reason"] = "conflicting_latest"
                continue
            # Identical numerical ties produce the same feature; source selection
            # is deterministic even if input row order changes.
            chosen = (
                tied.assign(
                    _tie=tied[["lab_name", "unit", "raw_value"]]
                    .astype(str)
                    .agg("\x1f".join, axis=1)
                )
                .sort_values("_tie", kind="stable")
                .index[0]
            )
            provenance.loc[tied.index, "reason"] = "equivalent_latest"
            provenance.loc[chosen, ["reason", "selected"]] = ["selected", True]
            wide.loc[
                wide["patient_id"].eq(patient) & wide["operation_id"].eq(operation),
                concept,
            ] = provenance.loc[chosen, "normalized_value"]
    audit_leakage(cohort, wide, provenance, feature_config)
    return wide, provenance


def audit_leakage(cohort, features, provenance, feature_config) -> None:
    _validate_config(feature_config)
    validate_identity(cohort)
    validate_identity(features)
    if list(features.columns) != IDENTITY + list(FEATURES):
        raise ValueError("Feature table contains unexpected columns or ordering")
    expected = cohort[IDENTITY].reset_index(drop=True)
    actual = features[IDENTITY].reset_index(drop=True)
    if not expected.equals(actual):
        raise ValueError("Feature identities differ from indexed cohort")
    require_columns(provenance, PROVENANCE_COLUMNS)
    selected = provenance.loc[provenance["selected"].eq(True)].copy()
    if not selected["reason"].eq("selected").all():
        raise ValueError("Selected provenance has rejection reasons")
    if selected.duplicated(IDENTITY + ["concept"]).any():
        raise ValueError("Multiple selected observations per concept")
    if not selected["concept"].isin(LABS).all():
        raise ValueError("Unknown selected concept")
    linked = selected.merge(
        cohort[IDENTITY],
        on=IDENTITY,
        how="left",
        indicator=True,
        validate="many_to_one",
    )
    if not linked["_merge"].eq("both").all():
        raise ValueError("Unlinked selected provenance")
    for row in selected.itertuples(index=False):
        lower = row.t0 - pd.Timedelta(days=30)
        upper = row.t0
        if feature_config["availability"] == "collection_proxy":
            upper -= pd.Timedelta(hours=24)
        if pd.isna(row.collection_time) or not lower <= row.collection_time <= upper:
            raise ValueError("Selected observation violates collection window")
        if feature_config["availability"] == "strict":
            if pd.isna(row.result_time) or not row.collection_time <= row.result_time <= row.t0:
                raise ValueError("Selected observation violates release availability")
        spec = feature_config["labs"][row.concept]
        if row.lab_name not in spec["names"] or row.unit not in spec["units"]:
            raise ValueError("Selected lab has an unreviewed identity/unit")
        raw = _numeric_series(pd.Series([row.raw_value]), errors="coerce").iloc[0]
        normalized = raw * spec["units"][row.unit]
        if (
            not np.isfinite(normalized)
            or not spec["min"] <= normalized <= spec["max"]
            or not np.isclose(normalized, row.normalized_value)
        ):
            raise ValueError("Selected value violates conversion/plausibility")
    for concept in LABS:
        evidence = selected.loc[selected["concept"].eq(concept)]
        values = features[IDENTITY + [concept]].merge(
            evidence[IDENTITY + ["normalized_value"]],
            on=IDENTITY,
            how="left",
            validate="one_to_one",
        )
        if not np.allclose(
            np.asarray(_numeric_series(_get_column(values, concept)).to_numpy(), dtype=float),
            np.asarray(_get_column(values, "normalized_value").to_numpy(), dtype=float),
            equal_nan=True,
        ):
            raise ValueError(f"{concept}: feature differs from selection provenance")
    for concept in FEATURES[:3]:
        if (
            not features[concept]
            .reset_index(drop=True)
            .equals(cohort[concept].reset_index(drop=True))
        ):
            raise ValueError(f"Static feature changed: {concept}")
