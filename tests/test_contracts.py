from datetime import UTC, datetime, timedelta

import pytest

from preop_xai.capabilities import foundation_capabilities
from preop_xai.contracts import (
    CapabilityStatus,
    DataKind,
    Observation,
    is_strictly_preoperative,
)


@pytest.mark.parametrize("offset", [timedelta(), timedelta(seconds=1)])
def test_availability_at_or_after_cutoff_is_excluded(offset: timedelta) -> None:
    # Given
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    observation = Observation(
        available_at=cutoff + offset,
        availability_verified=True,
    )

    # When
    result = is_strictly_preoperative(observation, cutoff)

    # Then
    assert result is False


def test_verified_availability_before_cutoff_is_included() -> None:
    # Given
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    observation = Observation(
        available_at=cutoff - timedelta(microseconds=1),
        availability_verified=True,
    )

    # When
    result = is_strictly_preoperative(observation, cutoff)

    # Then
    assert result is True


def test_unverified_availability_is_excluded() -> None:
    # Given
    observation = Observation(available_at=None, availability_verified=False)

    # When
    result = is_strictly_preoperative(
        observation,
        datetime(2026, 1, 1, tzinfo=UTC),
    )

    # Then
    assert result is False


def test_real_mortality_is_blocked_before_local_audit() -> None:
    # Given / When
    manifest = foundation_capabilities(DataKind.REAL)

    # Then
    assert manifest.mortality.status is CapabilityStatus.BLOCKED
