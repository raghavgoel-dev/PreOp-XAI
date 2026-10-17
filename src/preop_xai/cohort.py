"""Canonical information adapter and outcome-independent index selection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl

from .audit import _get_column, _numeric_series, parse_times, scan_strings

IDENTITY = ["patient_id", "operation_id", "t0"]
REVIEW_GATES = (
    "age_numeric_years",
    "asa_mapping",
    "hospitalization_linkage",
    "anesthesia_boundary",
    "static_provenance",
)
INFORMATION_COLUMNS = {
    "MRN": "patient_id",
    "LOG_ID": "operation_id",
    "BIRTH_DATE": "age",
    "SEX": "sex",
    "ASA_RATING_C": "asa",
    "AN_START_DATETIME": "t0",
    "AN_STOP_DATETIME": "anesthesia_end",
    "HOSP_ADMSN_TIME": "admission_time",
    "HOSP_DISCH_TIME": "discharge_time",
    "DISCH_DISP_C": "disposition_code",
    "DISCH_DISP": "disposition",
}


def require_columns(frame: pd.DataFrame, columns) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing canonical columns: {sorted(missing)}")


def validate_identity(frame: pd.DataFrame) -> None:
    require_columns(frame, IDENTITY)
    if frame[IDENTITY].isna().to_numpy().any():
        raise ValueError("Canonical identity contains missing values")
    for column in ("patient_id", "operation_id"):
        if frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Empty {column}")
        if frame[column].duplicated().any():
            raise ValueError(f"Expected one indexed row per {column}")


def load_information(raw_dir: Path) -> pd.DataFrame:
    lf = scan_strings(Path(raw_dir) / "patient_information.csv")
    result = (
        lf.select([pl.col(source).alias(target) for source, target in INFORMATION_COLUMNS.items()])
        .collect(engine="streaming")
        .to_pandas()
    )
    for column in ("t0", "anesthesia_end", "admission_time", "discharge_time"):
        result[column] = parse_times(_get_column(result, column))
    # Explicitly unreviewed; callers must supply a documented external review.
    result.attrs["review"] = {}
    return result


def build_cohort(information: pd.DataFrame) -> pd.DataFrame:
    """Quarantine conflicting operations, then index first eligible operation.

    Review metadata is supplied externally in information.attrs["review"].
    ASA values must already have been translated to canonical classes 1--6.
    """
    require_columns(information, INFORMATION_COLUMNS.values())
    review = information.attrs.get("review", {})
    missing = [name for name in REVIEW_GATES if review.get(name) is not True]
    if missing:
        raise ValueError(f"External clinical review required: {', '.join(missing)}")

    data = information.copy().drop_duplicates()
    exclusions: list[pd.DataFrame] = []

    def remove(mask, reason):
        nonlocal data
        rejected = data.loc[mask, IDENTITY].copy()
        rejected["reason"] = reason
        exclusions.append(rejected)
        data = data.loc[~mask].copy()

    remove(
        data[["patient_id", "operation_id"]].isna().any(axis=1)
        | data["patient_id"].astype(str).str.strip().eq("")
        | data["operation_id"].astype(str).str.strip().eq(""),
        "missing_identity",
    )
    # Exact duplicates were removed across every field, not a clinical subset.
    remove(data["operation_id"].duplicated(keep=False), "operation_conflict")
    for column in ("t0", "anesthesia_end", "admission_time", "discharge_time"):
        data[column] = pd.to_datetime(data[column], errors="coerce")
    data["age"] = _numeric_series(_get_column(data, "age"), errors="coerce")
    asa = _numeric_series(_get_column(data, "asa"), errors="coerce")
    remove(data["age"].isna() | ~data["age"].between(18, float("inf")), "not_adult")
    asa = asa.loc[data.index]
    remove(
        asa.eq(6).fillna(False) | (asa.notna() & ~asa.isin([1, 2, 3, 4, 5, 6])),
        "invalid_or_donor_asa",
    )
    data["asa"] = _numeric_series(_get_column(data, "asa")).astype("Int64").astype("string")
    valid = data["t0"].notna() & (data["anesthesia_end"] > data["t0"])
    remove(~valid, "invalid_anesthesia_boundary")
    data = data.sort_values(["patient_id", "t0", "operation_id"], kind="stable")
    first_time = data.groupby("patient_id")["t0"].transform("min")
    tied_first = data.loc[data["t0"].eq(first_time)].duplicated("patient_id", keep=False)
    ambiguous_patients = data.loc[data["t0"].eq(first_time)].loc[tied_first, "patient_id"]
    remove(data["patient_id"].isin(ambiguous_patients), "ambiguous_first_operation_time")
    remove(data["patient_id"].duplicated(), "later_eligible_operation")
    result = data.reset_index(drop=True)
    validate_identity(result)
    result.attrs["review"] = dict(review)
    result.attrs["exclusions"] = pd.concat(exclusions, ignore_index=True)
    return result
