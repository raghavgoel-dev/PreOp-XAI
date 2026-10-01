"""Local scientific capability audit."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from preop_xai.capabilities import (
    Capability,
    CapabilityManifest,
    foundation_capabilities,
)
from preop_xai.contracts import CapabilityStatus, DataKind


class AuditEvidence(BaseModel):
    """Researcher-verified logical-role and timing evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    data_kind: DataKind
    mortality_linkage_verified: bool = False
    mortality_timing_verified: bool = False
    acute_kidney_injury_supported: bool = False
    early_icu_admission_supported: bool = False
    prolonged_invasive_support_supported: bool = False
    chronology_valid: bool = False


def audit_capabilities(evidence: AuditEvidence) -> CapabilityManifest:
    """Derive endpoint support only from explicit local evidence."""
    if evidence.data_kind is DataKind.SYNTHETIC:
        return foundation_capabilities(evidence.data_kind)

    def capability(*, supported: bool, blocked: bool = False) -> Capability:
        if blocked:
            return Capability(
                status=CapabilityStatus.BLOCKED,
                reason="Required local linkage or timing evidence is incomplete",
            )
        return Capability(
            status=(
                CapabilityStatus.SUPPORTED
                if supported
                else CapabilityStatus.UNSUPPORTED
            ),
            reason=(
                "Verified by local capability audit"
                if supported
                else "Not supported by local capability audit"
            ),
        )

    mortality_supported = (
        evidence.mortality_linkage_verified and evidence.mortality_timing_verified
    )
    return CapabilityManifest(
        data_kind=evidence.data_kind,
        mortality=capability(
            supported=mortality_supported,
            blocked=not mortality_supported,
        ),
        acute_kidney_injury=capability(
            supported=evidence.acute_kidney_injury_supported
        ),
        early_icu_admission=capability(
            supported=evidence.early_icu_admission_supported
        ),
        prolonged_invasive_support=capability(
            supported=evidence.prolonged_invasive_support_supported
        ),
        composite=Capability(
            status=CapabilityStatus.UNSUPPORTED,
            reason="Composite endpoint is disabled by protocol",
        ),
        chronology=capability(supported=evidence.chronology_valid),
    )
