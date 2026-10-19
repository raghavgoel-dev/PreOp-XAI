"""Configuration and explicit clinical-review boundaries."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict, TypeVar

import yaml


class LabMapping(TypedDict):
    names: list[str]
    units: dict[str, float]
    min: float
    max: float


class FeatureMapping(TypedDict):
    version: str
    synthetic_only: bool
    reviewed: bool
    availability: str
    proxy_lag_hours: int
    labs: dict[str, LabMapping]
    columns: NotRequired[dict[str, str]]


class MortalityMapping(TypedDict):
    reviewed: bool
    positive_descriptions: list[str]
    negative_descriptions: list[str]
    unknown_descriptions: list[str]


class RespiratoryRule(TypedDict):
    element: str
    abbreviation: str
    context: str
    value: str
    label: int


class RespiratoryMapping(TypedDict):
    enabled: bool
    reviewed: bool
    rules: list[RespiratoryRule]


class OutcomeMapping(TypedDict):
    version: str
    synthetic_only: bool
    mortality: MortalityMapping
    respiratory: RespiratoryMapping


class MappingDocument(TypedDict, total=False):
    """Fields read from either feature-map or outcome YAML documents."""

    version: str
    synthetic_only: bool
    reviewed: bool
    availability: str
    proxy_lag_hours: int
    labs: dict[str, LabMapping]
    columns: dict[str, str]
    mortality: MortalityMapping
    respiratory: RespiratoryMapping


_Payload = TypeVar("_Payload")


@dataclass(frozen=True, slots=True)
class Settings:
    path: Path
    raw_dir: Path
    output_dir: Path
    feature_map: Path
    outcomes: Path
    seed: int
    folds: int
    evaluation_bootstraps: int
    stability_refits: int
    approved: bool
    respiratory_enabled: bool
    respiratory_approved: bool
    review_evidence: str
    synthetic_only: bool = False


def load_settings(path: Path) -> Settings:
    """Load local paths relative to the repository working directory."""
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    review = raw.get("review", {})
    respiratory = raw.get("respiratory", {})
    required = (
        "age_semantics",
        "asa_mapping",
        "anesthesia_boundary",
        "static_predictor_provenance",
        "mortality_hospitalization_linkage",
        "mortality_dispositions",
    )
    approved = all(review.get(key) is True for key in required)
    approved = approved and bool(review.get("reviewer")) and bool(review.get("evidence"))
    respiratory_approved = (
        all(
            respiratory.get(key) is True
            for key in ("postoperative_meaning", "explicit_negatives", "sufficient_events")
        )
        and bool(respiratory.get("reviewer"))
        and bool(respiratory.get("evidence"))
    )
    return Settings(
        path=path,
        raw_dir=Path(raw["raw_dir"]),
        output_dir=Path(raw["output_dir"]),
        feature_map=Path(raw["feature_map"]),
        outcomes=Path(raw["outcomes"]),
        seed=int(raw.get("seed", 2026)),
        folds=int(raw.get("folds", 5)),
        evaluation_bootstraps=int(raw.get("evaluation_bootstraps", 1000)),
        stability_refits=int(raw.get("stability_refits", 10)),
        approved=approved,
        respiratory_enabled=respiratory.get("enabled") is True,
        respiratory_approved=respiratory_approved,
        review_evidence=str(review.get("evidence", "")),
        synthetic_only=raw.get("synthetic_only") is True,
    )


def require_review(settings: Settings, endpoint: str = "mortality") -> None:
    if endpoint not in {"mortality", "respiratory"}:
        raise ValueError("Endpoint must be mortality or respiratory.")
    if not settings.approved:
        raise ValueError(
            "Clinical review required: verify age, ASA, anesthesia boundary, static predictor "
            "provenance and mortality hospitalization/disposition mappings; record reviewer "
            "and evidence in the local study configuration. Run audit first."
        )
    if endpoint == "respiratory" and not (
        settings.respiratory_enabled and settings.respiratory_approved
    ):
        raise ValueError(
            "Respiratory endpoint stopped: reviewed postoperative meaning, explicit negatives, "
            "adequate events and reviewer evidence are required. Retain mortality-only title."
        )


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configuration_hash(settings: Settings) -> str:
    return hashlib.sha256(
        "".join(
            file_hash(p)
            for p in (
                settings.path,
                settings.feature_map,
                settings.outcomes,
            )
        ).encode()
    ).hexdigest()


def write_json(path: Path, payload: _Payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False, default=str), encoding="utf-8")
