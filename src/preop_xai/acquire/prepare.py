"""Immutable raw-to-Parquet preparation."""

from pathlib import Path, PurePosixPath
from typing import ClassVar, Literal

import polars as pl
from pydantic import BaseModel, ConfigDict

from preop_xai.acquire.paths import resolve_under_root


class TableMapping(BaseModel):
    """Researcher-verified logical table mapping."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    logical_role: str
    relative_path: PurePosixPath
    format: Literal["csv", "parquet"]


def prepare_mapped_tables(
    mappings: tuple[TableMapping, ...],
    raw_root: Path,
    derived_root: Path,
) -> tuple[Path, ...]:
    """Convert verified mapped tables without mutating raw inputs."""
    derived_root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for mapping in mappings:
        source = resolve_under_root(raw_root, mapping.relative_path)
        output = resolve_under_root(
            derived_root,
            PurePosixPath(f"{mapping.logical_role}.parquet"),
        )
        match mapping.format:
            case "csv":
                pl.scan_csv(source).sink_parquet(output)
            case "parquet":
                pl.scan_parquet(source).sink_parquet(output)
        outputs.append(output)
    return tuple(outputs)
