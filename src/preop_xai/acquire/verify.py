"""Downloaded-file verification."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import override

from preop_xai.acquire.paths import resolve_under_root
from preop_xai.acquire.plan import DownloadPlan


@dataclass(frozen=True, slots=True)
class VerificationFailure(ValueError):  # noqa: N818
    """A file failed its authenticated size or hash contract."""

    relative_path: str
    reason: str

    @override
    def __str__(self) -> str:
        """Render the failed path and verification reason."""
        return f"{self.relative_path}: {self.reason}"


def verify_downloads(
    plan: DownloadPlan,
    raw_root: Path,
    quarantine_root: Path,
) -> tuple[Path, ...]:
    """Verify all planned files and quarantine mismatches."""
    verified: list[Path] = []
    for entry in plan.entries:
        target = resolve_under_root(raw_root, entry.relative_path)
        if not target.is_file():
            raise VerificationFailure(
                relative_path=str(entry.relative_path),
                reason="missing file",
            )
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        valid = (
            target.stat().st_size == entry.size_bytes
            and digest.hexdigest() == entry.sha256
        )
        if not valid:
            quarantine = resolve_under_root(quarantine_root, entry.relative_path)
            quarantine.parent.mkdir(parents=True, exist_ok=True)
            _ = target.replace(quarantine)
            raise VerificationFailure(
                relative_path=str(entry.relative_path),
                reason="size or SHA-256 mismatch",
            )
        verified.append(target)
    return tuple(verified)
