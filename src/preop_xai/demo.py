"""Synthetic end-to-end proof; never a substitute for clinical experiments."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd
import typer
import yaml
from scipy.special import expit

from preop_xai.cohort import INFORMATION_COLUMNS, REVIEW_GATES
from preop_xai.config import FeatureMapping, OutcomeMapping, load_settings, write_json
from preop_xai.labels import COMPLICATION_COLUMNS
from preop_xai.preprocessing import LABS
from preop_xai.workflow import run_stage


class LabRecord(TypedDict):
    patient_id: str
    operation_id: str
    lab_name: str
    collection_time: datetime
    value: str
    unit: str


def synthetic_tables(
    seed: int = 2026, n: int = 600
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, FeatureMapping, OutcomeMapping]:
    """Return artificial source tables with known, nonclinical coding semantics."""
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 91, n)
    asa = rng.choice([1, 2, 3, 4], n)
    t0 = datetime(2020, 2, 1, 12)
    y = rng.binomial(1, expit(-2.5 + 0.04 * (age - 50) + 0.55 * (asa - 2)))
    information = pd.DataFrame(
        {
            "patient_id": [f"synthetic-p{i:04}" for i in range(n)],
            "operation_id": [f"synthetic-o{i:04}" for i in range(n)],
            "t0": t0,
            "anesthesia_end": t0 + timedelta(hours=2),
            "admission_time": t0 - timedelta(days=1),
            "discharge_time": t0 + timedelta(days=3),
            "age": age,
            "sex": rng.choice(["F", "M"], n),
            "asa": asa.astype(str),
            "disposition": np.where(y, "Synthetic death", "Synthetic home"),
            "disposition_code": np.where(y, "D", "H"),
        }
    )
    information.attrs["review"] = dict.fromkeys(REVIEW_GATES, True)
    respiratory = rng.binomial(1, expit(-2.2 + 0.5 * (asa - 2)))
    complications = pd.DataFrame(
        {
            "patient_id": information.patient_id,
            "operation_id": information.operation_id,
            "element": "Synthetic postoperative respiratory assessment",
            "abbreviation": "SYNTH",
            "context": "SYNTHETIC_POSTOPERATIVE",
            "value": np.where(respiratory, "Synthetic yes", "Synthetic no"),
        }
    )
    means = [13, 220, 1.1, 18, 140, 4, 110]
    deviations = [2, 50, 0.3, 6, 3, 0.4, 25]
    records: list[LabRecord] = []
    for _index, row in information.iterrows():
        for lab, mean, sd in zip(LABS, means, deviations, strict=True):
            if rng.random() < 0.15:
                continue
            records.append(
                {
                    "patient_id": row.patient_id,
                    "operation_id": row.operation_id,
                    "lab_name": lab,
                    "collection_time": t0 - timedelta(days=2),
                    "value": str(max(0.01, rng.normal(mean, sd))),
                    "unit": "synthetic-unit",
                }
            )
    mapping: FeatureMapping = {
        "version": "synthetic-v1",
        "synthetic_only": True,
        "reviewed": True,
        "availability": "collection_proxy",
        "proxy_lag_hours": 24,
        "labs": {
            lab: {"names": [lab], "units": {"synthetic-unit": 1.0}, "min": 0, "max": 10000}
            for lab in LABS
        },
    }
    outcomes: OutcomeMapping = {
        "version": "synthetic-v1",
        "synthetic_only": True,
        "mortality": {
            "reviewed": True,
            "positive_descriptions": ["Synthetic death"],
            "negative_descriptions": ["Synthetic home"],
            "unknown_descriptions": ["Synthetic transfer"],
        },
        "respiratory": {
            "enabled": True,
            "reviewed": True,
            "rules": [
                {
                    "element": "Synthetic postoperative respiratory assessment",
                    "abbreviation": "SYNTH",
                    "context": "SYNTHETIC_POSTOPERATIVE",
                    "value": value,
                    "label": label,
                }
                for value, label in [("Synthetic no", 0), ("Synthetic yes", 1)]
            ],
        },
    }
    return information, complications, pd.DataFrame(records), mapping, outcomes


def run_demo(output: Path, seed: int = 2026) -> None:
    """Exercise both endpoints through real estimators, SHAP and paired uncertainty."""
    if output.exists() and any(output.iterdir()):
        raise ValueError("Demo output is not empty; choose a new directory to preserve evidence.")
    output.mkdir(parents=True, exist_ok=True)
    information, complications, labs, mapping, outcomes = synthetic_tables(seed)
    raw = output / "synthetic_raw"
    raw.mkdir()
    information.attrs = {}
    information.rename(columns={v: k for k, v in INFORMATION_COLUMNS.items()}).to_csv(
        raw / "patient_information.csv",
        index=False,
    )
    complications.rename(columns={v: k for k, v in COMPLICATION_COLUMNS.items()}).to_csv(
        raw / "patient_post_op_complications.csv",
        index=False,
    )
    labs.rename(
        columns={
            "patient_id": "MRN",
            "operation_id": "LOG_ID",
            "lab_name": "Lab Name",
            "collection_time": "Collection Datetime",
            "value": "Observation Value",
            "unit": "Measurement Units",
        }
    ).to_csv(raw / "patient_labs.csv", index=False)
    pd.DataFrame(columns=["LOG_ID", "MRN", "EVENT_DISPLAY_NAME", "EVENT_TIME"]).to_csv(
        raw / "patient_procedure events.csv",
        index=False,
    )
    mapping["columns"] = {
        "patient_id": "MRN",
        "operation_id": "LOG_ID",
        "lab_name": "Lab Name",
        "collection_time": "Collection Datetime",
        "value": "Observation Value",
        "unit": "Measurement Units",
    }
    feature_path, outcome_path = output / "feature_map.yaml", output / "outcomes.yaml"
    feature_path.write_text(yaml.safe_dump(mapping), encoding="utf-8")
    outcome_path.write_text(yaml.safe_dump(outcomes), encoding="utf-8")
    config = {
        "protocol_version": "1.1",
        "synthetic_only": True,
        "raw_dir": str(raw.resolve()),
        "output_dir": str(output.resolve()),
        "feature_map": str(feature_path.resolve()),
        "outcomes": str(outcome_path.resolve()),
        "seed": seed,
        "folds": 5,
        "evaluation_bootstraps": 1000,
        "stability_refits": 10,
        "review": {
            **dict.fromkeys(
                (
                    "age_semantics",
                    "asa_mapping",
                    "anesthesia_boundary",
                    "static_predictor_provenance",
                    "mortality_hospitalization_linkage",
                    "mortality_dispositions",
                ),
                True,
            ),
            "reviewer": "SYNTHETIC FIXTURE",
            "evidence": "Artificial known generating process",
        },
        "respiratory": {
            "enabled": True,
            "postoperative_meaning": True,
            "explicit_negatives": True,
            "sufficient_events": True,
            "reviewer": "SYNTHETIC FIXTURE",
            "evidence": "Artificial known generating process",
        },
    }
    config_path = output / "study.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    settings = load_settings(config_path)
    for stage in (
        "audit",
        "build-cohort",
        "build-labels",
        "build-features",
        "audit-leakage",
        "split",
    ):
        run_stage(stage, settings)
    for stage in ("train", "calibrate", "explain", "stability", "freeze", "evaluate"):
        for endpoint in ("mortality", "respiratory"):
            run_stage(stage, settings, endpoint, "test" if stage == "evaluate" else "validation")
    run_stage("report", settings)
    report = output / "report.md"
    report.write_text(
        "SYNTHETIC SOFTWARE DEMONSTRATION ONLY - NO CLINICAL RESULTS\n\n"
        + report.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    write_json(
        output / "demo_complete.json",
        {
            "synthetic_only": True,
            "endpoints": ["mortality", "respiratory"],
            "passed": True,
            "pipeline_execution": "complete",
            "predictive_reliability": "not-established; see per-model calibration status",
            "clinical_use": "unsupported-research-only",
        },
    )
    typer.echo(
        json.dumps(
            {
                "synthetic_only": True,
                "report": str(report),
                "passed": True,
                "pipeline_execution": "complete",
                "predictive_reliability": "not-established; see report calibration status",
                "clinical_use": "unsupported-research-only",
            }
        )
    )
