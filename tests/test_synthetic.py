import polars as pl

from preop_xai.contracts import DataKind
from preop_xai.synthetic.generator import generate_synthetic


def test_synthetic_fixture_is_seed_deterministic() -> None:
    # Given / When
    first = generate_synthetic(seed=41, rows=12)
    second = generate_synthetic(seed=41, rows=12)

    # Then
    assert first.operations.equals(second.operations)
    assert first.labs.equals(second.labs)
    assert first.labels.equals(second.labels)


def test_synthetic_fixture_is_labeled_and_uses_synthetic_ids() -> None:
    # Given / When
    dataset = generate_synthetic(seed=5, rows=8)

    # Then
    assert dataset.operations.filter(
        pl.col("data_kind") != DataKind.SYNTHETIC
    ).is_empty()
    assert dataset.operations.filter(
        ~pl.col("patient_id").str.starts_with("SYN-")
    ).is_empty()
