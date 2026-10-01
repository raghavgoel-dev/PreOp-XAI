"""Software and scientific readiness checks."""

import platform
import shutil
import sys
from enum import StrEnum, unique
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from preop_xai.config import AppConfig
from preop_xai.contracts import DataKind


@unique
class ReadinessStatus(StrEnum):
    """Status of one readiness prerequisite."""

    READY = "ready"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


class ReadinessCheck(BaseModel):
    """One non-sensitive readiness result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    name: str
    status: ReadinessStatus
    detail: str


class DoctorReport(BaseModel):
    """Machine-readable readiness matrix."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    software_ready: bool
    data_status: str
    checks: tuple[ReadinessCheck, ...]


def build_doctor_report(config: AppConfig) -> DoctorReport:
    """Inspect software readiness without exposing private values."""
    python_ready = sys.version_info[:2] == (3, 12)
    uv_ready = shutil.which("uv") is not None
    git_ready = shutil.which("git") is not None
    credential_status = {
        DataKind.SYNTHETIC: ReadinessStatus.NOT_REQUIRED,
        DataKind.REAL: ReadinessStatus.BLOCKED,
    }[config.data_kind]
    checks = (
        ReadinessCheck(
            name="python",
            status=ReadinessStatus.READY if python_ready else ReadinessStatus.BLOCKED,
            detail=f"Python {platform.python_version()} (requires 3.12)",
        ),
        ReadinessCheck(
            name="uv",
            status=ReadinessStatus.READY if uv_ready else ReadinessStatus.BLOCKED,
            detail="uv executable available" if uv_ready else "uv executable missing",
        ),
        ReadinessCheck(
            name="git",
            status=ReadinessStatus.READY if git_ready else ReadinessStatus.BLOCKED,
            detail=(
                "Git executable available" if git_ready else "Git executable missing"
            ),
        ),
        ReadinessCheck(
            name="credentials",
            status=credential_status,
            detail="Not required for synthetic-only foundation commands",
        ),
        ReadinessCheck(
            name="real_data",
            status=ReadinessStatus.BLOCKED,
            detail=("Local authenticated inventory and capability audit not completed"),
        ),
    )
    return DoctorReport(
        software_ready=python_ready and uv_ready and git_ready,
        data_status="REAL_DATA_PENDING",
        checks=checks,
    )
