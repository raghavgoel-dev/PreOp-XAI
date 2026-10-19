"""Explicit derivative manifest schema and aggregate-index validation."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from preop_xai.result_io import Json, Scalar, aggregate_path, load_json, sha256


class ArtifactEntry(TypedDict):
    path: str
    sha256: str
    role: str
    source_files: list[str]
    endpoint: str | None
    model: str
    variant: str
    denominator: Scalar
    units_scale: str
    availability: str
    calibration_status: str


class SourceLink(TypedDict):
    path: str
    sha256: str
    role: str


class ExportManifest(TypedDict):
    schema_version: int
    source_campaign: dict[str, str]
    exporter: dict[str, Json]
    created_at: str
    source_hashes: dict[str, str]
    verified_seal_input_counts: dict[str, int]
    endpoints: dict[str, Json]
    artifacts: list[ArtifactEntry]
    source_links: list[SourceLink]
    unavailable: list[dict[str, Scalar]]
    definitions: dict[str, Json]
    legacy_provenance_limitations: list[str]


def read_manifest(path: Path) -> ExportManifest:
    """Parse the machine-consumed report boundary before following any paths."""
    value = load_json(path)
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int:
        raise ValueError("Invalid report artifact manifest schema.")
    for key in (
        "source_campaign",
        "exporter",
        "endpoints",
        "definitions",
        "source_hashes",
        "verified_seal_input_counts",
    ):
        if not isinstance(value.get(key), dict):
            raise ValueError(f"Invalid report artifact manifest field: {key}")
    for key in ("identity", "revision", "evidence_kind"):
        if not isinstance(value["source_campaign"].get(key), str):
            raise ValueError(f"Invalid source campaign field: {key}")
    if not isinstance(value["exporter"].get("revision"), str):
        raise ValueError("Invalid derivative exporter revision.")
    for key in ("artifacts", "source_links", "unavailable", "legacy_provenance_limitations"):
        if not isinstance(value.get(key), list):
            raise ValueError(f"Invalid report artifact manifest field: {key}")
    for entry in value["artifacts"] + value["source_links"]:
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(key), str) for key in ("path", "sha256", "role")
        ):
            raise ValueError("Invalid aggregate manifest entry.")
    if any(not isinstance(entry, dict) for entry in value["unavailable"]):
        raise ValueError("Invalid unavailable artifact entry.")
    if any(not isinstance(item, str) for item in value["legacy_provenance_limitations"]):
        raise ValueError("Invalid provenance limitations.")
    return ExportManifest(
        schema_version=value["schema_version"],
        source_campaign=value["source_campaign"],
        exporter=value["exporter"],
        created_at=value.get("created_at", ""),
        source_hashes=value["source_hashes"],
        verified_seal_input_counts=value["verified_seal_input_counts"],
        endpoints=value["endpoints"],
        artifacts=value["artifacts"],
        source_links=value["source_links"],
        unavailable=value["unavailable"],
        definitions=value["definitions"],
        legacy_provenance_limitations=value["legacy_provenance_limitations"],
    )


def validate_manifest(output: Path, manifest: ExportManifest) -> None:
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported report artifact manifest schema.")
    if manifest["source_campaign"]["evidence_kind"] not in {
        "synthetic",
        "clinical-research",
        "report-illustration-reference",
    }:
        raise ValueError("Unknown report evidence kind.")
    paths: set[str] = set()
    for entry in manifest["artifacts"]:
        relative = entry["path"]
        path = aggregate_path(output, relative)
        if relative in paths:
            raise ValueError(f"Duplicate aggregate manifest path: {relative}")
        paths.add(relative)
        if path.suffix.lower() not in {".csv", ".png", ".md"}:
            raise ValueError(f"Non-aggregate artifact in report manifest: {relative}")
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"Aggregate artifact hash mismatch: {relative}")
    for entry in manifest["source_links"]:
        linked_source(output, manifest, entry)


def linked_source(output: Path, manifest: ExportManifest, entry: SourceLink) -> Path:
    from preop_xai import result_integrity

    source = aggregate_path(
        result_integrity.ARTIFACTS_ROOT, manifest["source_campaign"]["storage_path"]
    )
    path = aggregate_path(source, entry["path"])
    if path.name != "lr_coefficients.csv" or sha256(path) != entry["sha256"]:
        raise ValueError(f"Invalid source aggregate link: {entry['path']}")
    return path
