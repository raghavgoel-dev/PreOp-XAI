from preop_xai.audit import AuditEvidence, audit_capabilities
from preop_xai.contracts import CapabilityStatus, DataKind


def test_audit_keeps_real_mortality_blocked_without_linkage_and_timing() -> None:
    # Given
    evidence = AuditEvidence(
        data_kind=DataKind.REAL,
        mortality_linkage_verified=True,
        mortality_timing_verified=False,
    )

    # When
    manifest = audit_capabilities(evidence)

    # Then
    assert manifest.mortality.status is CapabilityStatus.BLOCKED


def test_audit_records_supported_endpoint_matrix() -> None:
    # Given
    evidence = AuditEvidence(
        data_kind=DataKind.REAL,
        mortality_linkage_verified=True,
        mortality_timing_verified=True,
        acute_kidney_injury_supported=True,
        chronology_valid=True,
    )

    # When
    manifest = audit_capabilities(evidence)

    # Then
    assert manifest.mortality.status is CapabilityStatus.SUPPORTED
    assert manifest.acute_kidney_injury.status is CapabilityStatus.SUPPORTED
    assert manifest.early_icu_admission.status is CapabilityStatus.UNSUPPORTED
    assert manifest.chronology.status is CapabilityStatus.SUPPORTED
