from pathlib import Path

import pandas as pd
import pytest

from preop_xai.audit import audit_raw
from preop_xai.cohort import REVIEW_GATES, build_cohort
from preop_xai.features import (
    LABS,
    audit_leakage,
    build_features,
    load_labs,
)
from preop_xai.labels import build_labels, load_complications
from preop_xai.splits import assign_splits


def information():
    return pd.DataFrame(
        {
            "patient_id": ["p", "p", "q"],
            "operation_id": ["a", "b", "c"],
            "t0": pd.to_datetime(["2020-02-01", "2020-03-01", "2020-02-01"]),
            "anesthesia_end": pd.to_datetime(
                ["2020-02-01 02:00", "2020-03-01 02:00", "2020-02-01 02:00"]
            ),
            "admission_time": pd.to_datetime(["2020-01-31", "2020-02-28", "2020-01-31"]),
            "discharge_time": pd.to_datetime(["2020-02-03", "2020-03-03", "2020-02-03"]),
            "age": [40, 40, 65],
            "asa": ["2", "2", "3"],
            "sex": ["F", "F", "M"],
            "disposition": ["Home", "Expired", "Transfer"],
            "disposition_code": ["1", "2", "3"],
        }
    )


def reviewed():
    data = information()
    data.attrs["review"] = dict.fromkeys(REVIEW_GATES, True)
    return data


def config(mode="collection_proxy"):
    return {
        "reviewed": True,
        "availability": mode,
        "proxy_lag_hours": 24,
        "labs": {lab: {"names": [lab], "units": {"u": 0.1}, "min": 0, "max": 100} for lab in LABS},
    }


def test_review_indexing_and_conflict_quarantine():
    with pytest.raises(ValueError, match="review"):
        build_cohort(information())
    source = reviewed()
    result = build_cohort(source)
    assert result["operation_id"].tolist() == ["a", "c"]
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    duplicate.attrs = source.attrs.copy()
    assert build_cohort(duplicate)["operation_id"].tolist() == ["a", "c"]
    conflict = source.iloc[[0]].copy()
    conflict["sex"] = "M"
    data = pd.concat([source, conflict], ignore_index=True)
    data.attrs = source.attrs.copy()
    assert build_cohort(data)["operation_id"].tolist() == ["b", "c"]


def test_containment_and_end_boundary():
    data = reviewed()
    data.loc[0, "anesthesia_end"] = data.loc[0, "t0"]
    data.loc[2, "discharge_time"] = data.loc[2, "t0"]
    assert build_cohort(data)["operation_id"].tolist() == ["b", "c"]


def test_index_does_not_depend_on_missing_discharge_or_asa():
    # Given: the first operation lacks outcome ascertainment and a predictor.
    data = reviewed()
    data.loc[0, "discharge_time"] = pd.NaT
    data.loc[0, "asa"] = pd.NA
    # When: selecting the first eligible observed operation.
    cohort = build_cohort(data)
    # Then: later label availability cannot replace it.
    assert cohort["operation_id"].tolist() == ["a", "c"]
    assert pd.isna(cohort.loc[0, "asa"])


def test_ambiguous_first_operation_time_is_quarantined():
    # Given: two distinct operations have an indistinguishable first cutoff.
    data = reviewed()
    data.loc[1, "t0"] = data.loc[0, "t0"]
    # When: indexing without inventing chronology from identifier sort order.
    cohort = build_cohort(data)
    # Then: the ambiguous patient is excluded with an explicit reason.
    assert cohort["patient_id"].tolist() == ["q"]
    assert "ambiguous_first_operation_time" in set(cohort.attrs["exclusions"]["reason"])


def test_nullable_reviewed_labels_and_literal_none(tmp_path: Path):
    path = tmp_path / "patient_post_op_complications.csv"
    path.write_text(
        "LOG_ID,MRN,Element_Name,CONTEXT_NAME,Element_abbr,SMRTDTA_ELEM_VALUE\n"
        "a,p,Resp,Postop,R,None\n"
        "a,p,Resp,Postop,R,Yes\n",
        encoding="utf-8",
    )
    complications = load_complications(tmp_path)
    assert complications["value"].iloc[0] == "None"
    outcomes = {
        "version": "test-v1",
        "mortality": {
            "reviewed": True,
            "positive_descriptions": ["Expired"],
            "negative_descriptions": ["Home"],
            "unknown_descriptions": ["Transfer", "Hospice"],
        },
        "respiratory": {
            "enabled": True,
            "reviewed": True,
            "rules": [
                {
                    "element": "Resp",
                    "context": "Postop",
                    "abbreviation": "R",
                    "value": value,
                    "label": label,
                }
                for value, label in [("None", 0), ("Yes", 1)]
            ],
        },
    }
    source = reviewed()
    result = build_labels(build_cohort(source), source, complications, outcomes)
    assert result["mortality"].iloc[0] == 0
    assert pd.isna(result["mortality"].iloc[1])
    assert result["respiratory"].isna().all()
    assert result["mortality"].dtype == "Int64"


def lab_rows(times, values):
    return pd.DataFrame(
        {
            "patient_id": ["p"] * len(times),
            "operation_id": ["a"] * len(times),
            "collection_time": times,
            "lab_name": ["hemoglobin"] * len(times),
            "value": values,
            "unit": ["u"] * len(times),
        }
    )


def test_proxy_bounds_conversion_and_no_future_missingness():
    cohort = build_cohort(reviewed())
    cutoff = cohort["t0"].iloc[0]
    labs = lab_rows(
        [
            cutoff - pd.Timedelta(days=30),
            cutoff - pd.Timedelta(hours=24),
            cutoff - pd.Timedelta(hours=23),
            cutoff + pd.Timedelta(hours=1),
        ],
        ["90", "100", "200", "300"],
    )
    wide, provenance = build_features(cohort, labs, config())
    assert len(wide) == 2
    assert wide["hemoglobin"].iloc[0] == 10
    assert pd.isna(wide["hemoglobin"].iloc[1])
    assert set(provenance["reason"]) == {
        "older_eligible",
        "selected",
        "proxy_lag",
        "future_collection",
    }
    broken = wide.copy()
    broken.loc[0, "hemoglobin"] = 30
    with pytest.raises(ValueError, match="provenance"):
        audit_leakage(cohort, broken, provenance, config())


def test_strict_release_and_conflicting_latest():
    cohort = build_cohort(reviewed())
    cutoff = cohort["t0"].iloc[0]
    labs = lab_rows([cutoff - pd.Timedelta(hours=1)] * 2, ["100", "110"])
    labs["result_time"] = cutoff
    wide, provenance = build_features(cohort, labs, config("strict"))
    assert wide["hemoglobin"].isna().all()
    assert provenance["reason"].eq("conflicting_latest").all()
    labs.loc[1, "result_time"] = cutoff + pd.Timedelta(seconds=1)
    wide, provenance = build_features(cohort, labs, config("strict"))
    assert wide["hemoglobin"].iloc[0] == 10
    assert "future_release" in set(provenance["reason"])


def test_text_threshold_and_unknown_unit_rejected():
    cohort = build_cohort(reviewed())
    time = cohort["t0"].iloc[0] - pd.Timedelta(days=2)
    labs = lab_rows([time, time], ["<10", "100"])
    labs.loc[1, "unit"] = "unreviewed"
    wide, provenance = build_features(cohort, labs, config())
    assert wide["hemoglobin"].isna().all()
    assert set(provenance["reason"]) == {"nonnumeric_or_nonfinite", "unknown_unit"}


def test_lazy_adapter_requires_explicit_strict_release_map(tmp_path):
    cohort = build_cohort(reviewed())
    (tmp_path / "patient_labs.csv").write_text(
        "MRN,LOG_ID,RESULT_TIME,LAB_NAME,ORD_VALUE,RESULT_UNIT\n"
        "p,a,2020-01-30,hemoglobin,100,u\n"
        "other,other,2020-01-30,hemoglobin,200,u\n",
        encoding="utf-8",
    )
    assert len(load_labs(tmp_path, cohort, config())) == 1
    with pytest.raises(ValueError, match="release-time"):
        load_labs(tmp_path, cohort, config("strict"))


def test_seeded_patient_splits_unknown_retention_and_failure():
    n = 240
    data = pd.DataFrame(
        {
            "patient_id": [f"p{i:04}" for i in range(n)],
            "operation_id": [f"o{i:04}" for i in range(n)],
            "t0": pd.Timestamp("2020-01-01"),
            "mortality": pd.array(([0, 1] * 100) + [pd.NA] * 40, dtype="Int64"),
            "respiratory": pd.array([pd.NA] * n, dtype="Int64"),
        }
    )
    first = assign_splits(data)
    second = assign_splits(data.sample(frac=1, random_state=8))
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == n
    assert first.groupby("patient_id")["partition"].nunique().max() == 1
    assert set(first["partition"]) == {"train", "validation", "test"}
    assert first["mortality"].isna().sum() == 40
    insufficient = data.iloc[:10].copy()
    insufficient["mortality"] = [1] + [0] * 9
    with pytest.raises(ValueError, match="sample adequacy"):
        assign_splits(insufficient)


def test_raw_audit_dynamic_headers_and_checksums(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "custom.csv").write_text(
        "LOG_ID,MRN,UNEXPECTED,LAB_NAME,RESULT_UNIT\n"
        "a,p,None,hemoglobin,u\n"
        "a,p,None,hemoglobin,u\n",
        encoding="utf-8",
    )
    destination = audit_raw(raw, tmp_path / "audit")
    import json

    report = json.loads(destination.read_text(encoding="utf-8"))
    table = report["tables"]["custom.csv"]
    assert table["rows"] == 2
    assert table["schema"]["UNEXPECTED"] == "String"
    assert len(table["sha256"]) == 64
    assert table["duplicate_operations"] == {"duplicated": 1, "conflicting": 0}
    assert report["clinical_verification"] is False
