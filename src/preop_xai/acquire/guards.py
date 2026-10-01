"""Cross-artifact acquisition consistency guards."""

from preop_xai.acquire.plan import DownloadPlan
from preop_xai.acquire.prepare import TableMapping
from preop_xai.contracts import DataKind


def require_release(actual: str, expected: str) -> None:
    """Reject an artifact from a different configured release."""
    if actual != expected:
        message = (
            f"artifact release {actual} does not match configured release {expected}"
        )
        raise ValueError(message)


def require_data_kind(actual: DataKind, expected: DataKind) -> None:
    """Reject evidence for a different configured data kind."""
    if actual is not expected:
        message = (
            f"evidence data kind {actual.value} does not match configured "
            f"data kind {expected.value}"
        )
        raise ValueError(message)


def require_verified_mappings(
    mappings: tuple[TableMapping, ...],
    manifest: DownloadPlan,
) -> None:
    """Require every mapped source to appear in the verification manifest."""
    verified_paths = {entry.relative_path for entry in manifest.entries}
    unverified = tuple(
        mapping.relative_path
        for mapping in mappings
        if mapping.relative_path not in verified_paths
    )
    if unverified:
        message = f"mapped sources are not verified: {', '.join(map(str, unverified))}"
        raise ValueError(message)
