from datetime import UTC, datetime, timedelta

import polars as pl

from preop_xai.cohort import CohortFlow, build_cohort

START = datetime(2025, 1, 1, 8, tzinfo=UTC)


def test_cohort_selects_first_structurally_eligible_operation() -> None:
    # Given
    operations = pl.DataFrame(
        {
            "patient_id": ["p1", "p1", "p2"],
            "operation_id": ["first", "later", "only"],
            "operation_start": [START, START + timedelta(days=1), START],
            "age_years": [40, 40, 65],
            "feature_observed": [False, True, True],
            "outcome_observed": [False, True, True],
        }
    )

    # When
    result = build_cohort(operations)

    # Then
    assert result.cohort.get_column("operation_id").to_list() == ["first", "only"]
    assert result.flow == CohortFlow(
        input_rows=3,
        selected_rows=2,
        excluded_invalid_key=0,
        excluded_invalid_time=0,
        excluded_unrepresentable_age=0,
        excluded_donor=0,
        excluded_asa6=0,
        excluded_later_operation=1,
    )


def test_cohort_records_mutually_exclusive_structural_exclusions() -> None:
    # Given
    operations = pl.DataFrame(
        {
            "patient_id": ["", "p-time", "p-sequence", "p-age", "p-donor", "p-asa"],
            "operation_id": [
                "bad-key",
                "bad-time",
                "bad-sequence",
                "bad-age",
                "donor",
                "asa",
            ],
            "operation_start": [START, None, START, START, START, START],
            "operation_end": [
                START + timedelta(hours=1),
                START + timedelta(hours=1),
                START - timedelta(minutes=1),
                START + timedelta(hours=1),
                START + timedelta(hours=1),
                START + timedelta(hours=1),
            ],
            "age_years": [40, 40, 40, -1, 40, 40],
            "is_donor": [False, False, False, False, True, False],
            "asa_class": [2, 2, 2, 2, 2, 6],
        }
    )

    # When
    result = build_cohort(
        operations,
        donor_field_verified=True,
        asa_field_verified=True,
    )

    # Then
    assert result.cohort.is_empty()
    assert result.flow == CohortFlow(
        input_rows=6,
        selected_rows=0,
        excluded_invalid_key=1,
        excluded_invalid_time=2,
        excluded_unrepresentable_age=1,
        excluded_donor=1,
        excluded_asa6=1,
        excluded_later_operation=0,
    )
    assert sum(result.flow.model_dump().values()) - result.flow.input_rows == 6


def test_cohort_breaks_equal_time_ties_by_operation_id() -> None:
    # Given
    operations = pl.DataFrame(
        {
            "patient_id": ["p1", "p1", "p2"],
            "operation_id": ["op-b", "op-a", "op-c"],
            "operation_start": [START, START, START],
            "age_years": [30, 30, 50],
        }
    )

    # When
    result = build_cohort(operations)

    # Then
    assert result.cohort.get_column("operation_id").to_list() == ["op-a", "op-c"]
    assert result.cohort.get_column("patient_id").n_unique() == result.cohort.height
