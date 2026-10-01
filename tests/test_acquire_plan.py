import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from preop_xai.acquire.inventory import load_inventory
from preop_xai.acquire.plan import build_download_plan


def test_inventory_requires_authenticated_metadata_fields(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "inventory.json"
    _ = path.write_text(
        json.dumps({"release": "1.4.2", "files": [{"logical_role": "operations"}]}),
        encoding="utf-8",
    )

    # When / Then
    with pytest.raises(ValidationError):
        _ = load_inventory(str(path))


def test_plan_rejects_non_official_or_unsafe_inventory_entry(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "inventory.json"
    _ = path.write_text(
        json.dumps(
            {
                "release": "1.4.2",
                "files": [
                    {
                        "logical_role": "operations",
                        "relative_path": "../escape.csv",
                        "url": "https://example.invalid/escape.csv",
                        "size_bytes": 10,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inventory = load_inventory(str(path))

    # When / Then
    with pytest.raises(ValueError, match=r"unsafe|official"):
        _ = build_download_plan(inventory)


@pytest.mark.parametrize(
    "url",
    [
        "https://user@physionet.org/files/inspire/table.csv",
        "https://physionet.org:8443/files/inspire/table.csv",
    ],
)
def test_plan_rejects_credential_or_nonstandard_port_url(
    tmp_path: Path,
    url: str,
) -> None:
    # Given
    path = tmp_path / "inventory.json"
    _ = path.write_text(
        json.dumps(
            {
                "release": "1.4.2",
                "files": [
                    {
                        "logical_role": "operations",
                        "relative_path": "release/table.csv",
                        "url": url,
                        "size_bytes": 10,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # When / Then
    with pytest.raises(ValueError, match="official"):
        _ = build_download_plan(load_inventory(str(path)))
