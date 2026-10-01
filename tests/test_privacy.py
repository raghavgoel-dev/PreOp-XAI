from pathlib import Path

import pytest

from preop_xai.privacy import require_external_path, require_safe_text


def test_repository_internal_path_is_rejected(tmp_path: Path) -> None:
    # Given
    internal = tmp_path / "runs"

    # When / Then
    with pytest.raises(ValueError, match="external"):
        _ = require_external_path(internal, tmp_path)


def test_placeholder_path_is_rejected(tmp_path: Path) -> None:
    # Given
    placeholder = Path("<external-path>")

    # When / Then
    with pytest.raises(ValueError, match="placeholder"):
        _ = require_external_path(placeholder, tmp_path)


@pytest.mark.parametrize(
    "value",
    ["password=hunter2", "Authorization: Bearer abc", "api_key=secret"],
)
def test_secret_like_text_is_rejected(value: str) -> None:
    # Given / When / Then
    with pytest.raises(ValueError, match="credential"):
        _ = require_safe_text(value)
