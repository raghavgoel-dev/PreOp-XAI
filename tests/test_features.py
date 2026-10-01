from datetime import UTC, datetime, timedelta

import polars as pl

from preop_xai.features import build_features

START = datetime(2025, 1, 31, 8, tzinfo=UTC)


def test_labels_reject_inputs_not_verified_before_operation_start() -> None:
    # Given
    cohort = pl.DataFrame(
        {
            "patient_id": ["p1"],
            "operation_id": ["op-1"],
            "operation_start": [START],
            "age_years": [50],
            "asa_class": [2],
        }
    )
    observations = pl.DataFrame(
        {
            "operation_id": ["op-1"] * 4,
            "logical_test": ["verified_pre", "at_cutoff", "post", "unverified_pre"],
            "value": [1.0, 2.0, 3.0, 4.0],
            "available_at": [
                START - timedelta(seconds=1),
                START,
                START + timedelta(seconds=1),
                START - timedelta(hours=1),
            ],
            "availability_verified": [True, True, True, False],
        }
    )

    # When
    result = build_features(
        cohort,
        observations,
        strict_days=30,
        proxy_days=30,
    )

    # Then
    assert "verified_pre" in result.strict.columns
    assert "at_cutoff" not in result.strict.columns
    assert "post" not in result.strict.columns
    assert "unverified_pre" not in result.strict.columns


def test_strict_feature_set_excludes_proxy_variables() -> None:
    # Given
    cohort = pl.DataFrame(
        {
            "patient_id": ["p1"],
            "operation_id": ["op-1"],
            "operation_start": [START],
            "age_years": [50],
            "asa_class": [2],
        }
    )
    observations = pl.DataFrame(
        {
            "operation_id": ["op-1", "op-1"],
            "logical_test": ["strict_lab", "proxy_lab"],
            "value": [1.0, 2.0],
            "available_at": [START - timedelta(hours=2)] * 2,
            "availability_verified": [True, False],
        }
    )

    # When
    result = build_features(
        cohort,
        observations,
        strict_days=30,
        proxy_days=30,
    )

    # Then
    assert "proxy_lab" not in result.strict.columns
    assert result.proxy.get_column("proxy_lab").to_list() == [2.0]
    assert result.manifest.proxy_only_features == ("proxy_lab",)


def test_features_use_latest_value_in_window_and_keep_empty_operations() -> None:
    # Given
    cohort = pl.DataFrame(
        {
            "patient_id": ["p1", "p2"],
            "operation_id": ["op-1", "op-2"],
            "operation_start": [START, START],
            "age_years": [50, 60],
            "asa_class": [2, 3],
        }
    )
    observations = pl.DataFrame(
        {
            "operation_id": ["op-1", "op-1", "op-1"],
            "logical_test": ["creatinine"] * 3,
            "value": [9.0, 1.0, 1.5],
            "available_at": [
                START - timedelta(days=31),
                START - timedelta(days=2),
                START - timedelta(days=1),
            ],
            "availability_verified": [True, True, True],
        }
    )

    # When
    result = build_features(
        cohort,
        observations,
        strict_days=30,
        proxy_days=30,
    )

    # Then
    assert result.strict.get_column("operation_id").to_list() == ["op-1", "op-2"]
    assert result.strict.get_column("creatinine").to_list() == [1.5, None]
