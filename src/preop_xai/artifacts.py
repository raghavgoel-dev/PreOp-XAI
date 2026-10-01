"""Synthetic artifact writer."""

import json
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from preop_xai.synthetic.generator import SyntheticDataset


class SyntheticManifest(BaseModel):
    """Synthetic artifact inventory."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    data_kind: Literal["synthetic"]
    rows: int
    tables: tuple[str, ...]


def write_synthetic_artifacts(dataset: SyntheticDataset, output_root: Path) -> Path:
    """Write synthetic tables and a manifest beneath an external run root."""
    run_path = output_root / "synthetic"
    run_path.mkdir(parents=True, exist_ok=True)
    dataset.operations.write_parquet(run_path / "operations.parquet")
    dataset.labs.write_parquet(run_path / "labs.parquet")
    dataset.labels.write_parquet(run_path / "labels.parquet")
    manifest = SyntheticManifest(
        data_kind="synthetic",
        rows=dataset.operations.height,
        tables=("operations.parquet", "labs.parquet", "labels.parquet"),
    )
    _ = (run_path / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_path
