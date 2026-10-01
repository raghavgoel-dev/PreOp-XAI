import hashlib
from pathlib import Path, PurePosixPath

import pytest

from preop_xai.acquire.plan import DownloadPlan, DownloadPlanEntry
from preop_xai.acquire.verify import VerificationFailure, verify_downloads


def test_verify_quarantines_size_or_hash_mismatch(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    quarantine = tmp_path / "quarantine"
    target = raw_root / "release" / "table.bin"
    target.parent.mkdir(parents=True)
    _ = target.write_bytes(b"wrong")
    entry = DownloadPlanEntry(
        logical_role="operations",
        relative_path=PurePosixPath("release/table.bin"),
        url="https://physionet.org/files/inspire/1.4.2/table.bin",
        size_bytes=7,
        sha256=hashlib.sha256(b"correct").hexdigest(),
    )
    plan = DownloadPlan(release="1.4.2", entries=(entry,))

    # When / Then
    with pytest.raises(VerificationFailure):
        _ = verify_downloads(plan, raw_root, quarantine)
    assert not target.exists()
    assert (quarantine / "release" / "table.bin").is_file()
