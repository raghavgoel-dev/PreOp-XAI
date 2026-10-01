"""Scientific contract types."""

from datetime import datetime
from enum import StrEnum, unique
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


@unique
class CapabilityStatus(StrEnum):
    """Scientific capability state."""

    SUPPORTED = "supported"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"


@unique
class DataKind(StrEnum):
    """Dataset provenance class."""

    SYNTHETIC = "synthetic"
    REAL = "real"


class Observation(BaseModel):
    """A result with its verified availability timestamp."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    available_at: datetime | None
    availability_verified: bool


def is_strictly_preoperative(observation: Observation, cutoff: datetime) -> bool:
    """Return whether a verified result was available strictly before cutoff."""
    if not observation.availability_verified or observation.available_at is None:
        return False
    return observation.available_at < cutoff
