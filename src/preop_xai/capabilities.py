"""Capability manifest contracts."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from preop_xai.contracts import CapabilityStatus, DataKind


class Capability(BaseModel):
    """One endpoint or chronology capability."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    status: CapabilityStatus
    reason: str


class CapabilityManifest(BaseModel):
    """Auditable scientific capability matrix."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    data_kind: DataKind
    mortality: Capability
    acute_kidney_injury: Capability
    early_icu_admission: Capability
    prolonged_invasive_support: Capability
    composite: Capability
    chronology: Capability


def foundation_capabilities(data_kind: DataKind) -> CapabilityManifest:
    """Build the truthful pre-audit capability matrix."""
    mortality = {
        DataKind.SYNTHETIC: Capability(
            status=CapabilityStatus.SUPPORTED,
            reason="Synthetic mortality label generated for software validation",
        ),
        DataKind.REAL: Capability(
            status=CapabilityStatus.BLOCKED,
            reason="REAL_DATA_PENDING: local linkage and timing audit required",
        ),
    }[data_kind]

    conditional = Capability(
        status=CapabilityStatus.BLOCKED,
        reason="Local capability audit required",
    )
    unsupported = Capability(
        status=CapabilityStatus.UNSUPPORTED,
        reason="Not enabled by the frozen foundation protocol",
    )
    return CapabilityManifest(
        data_kind=data_kind,
        mortality=mortality,
        acute_kidney_injury=conditional,
        early_icu_admission=conditional,
        prolonged_invasive_support=conditional,
        composite=unsupported,
        chronology=unsupported,
    )
