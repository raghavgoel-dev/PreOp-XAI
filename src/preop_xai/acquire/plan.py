"""Safe download-plan construction."""

from pathlib import PurePosixPath
from re import fullmatch
from typing import ClassVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from preop_xai.acquire.inventory import AuthenticatedInventory
from preop_xai.acquire.paths import require_safe_relative_path

OFFICIAL_HOST = "physionet.org"


def require_official_url(url: str) -> None:
    """Require credential-free HTTPS on the official host and port."""
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        message = "inventory URL must use HTTPS on the official host"
        raise ValueError(message) from error
    valid_url = (
        parsed.scheme == "https"
        and parsed.hostname == OFFICIAL_HOST
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
    )
    if not valid_url:
        message = "inventory URL must use HTTPS on the official host"
        raise ValueError(message)


class DownloadPlanEntry(BaseModel):
    """One verified download target."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    logical_role: str
    relative_path: PurePosixPath
    url: str
    size_bytes: int = Field(gt=0)
    sha256: str


class DownloadPlan(BaseModel):
    """Versioned download plan."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    release: str
    entries: tuple[DownloadPlanEntry, ...]


def build_download_plan(inventory: AuthenticatedInventory) -> DownloadPlan:
    """Validate official-host inventory entries and build a plan."""
    entries: list[DownloadPlanEntry] = []
    for item in inventory.files:
        relative_path = require_safe_relative_path(item.relative_path)
        require_official_url(item.url)
        if fullmatch(r"[0-9a-f]{64}", item.sha256) is None:
            message = "inventory SHA-256 must be 64 lowercase hexadecimal characters"
            raise ValueError(message)
        entries.append(
            DownloadPlanEntry(
                logical_role=item.logical_role,
                relative_path=relative_path,
                url=item.url,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
            )
        )
    return DownloadPlan(release=inventory.release, entries=tuple(entries))
