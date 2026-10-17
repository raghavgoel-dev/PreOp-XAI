"""Reviewed, explicit endpoint mappings; absence of evidence is unknown."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl

from .audit import scan_strings
from .cohort import IDENTITY, require_columns, validate_identity

COMPLICATION_COLUMNS = {
    "MRN": "patient_id",
    "LOG_ID": "operation_id",
    "Element_Name": "element",
    "CONTEXT_NAME": "context",
    "Element_abbr": "abbreviation",
    "SMRTDTA_ELEM_VALUE": "value",
}


def load_complications(raw_dir: Path) -> pd.DataFrame:
    return (
        scan_strings(Path(raw_dir) / "patient_post_op_complications.csv")
        .select([pl.col(source).alias(target) for source, target in COMPLICATION_COLUMNS.items()])
        .collect(engine="streaming")
        .to_pandas()
    )


def build_labels(cohort, information, complications, outcome_config) -> pd.DataFrame:
    validate_identity(cohort)
    require_columns(information, IDENTITY + ["disposition", "admission_time", "discharge_time"])
    mortality = outcome_config.get("mortality", {})
    if mortality.get("reviewed") is not True:
        raise ValueError("Mortality mapping and hospitalization linkage require review")
    if not outcome_config.get("version"):
        raise ValueError("A versioned outcome mapping is required")
    positive = set(mortality.get("positive_descriptions", []))
    negative = set(mortality.get("negative_descriptions", []))
    unknown = set(mortality.get("unknown_descriptions", []))
    if not positive or not negative or not unknown:
        raise ValueError("Specify positive, negative and unknown disposition descriptions")
    if positive & negative or unknown & (positive | negative):
        raise ValueError("Disposition mapping sets overlap")

    respiratory = outcome_config.get("respiratory", {})
    enabled = respiratory.get("enabled", False)
    rule_map = {}
    if enabled:
        if respiratory.get("reviewed") is not True:
            raise ValueError("Respiratory postoperative and negative semantics need review")
        require_columns(complications, COMPLICATION_COLUMNS.values())
        for rule in respiratory.get("rules", []):
            key = tuple(rule[field] for field in ("element", "abbreviation", "context", "value"))
            state = rule["label"]
            if state not in (0, 1):
                raise ValueError("Respiratory rules must label 0 or 1")
            if key in rule_map and rule_map[key] != state:
                raise ValueError("Contradictory respiratory rules")
            rule_map[key] = state
        if set(rule_map.values()) != {0, 1}:
            raise ValueError("Reviewed positive and explicit negative rules are required")

    information_groups = {
        key: group.drop_duplicates()
        for key, group in information.groupby(["patient_id", "operation_id"], sort=False)
    }
    complication_groups = (
        {
            key: group
            for key, group in complications.groupby(["patient_id", "operation_id"], sort=False)
        }
        if enabled
        else {}
    )
    rows = []
    for row in cohort.itertuples(index=False):
        evidence = information_groups.get((row.patient_id, row.operation_id), information.iloc[:0])
        m, m_reason = pd.NA, "missing_or_unlinked"
        if len(evidence):
            admission = pd.to_datetime(evidence["admission_time"], errors="coerce")
            discharge = pd.to_datetime(evidence["discharge_time"], errors="coerce")
            cutoff = pd.to_datetime(evidence["t0"], errors="coerce")
            linked = admission.le(row.t0) & discharge.ge(row.anesthesia_end) & cutoff.eq(row.t0)
            states = [
                1 if value in positive else 0 if value in negative else None
                for value in evidence["disposition"]
            ]
            if linked.all() and None not in states and len(set(states)) == 1:
                m, m_reason = states[0], "reviewed_disposition"
            else:
                m_reason = "unknown_conflicting_or_unlinked_disposition"
        r, r_reason = pd.NA, "disabled"
        if enabled:
            matched = complication_groups.get(
                (row.patient_id, row.operation_id), complications.iloc[:0]
            )
            states = {
                rule_map[key]
                for key in matched[["element", "abbreviation", "context", "value"]].itertuples(
                    index=False, name=None
                )
                if key in rule_map
            }
            r_reason = "no_reviewed_assessment"
            if len(states) == 1:
                r, r_reason = states.pop(), "reviewed_assessment"
            elif len(states) > 1:
                r_reason = "contradictory_assessments"
        rows.append(
            {
                "patient_id": row.patient_id,
                "operation_id": row.operation_id,
                "t0": row.t0,
                "mortality": m,
                "respiratory": r,
                "mortality_reason": m_reason,
                "respiratory_reason": r_reason,
                "mapping_version": outcome_config["version"],
            }
        )
    result = pd.DataFrame(
        rows,
        columns=IDENTITY
        + [
            "mortality",
            "respiratory",
            "mortality_reason",
            "respiratory_reason",
            "mapping_version",
        ],
    )
    for endpoint in ("mortality", "respiratory"):
        result[endpoint] = result[endpoint].astype("Int64")
    return result
