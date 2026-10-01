"""Structural cohort selection before endpoint or feature filtering."""

from dataclasses import dataclass
from typing import ClassVar

import polars as pl
from pydantic import BaseModel, ConfigDict, NonNegativeInt

_REQUIRED_COLUMNS = frozenset(
    {"patient_id", "operation_id", "operation_start", "age_years"}
)
_REASON = "_cohort_exclusion_reason"


class CohortFlow(BaseModel):
    """Mutually exclusive row counts through structural cohort selection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    input_rows: NonNegativeInt
    selected_rows: NonNegativeInt
    excluded_invalid_key: NonNegativeInt
    excluded_invalid_time: NonNegativeInt
    excluded_unrepresentable_age: NonNegativeInt
    excluded_donor: NonNegativeInt
    excluded_asa6: NonNegativeInt
    excluded_later_operation: NonNegativeInt


@dataclass(frozen=True, slots=True)
class CohortResult:
    """Selected operations and aggregate structural flow counts."""

    cohort: pl.DataFrame
    flow: CohortFlow


def _require_columns(
    operations: pl.DataFrame,
    *,
    donor_field_verified: bool,
    asa_field_verified: bool,
) -> None:
    required = set(_REQUIRED_COLUMNS)
    if donor_field_verified:
        required.add("is_donor")
    if asa_field_verified:
        required.add("asa_class")
    missing = required.difference(operations.columns)
    if missing:
        message = f"Missing structural cohort columns: {', '.join(sorted(missing))}"
        raise ValueError(message)


def _reason_count(classified: pl.DataFrame, reason: str) -> int:
    return classified.filter(pl.col(_REASON) == reason).height


def build_cohort(
    operations: pl.DataFrame,
    *,
    donor_field_verified: bool = False,
    asa_field_verified: bool = False,
) -> CohortResult:
    """Select each patient's first structurally eligible released operation."""
    _require_columns(
        operations,
        donor_field_verified=donor_field_verified,
        asa_field_verified=asa_field_verified,
    )

    invalid_key = (
        pl.col("patient_id").is_null()
        | pl.col("operation_id").is_null()
        | (pl.col("patient_id").cast(pl.String).str.strip_chars() == "")
        | (pl.col("operation_id").cast(pl.String).str.strip_chars() == "")
    )
    invalid_time = pl.col("operation_start").is_null()
    if "operation_end" in operations.columns:
        invalid_time |= pl.col("operation_end").is_not_null() & (
            pl.col("operation_end") < pl.col("operation_start")
        )
    age = pl.col("age_years").cast(pl.Float64, strict=False)
    invalid_age = age.is_null() | ~age.is_finite() | (age < 0)
    donor = (
        pl.col("is_donor").cast(pl.Boolean, strict=False).fill_null(value=False)
        if donor_field_verified
        else pl.lit(value=False)
    )
    asa6 = (
        pl.col("asa_class").cast(pl.Int64, strict=False).eq(6)
        if asa_field_verified
        else pl.lit(value=False)
    )

    classified = operations.with_columns(
        pl.when(invalid_key)
        .then(pl.lit("invalid_key"))
        .when(invalid_time)
        .then(pl.lit("invalid_time"))
        .when(invalid_age)
        .then(pl.lit("unrepresentable_age"))
        .when(donor)
        .then(pl.lit("donor"))
        .when(asa6)
        .then(pl.lit("asa6"))
        .otherwise(pl.lit(None, dtype=pl.String))
        .alias(_REASON)
    )
    eligible = classified.filter(pl.col(_REASON).is_null()).drop(_REASON)
    cohort = (
        eligible.sort(["patient_id", "operation_start", "operation_id"])
        .group_by("patient_id", maintain_order=True)
        .first()
    )
    flow = CohortFlow(
        input_rows=operations.height,
        selected_rows=cohort.height,
        excluded_invalid_key=_reason_count(classified, "invalid_key"),
        excluded_invalid_time=_reason_count(classified, "invalid_time"),
        excluded_unrepresentable_age=_reason_count(classified, "unrepresentable_age"),
        excluded_donor=_reason_count(classified, "donor"),
        excluded_asa6=_reason_count(classified, "asa6"),
        excluded_later_operation=eligible.height - cohort.height,
    )
    return CohortResult(cohort=cohort, flow=flow)
