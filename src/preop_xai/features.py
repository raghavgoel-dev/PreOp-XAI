"""Leakage-aware strict and proxy feature construction."""

from dataclasses import dataclass
from typing import ClassVar

import polars as pl
from pydantic import BaseModel, ConfigDict, NonNegativeInt

_COHORT_REQUIRED = frozenset({"operation_id", "operation_start"})
_OBSERVATION_REQUIRED = frozenset(
    {
        "operation_id",
        "logical_test",
        "value",
        "available_at",
        "availability_verified",
    }
)
_BASELINE_COLUMNS = ("patient_id", "operation_id", "age_years", "asa_class")
_IDENTIFIER_COLUMNS = frozenset({"patient_id", "operation_id"})


class FeatureManifest(BaseModel):
    """Counts and column identities for separate feature analyses."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    strict_observations: NonNegativeInt
    proxy_observations: NonNegativeInt
    strict_features: tuple[str, ...]
    proxy_features: tuple[str, ...]
    proxy_only_features: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeaturesResult:
    """Separate strict and proxy feature matrices with an audit manifest."""

    strict: pl.DataFrame
    proxy: pl.DataFrame
    manifest: FeatureManifest


def _require_columns(
    frame: pl.DataFrame,
    required: frozenset[str],
    *,
    role: str,
) -> None:
    missing = required.difference(frame.columns)
    if missing:
        message = f"Missing {role} columns: {', '.join(sorted(missing))}"
        raise ValueError(message)


def _feature_names(matrix: pl.DataFrame) -> tuple[str, ...]:
    return tuple(
        column for column in matrix.columns if column not in _IDENTIFIER_COLUMNS
    )


def _wide_matrix(
    cohort: pl.DataFrame,
    observations: pl.DataFrame,
) -> pl.DataFrame:
    baseline_columns = [
        column for column in _BASELINE_COLUMNS if column in cohort.columns
    ]
    baseline = cohort.select(baseline_columns)
    if observations.is_empty():
        return baseline

    latest = (
        observations.sort(
            ["operation_id", "logical_test", "available_at"],
            descending=[False, False, True],
        )
        .unique(
            subset=["operation_id", "logical_test"],
            keep="first",
            maintain_order=True,
        )
        .pivot(
            on="logical_test",
            index="operation_id",
            values="value",
            aggregate_function="first",
        )
    )
    matrix = baseline.join(latest, on="operation_id", how="left")
    feature_columns = sorted(set(matrix.columns).difference(baseline_columns))
    return matrix.select(*baseline_columns, *feature_columns)


def _within_window(days: int) -> pl.Expr:
    return (
        pl.col("available_at").is_not_null()
        & (pl.col("available_at") < pl.col("operation_start"))
        & (pl.col("available_at") >= pl.col("operation_start") - pl.duration(days=days))
    )


def build_features(
    cohort: pl.DataFrame,
    observations: pl.DataFrame,
    *,
    strict_days: int,
    proxy_days: int,
) -> FeaturesResult:
    """Build separate strict and timestamp-proxy feature matrices."""
    _require_columns(cohort, _COHORT_REQUIRED, role="cohort")
    _require_columns(observations, _OBSERVATION_REQUIRED, role="observation")
    if strict_days < 1 or proxy_days < 1:
        message = "Feature lookback windows must be positive"
        raise ValueError(message)
    if cohort.get_column("operation_id").n_unique() != cohort.height:
        message = "Cohort operation keys must be unique"
        raise ValueError(message)

    joined = observations.join(
        cohort.select("operation_id", "operation_start"),
        on="operation_id",
        how="inner",
    ).filter(
        pl.col("logical_test").is_not_null()
        & (pl.col("logical_test").cast(pl.String).str.strip_chars() != "")
    )
    verified = (
        pl.col("availability_verified")
        .cast(pl.Boolean, strict=False)
        .fill_null(value=False)
    )
    strict_observations = joined.filter(verified & _within_window(strict_days))
    proxy_observations = joined.filter(_within_window(proxy_days))
    strict = _wide_matrix(cohort, strict_observations)
    proxy = _wide_matrix(cohort, proxy_observations)
    strict_features = _feature_names(strict)
    proxy_features = _feature_names(proxy)
    manifest = FeatureManifest(
        strict_observations=strict_observations.height,
        proxy_observations=proxy_observations.height,
        strict_features=strict_features,
        proxy_features=proxy_features,
        proxy_only_features=tuple(
            sorted(set(proxy_features).difference(strict_features))
        ),
    )
    return FeaturesResult(strict=strict, proxy=proxy, manifest=manifest)
