"""Contain authenticated inventory paths beneath private storage roots."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import override


@dataclass(frozen=True, slots=True)
class UnsafeRelativePathError(ValueError):
    """An authenticated inventory path escaped its configured root."""

    relative_path: str

    @override
    def __str__(self) -> str:
        """Render the unsafe path without inspecting private content."""
        return f"unsafe relative path: {self.relative_path}"


def require_safe_relative_path(relative_path: PurePosixPath) -> PurePosixPath:
    """Reject absolute paths and parent traversal."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise UnsafeRelativePathError(relative_path=str(relative_path))
    return relative_path


def resolve_under_root(root: Path, relative_path: PurePosixPath) -> Path:
    """Resolve a safe inventory path beneath a private root."""
    safe = require_safe_relative_path(relative_path)
    target = root.joinpath(*safe.parts).resolve()
    resolved_root = root.resolve()
    if resolved_root not in target.parents:
        raise UnsafeRelativePathError(relative_path=str(relative_path))
    return target
