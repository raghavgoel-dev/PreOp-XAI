import hashlib
from pathlib import Path, PurePosixPath

import polars as pl
import pytest

from preop_xai.acquire.prepare import TableMapping, prepare_mapped_tables


def test_prepare_never_mutates_raw(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    derived_root = tmp_path / "derived"
    raw = raw_root / "verified" / "table.csv"
    raw.parent.mkdir(parents=True)
    _ = raw.write_text("operation_id,value\nSYN-OP-1,3\n", encoding="utf-8")
    before = hashlib.sha256(raw.read_bytes()).hexdigest()
    mapping = TableMapping(
        logical_role="operations",
        relative_path=PurePosixPath("verified/table.csv"),
        format="csv",
    )

    # When
    outputs = prepare_mapped_tables((mapping,), raw_root, derived_root)

    # Then
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == before
    assert outputs == (derived_root / "operations.parquet",)
    assert pl.scan_parquet(outputs[0]).collect().height == 1


def test_prepare_rejects_logical_role_output_escape(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    derived_root = tmp_path / "derived"
    raw = raw_root / "verified" / "table.csv"
    raw.parent.mkdir(parents=True)
    _ = raw.write_text("operation_id,value\nSYN-OP-1,3\n", encoding="utf-8")
    mapping = TableMapping(
        logical_role="../escape",
        relative_path=PurePosixPath("verified/table.csv"),
        format="csv",
    )

    # When / Then
    with pytest.raises(ValueError, match="unsafe"):
        _ = prepare_mapped_tables((mapping,), raw_root, derived_root)
    assert not (tmp_path / "escape.parquet").exists()
