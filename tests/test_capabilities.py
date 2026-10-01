from preop_xai.capabilities import foundation_capabilities
from preop_xai.contracts import CapabilityStatus, DataKind


def test_synthetic_manifest_supports_only_mortality() -> None:
    # Given / When
    manifest = foundation_capabilities(DataKind.SYNTHETIC)

    # Then
    assert manifest.mortality.status is CapabilityStatus.SUPPORTED
    assert manifest.composite.status is CapabilityStatus.UNSUPPORTED
    assert manifest.chronology.status is CapabilityStatus.UNSUPPORTED
