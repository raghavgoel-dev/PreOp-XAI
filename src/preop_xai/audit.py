"""Raw-source inspection. Outputs are restricted-data artifacts, not publications."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

import pandas as pd
import polars as pl


class _KeySummary(TypedDict):
    distinct: int
    nulls: int


class _Inventory(TypedDict):
    path: str
    columns: list[str]


class _DuplicateOperations(TypedDict):
    duplicated: int
    conflicting: int


class _TableSummary(TypedDict):
    sha256: str
    bytes: int
    schema: dict[str, str]
    rows: int
    keys: dict[str, _KeySummary]
    inventories: list[_Inventory]
    duplicate_operations: NotRequired[_DuplicateOperations]
    timestamps: NotRequired[dict[str, int]]


class _AuditReport(TypedDict):
    clinical_verification: bool
    tables: dict[str, _TableSummary]


def _get_column(frame: pd.DataFrame, name: str) -> pd.Series:
    column = frame[name]
    if not isinstance(column, pd.Series):
        raise ValueError(f"Expected a single column: {name}")
    return column


def _numeric_series(values: pd.Series, errors: Literal["raise", "coerce"] = "raise") -> pd.Series:
    result = pd.to_numeric(values, errors=errors)
    if not isinstance(result, pd.Series):
        raise TypeError("Expected numeric conversion to preserve Series")
    return result


def parse_times(values: pd.Series) -> pd.Series:
    """Parse documented source formats without date-only or locale guessing."""
    text = values.astype("string")
    parsed = pd.to_datetime(text, format="ISO8601", errors="coerce")
    for fmt in ("%m/%d/%y %H:%M", "%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M"):
        parsed = parsed.fillna(pd.to_datetime(text, format=fmt, errors="coerce"))
    return parsed


def scan_strings(path: Path) -> pl.LazyFrame:
    """Preserve literal 'None', identifiers and source codes without inference."""
    return pl.scan_csv(
        path,
        infer_schema=False,
        null_values=[""],
        try_parse_dates=False,
    )


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_raw(raw_dir: Path, output: Path) -> Path:
    """Inventory CSV sources without inferring clinical semantics."""
    raw_dir, output = Path(raw_dir), Path(output)
    required = (
        "patient_information.csv",
        "patient_labs.csv",
        "patient_post_op_complications.csv",
        "patient_procedure events.csv",
    )
    sources = [raw_dir / name for name in required if (raw_dir / name).is_file()]
    if not sources:
        sources = sorted(raw_dir.glob("*.csv"))
    if not sources:
        raise FileNotFoundError(f"No CSV sources in {raw_dir}")
    output.mkdir(parents=True, exist_ok=True)
    report: _AuditReport = {"clinical_verification": False, "tables": {}}
    inventory_fields = {
        "BIRTH_DATE",
        "SEX",
        "ASA_RATING_C",
        "ASA_RATING",
        "DISCH_DISP_C",
        "DISCH_DISP",
        "Element_Name",
        "Element_abbr",
        "CONTEXT_NAME",
        "SMRTDTA_ELEM_VALUE",
        "LAB_NAME",
        "RESULT_UNIT",
        "Lab Name",
        "Measurement Units",
        "Lab Code",
        "ENC_TYPE_NM",
        "EVENT_DISPLAY_NAME",
    }
    for path in sources:
        lf = scan_strings(path)
        columns = lf.collect_schema().names()
        summary: _TableSummary = {
            "sha256": _checksum(path),
            "bytes": path.stat().st_size,
            "schema": {name: "String" for name in columns},
            "rows": lf.select(pl.len()).collect(engine="streaming").item(),
            "keys": {},
            "inventories": [],
        }
        keys = [key for key in ("MRN", "LOG_ID") if key in columns]
        if keys:
            stats = (
                lf.select(
                    *[
                        expression
                        for key in keys
                        for expression in (
                            pl.col(key).drop_nulls().n_unique().alias(f"{key}_distinct"),
                            pl.col(key).null_count().alias(f"{key}_nulls"),
                        )
                    ]
                )
                .collect(engine="streaming")
                .to_dicts()[0]
            )
            summary["keys"] = {
                key: {"distinct": stats[f"{key}_distinct"], "nulls": stats[f"{key}_nulls"]}
                for key in keys
            }
        if "LOG_ID" in columns and path.name not in required[1:]:
            operations = (
                lf.filter(pl.col("LOG_ID").is_not_null())
                .group_by("LOG_ID")
                .agg(
                    pl.len().alias("rows"),
                    pl.struct(columns).n_unique().alias("distinct_records"),
                )
            )
            duplicates = (
                operations.select(
                    (pl.col("rows") > 1).sum().alias("duplicated"),
                    (pl.col("distinct_records") > 1).sum().alias("conflicting"),
                )
                .collect(engine="streaming")
                .to_dicts()[0]
            )
            summary["duplicate_operations"] = {
                "duplicated": duplicates["duplicated"],
                "conflicting": duplicates["conflicting"],
            }
        groups = [[c] for c in columns if c in inventory_fields]
        respiratory = [
            c
            for c in ("Element_Name", "Element_abbr", "CONTEXT_NAME", "SMRTDTA_ELEM_VALUE")
            if c in columns
        ]
        if respiratory:
            groups.append(respiratory)
        lab = [c for c in ("LAB_NAME", "RESULT_UNIT") if c in columns]
        if "Lab Name" in columns:
            lab = [c for c in ("Lab Name", "Measurement Units", "ENC_TYPE_NM") if c in columns]
        if len(lab) >= 2:
            groups.append(lab)
        if path.name == "patient_information.csv":
            info = lf.collect(engine="streaming").to_pandas()
            start = parse_times(_get_column(info, "AN_START_DATETIME"))
            end = parse_times(_get_column(info, "AN_STOP_DATETIME"))
            admission = parse_times(_get_column(info, "HOSP_ADMSN_TIME"))
            discharge = parse_times(_get_column(info, "HOSP_DISCH_TIME"))
            summary["timestamps"] = {
                "missing_or_invalid_start": int(start.isna().sum()),
                "midnight_start": int(start.eq(start.dt.normalize()).sum()),
                "invalid_end": int((end.isna() | end.le(start)).sum()),
                "admission_after_start": int(admission.gt(start).sum()),
                "discharge_before_end": int(discharge.lt(end).sum()),
            }
        for number, fields in enumerate(groups):
            name = f"{path.stem}.inventory-{number}.csv"
            lf.group_by(fields).len().sort(fields, nulls_last=True).collect(
                engine="streaming"
            ).write_csv(output / name)
            summary["inventories"].append({"path": name, "columns": fields})
        report["tables"][path.name] = summary
    destination = output / "audit.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination
