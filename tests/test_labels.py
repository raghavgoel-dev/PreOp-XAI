import polars as pl

from preop_xai.audit import AuditEvidence, audit_capabilities
from preop_xai.capabilities import foundation_capabilities
from preop_xai.contracts import CapabilityStatus, DataKind
from preop_xai.labels import Endpoint, LabelStatus, build_labels


def test_supported_mortality_preserves_positive_negative_and_unknown() -> None:
    # Given
    cohort = pl.DataFrame(
        {
            "operation_id": ["op-1", "op-2", "op-3", "op-4"],
            "predictor_observed": [True, False, True, False],
        }
    )
    outcomes = pl.DataFrame(
        {
            "operation_id": ["op-1", "op-2", "op-3", "op-4"],
            "in_hospital_mortality": [1, 0, None, 2],
            "predictor_available_at_cutoff": [True, True, True, True],
        }
    )

    # When
    result = build_labels(
        cohort,
        outcomes,
        foundation_capabilities(DataKind.SYNTHETIC),
    )

    # Then
    assert result.labels.to_dicts() == [
        {
            "operation_id": "op-1",
            "endpoint": Endpoint.MORTALITY,
            "status": LabelStatus.POSITIVE,
            "eligible": True,
            "reason": None,
        },
        {
            "operation_id": "op-2",
            "endpoint": Endpoint.MORTALITY,
            "status": LabelStatus.NEGATIVE,
            "eligible": True,
            "reason": None,
        },
        {
            "operation_id": "op-3",
            "endpoint": Endpoint.MORTALITY,
            "status": LabelStatus.UNKNOWN,
            "eligible": False,
            "reason": "Missing or invalid supported endpoint value",
        },
        {
            "operation_id": "op-4",
            "endpoint": Endpoint.MORTALITY,
            "status": LabelStatus.UNKNOWN,
            "eligible": False,
            "reason": "Missing or invalid supported endpoint value",
        },
    ]
    assert result.labels.columns == [
        "operation_id",
        "endpoint",
        "status",
        "eligible",
        "reason",
    ]


def test_real_mortality_blocked_until_audit_verifies_linkage() -> None:
    # Given
    cohort = pl.DataFrame({"operation_id": ["op-1"]})
    outcomes = pl.DataFrame({"operation_id": ["op-1"], "in_hospital_mortality": [1]})

    # When
    blocked = build_labels(
        cohort,
        outcomes,
        foundation_capabilities(DataKind.REAL),
    )
    supported = build_labels(
        cohort,
        outcomes,
        audit_capabilities(
            AuditEvidence(
                data_kind=DataKind.REAL,
                mortality_linkage_verified=True,
                mortality_timing_verified=True,
            )
        ),
    )

    # Then
    assert blocked.labels.is_empty()
    mortality_omission = next(
        omission
        for omission in blocked.omissions
        if omission.endpoint is Endpoint.MORTALITY
    )
    assert mortality_omission.status is CapabilityStatus.BLOCKED
    assert "REAL_DATA_PENDING" in mortality_omission.reason
    assert supported.labels.get_column("status").to_list() == [LabelStatus.POSITIVE]


def test_unsupported_secondary_endpoints_are_omitted_with_reasons() -> None:
    # Given
    cohort = pl.DataFrame({"operation_id": ["op-1"]})
    outcomes = pl.DataFrame({"operation_id": ["op-1"], "in_hospital_mortality": [0]})

    # When
    result = build_labels(
        cohort,
        outcomes,
        foundation_capabilities(DataKind.SYNTHETIC),
    )

    # Then
    assert {omission.endpoint for omission in result.omissions} == {
        Endpoint.ACUTE_KIDNEY_INJURY,
        Endpoint.EARLY_ICU_ADMISSION,
        Endpoint.PROLONGED_INVASIVE_SUPPORT,
        Endpoint.COMPOSITE,
    }
    assert all(omission.reason for omission in result.omissions)
