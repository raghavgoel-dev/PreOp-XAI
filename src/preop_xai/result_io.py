"""Small aggregate artifact interchange shared by read-only exporters."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

Scalar = str | int | float | bool | None
Row = dict[str, Scalar]
Json = Scalar | Sequence["Json"] | Mapping[str, "Json"]


class ArtifactTables(TypedDict):
    tables: dict[str, list[Row]]
    metadata: dict[str, Json]
    unavailable: list[Row]


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_json(path: Path):
    def reject(value: str) -> None:
        raise ValueError(f"Non-standard JSON constant in {path.name}: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_table(path: Path, rows: list[Row], fields: Sequence[str] | None = None) -> None:
    """Preserve floating precision and represent unavailable values as empty cells."""
    columns = fields or list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_path(root: Path, relative: str) -> Path:
    """Reject absolute, escaping, private and symlink-escaping aggregate references."""
    portable = relative.replace("\\", "/")
    parts = portable.split("/")
    if (
        not relative
        or Path(relative).is_absolute()
        or ":" in portable
        or any(part.casefold() in {"", ".", "..", "private"} for part in parts)
    ):
        raise ValueError(f"Unsafe aggregate artifact path: {relative}")
    candidate = (root / portable).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"Aggregate artifact escapes directory: {relative}")
    if "private" in (part.casefold() for part in candidate.relative_to(root.resolve()).parts):
        raise ValueError(f"Private aggregate artifact path: {relative}")
    return candidate
