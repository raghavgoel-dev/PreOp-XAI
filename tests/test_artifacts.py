from pathlib import Path

import polars as pl

from preop_xai.artifacts import SyntheticManifest, write_synthetic_artifacts
from preop_xai.synthetic.generator import generate_synthetic


def test_synthetic_artifacts_write_real_parquet_and_manifest(tmp_path: Path) -> None:
    # Given
    dataset = generate_synthetic(seed=8, rows=10)

    # When
    run_path = write_synthetic_artifacts(dataset, tmp_path)

    # Then
    manifest = SyntheticManifest.model_validate_json(
        (run_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.data_kind == "synthetic"
    assert manifest.rows == 10
    assert pl.scan_parquet(run_path / "operations.parquet").collect().height == 10
    assert (run_path / "labs.parquet").is_file()
    assert (run_path / "labels.parquet").is_file()
