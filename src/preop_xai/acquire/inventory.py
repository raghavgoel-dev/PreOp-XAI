"""Authenticated inventory contracts."""

from pathlib import Path, PurePosixPath
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class InventoryFile(BaseModel):
    """One authenticated release file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    logical_role: str
    relative_path: PurePosixPath
    url: str
    size_bytes: int = Field(gt=0)
    sha256: str


class AuthenticatedInventory(BaseModel):
    """Researcher-supplied authenticated release inventory."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    release: str
    files: tuple[InventoryFile, ...]


def load_inventory(path: str) -> AuthenticatedInventory:
    """Parse an authenticated inventory JSON file."""
    return AuthenticatedInventory.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )
