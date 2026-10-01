"""Capability-gated endpoint label construction."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar

import polars as pl
from pydantic import BaseModel, ConfigDict

from preop_xai.capabilities import Capability, CapabilityManifest
from preop_xai.contracts import CapabilityStatus


@unique
class Endpoint(StrEnum):
    """Endpoint names exposed by the frozen protocol."""

    MORTALITY = "in_hospital_mortality"
    ACUTE_KIDNEY_INJURY = "acute_kidney_injury"
    EARLY_ICU_ADMISSION = "early_icu_admission"
    PROLONGED_INVASIVE_SUPPORT = "prolonged_invasive_support"
    COMPOSITE = "composite"


@unique
class LabelStatus(StrEnum):
    """Observed state of a supported binary endpoint."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class EndpointOmission(BaseModel):
    """Auditable reason an endpoint is absent from label rows."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    endpoint: Endpoint
    status: CapabilityStatus
    reason: str


@dataclass(frozen=True, slots=True)
class LabelsResult:
    """Primary endpoint labels and explicitly omitted endpoints."""

    labels: pl.DataFrame
    omissions: tuple[EndpointOmission, ...]


def _empty_labels() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "operation_id": pl.String,
            "endpoint": pl.String,
            "status": pl.String,
            "eligible": pl.Boolean,
            "reason": pl.String,
        }
    )


def _require_column(frame: pl.DataFrame, column: str, *, role: str) -> None:
    if column not in frame.columns:
        message = f"Missing {role} column: {column}"
        raise ValueError(message)


def _omission(endpoint: Endpoint, capability: Capability) -> EndpointOmission:
    return EndpointOmission(
        endpoint=endpoint,
        status=capability.status,
        reason=capability.reason,
    )


def _secondary_capabilities(
    capabilities: CapabilityManifest,
) -> tuple[tuple[Endpoint, Capability], ...]:
    return (
        (Endpoint.ACUTE_KIDNEY_INJURY, capabilities.acute_kidney_injury),
        (Endpoint.EARLY_ICU_ADMISSION, capabilities.early_icu_admission),
        (
            Endpoint.PROLONGED_INVASIVE_SUPPORT,
            capabilities.prolonged_invasive_support,
        ),
        (Endpoint.COMPOSITE, capabilities.composite),
    )


def build_labels(
    cohort: pl.DataFrame,
    outcomes: pl.DataFrame,
    capabilities: CapabilityManifest,
) -> LabelsResult:
    """Build mortality labels only when the capability audit supports them."""
    _require_column(cohort, "operation_id", role="cohort key")
    _require_column(outcomes, "operation_id", role="outcome key")

    secondary = _secondary_capabilities(capabilities)
    supported_secondary = [
        endpoint
        for endpoint, capability in secondary
        if capability.status is CapabilityStatus.SUPPORTED
    ]
    if supported_secondary:
        names = ", ".join(endpoint.value for endpoint in supported_secondary)
        message = f"Supported secondary endpoint mappings are not configured: {names}"
        raise ValueError(message)

    omissions = tuple(
        _omission(endpoint, capability)
        for endpoint, capability in secondary
        if capability.status is not CapabilityStatus.SUPPORTED
    )
    if capabilities.mortality.status is not CapabilityStatus.SUPPORTED:
        return LabelsResult(
            labels=_empty_labels(),
            omissions=(
                _omission(Endpoint.MORTALITY, capabilities.mortality),
                *omissions,
            ),
        )

    _require_column(
        outcomes,
        Endpoint.MORTALITY.value,
        role="supported mortality endpoint",
    )
    if outcomes.get_column("operation_id").n_unique() != outcomes.height:
        message = "Outcome keys must be unique before label construction"
        raise ValueError(message)

    value = pl.col(Endpoint.MORTALITY.value)
    valid = value.is_in([0, 1])
    labels = (
        cohort.select(pl.col("operation_id").cast(pl.String))
        .join(
            outcomes.select(
                pl.col("operation_id").cast(pl.String),
                Endpoint.MORTALITY.value,
            ),
            on="operation_id",
            how="left",
        )
        .select(
            "operation_id",
            pl.lit(Endpoint.MORTALITY.value).alias("endpoint"),
            pl.when(value == 1)
            .then(pl.lit(LabelStatus.POSITIVE.value))
            .when(value == 0)
            .then(pl.lit(LabelStatus.NEGATIVE.value))
            .otherwise(pl.lit(LabelStatus.UNKNOWN.value))
            .alias("status"),
            valid.fill_null(value=False).alias("eligible"),
            pl.when(valid.fill_null(value=False))
            .then(pl.lit(None, dtype=pl.String))
            .otherwise(pl.lit("Missing or invalid supported endpoint value"))
            .alias("reason"),
        )
    )
    return LabelsResult(labels=labels, omissions=omissions)
