"""Separate executed stages, review attestations and empirical reliability."""

import json
from typing import TypedDict

import yaml

from preop_xai.config import Settings, file_hash, write_json


class EndpointStatus(TypedDict):
    review: str
    calibration: dict[str, dict[str, str | float | int | None]]
    internal_validation: str
    predictive_reliability: str


class StudyStatus(TypedDict):
    pipeline_execution: str
    completed_stages: list[str]
    synthetic_only: bool
    data_review: str
    endpoints: dict[str, EndpointStatus]
    clinical_use: str


def write_status(settings: Settings, stage: str = "", endpoint: str = "mortality") -> StudyStatus:
    """Persist statuses from explicit stage receipts, never infer clinical approval."""
    output = settings.output_dir
    path = output / "status.json"
    completed = set()
    if path.exists():
        completed.update(json.loads(path.read_text(encoding="utf-8"))["completed_stages"])
    shared = {"audit", "build-cohort", "build-labels", "build-features", "audit-leakage", "split"}
    if stage:
        completed.add(stage if stage in shared or stage == "report" else f"{endpoint}:{stage}")
    endpoints = ["mortality"] + (["respiratory"] if settings.respiratory_enabled else [])
    with settings.feature_map.open(encoding="utf-8") as handle:
        feature_map = yaml.safe_load(handle)
    with settings.outcomes.open(encoding="utf-8") as handle:
        outcomes = yaml.safe_load(handle)
    reviewed = (
        settings.approved
        and feature_map.get("reviewed") is True
        and outcomes["mortality"].get("reviewed") is True
    )
    result: StudyStatus = {
        "pipeline_execution": "incomplete",
        "completed_stages": sorted(completed),
        "synthetic_only": settings.synthetic_only,
        "data_review": (
            "synthetic-fixture-only"
            if settings.synthetic_only
            else "attested-not-independently-verified"
            if reviewed
            else "blocked"
        ),
        "endpoints": {},
        "clinical_use": "unsupported-research-only",
    }
    for name in endpoints:
        calibration_path = output / name / "calibration.json"
        calibration = (
            json.loads(calibration_path.read_text(encoding="utf-8"))
            if calibration_path.exists()
            else {}
        )
        valid = bool(calibration) and all(
            model["calibration_status"] == "fitted" for model in calibration.values()
        )
        receipt = output / name / "evaluation_complete.json"
        model_path = output / name / "models.joblib"
        assessed = False
        if (
            receipt.is_file()
            and model_path.is_file()
            and (output / name / "metrics.json").is_file()
        ):
            completion = json.loads(receipt.read_text(encoding="utf-8"))
            assessed = completion.get("completed") is True and completion.get(
                "models_sha256"
            ) == file_hash(model_path)
        endpoint_review = (
            reviewed
            if name == "mortality"
            else reviewed
            and settings.respiratory_approved
            and outcomes.get("respiratory", {}).get("reviewed") is True
        )
        result["endpoints"][name] = {
            "review": (
                "synthetic-fixture-only"
                if settings.synthetic_only
                else "attested-not-independently-verified"
                if endpoint_review
                else "blocked"
            ),
            "calibration": calibration,
            "internal_validation": (
                "synthetic-evaluation-complete"
                if assessed and settings.synthetic_only
                else "retrospective-internal-evaluation-complete"
                if assessed
                else "not-completed"
            ),
            "predictive_reliability": (
                "calibration-failed"
                if calibration and not valid
                else "not-established-by-software-execution"
            ),
        }
    required = shared | {
        f"{name}:{step}"
        for name in endpoints
        for step in ("train", "calibrate", "explain", "stability", "freeze", "evaluate")
    }
    if required <= completed:
        result["pipeline_execution"] = "complete"
    write_json(path, result)
    return result
