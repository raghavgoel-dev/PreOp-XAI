"""Read historical seals without reconstructing or changing their input schema."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from preop_xai.result_io import Row, load_json, sha256

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = REPOSITORY_ROOT / "artifacts"


class CampaignEvidence(TypedDict):
    source: Path
    evidence_kind: str
    completed: list[str]
    unavailable: list[Row]
    hashes: dict[str, str]
    verified_seal_inputs: dict[str, int]


def validate_destination(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"Destination already exists; refusing overwrite: {output}")
    if not output.is_relative_to(ARTIFACTS_ROOT.resolve()) or output == ARTIFACTS_ROOT.resolve():
        raise ValueError("Export destination must be under ignored artifacts storage.")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Export destination must be outside the source campaign tree.")


def _check_endpoint(source: Path, endpoint: str) -> int:
    directory = source / endpoint
    marker = load_json(directory / "evaluation_complete.json")
    if marker.get("completed") is not True:
        raise ValueError(f"{endpoint}: evaluation is incomplete.")
    model_path = directory / "models.joblib"
    actual = sha256(model_path)
    if marker.get("models_sha256") != actual:
        raise ValueError(f"{endpoint}: evaluation model hash mismatch: {model_path.name}")
    frozen = load_json(directory / "freeze.json")
    inputs = frozen.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError(f"{endpoint}: freeze has no recorded input hashes.")
    model_sealed = False
    for recorded, expected in inputs.items():
        path = Path(recorded.replace("\\", "/"))
        path = path if path.is_absolute() else REPOSITORY_ROOT / path
        if not path.is_file():
            raise ValueError(f"{endpoint}: sealed input missing: {recorded}")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(
                f"{endpoint}: sealed input hash mismatch: {recorded}; "
                f"expected {expected}; observed {actual}"
            )
        model_sealed |= path.resolve() == model_path.resolve()
    if not model_sealed:
        raise ValueError(f"{endpoint}: models.joblib is absent from recorded freeze inputs.")
    for filename in ("metrics.json", "predictions.npz"):
        if not (directory / filename).is_file():
            raise ValueError(f"{endpoint}: completed evaluation evidence missing: {filename}")
    return len(inputs)


def inspect_campaign(source: Path) -> CampaignEvidence:
    """Validate every completed endpoint before any derivative directory is created."""
    status_path = source / "status.json"
    status = load_json(status_path)
    if not isinstance(status.get("synthetic_only"), bool):
        raise ValueError("Campaign status must declare synthetic_only.")
    completed: list[str] = []
    unavailable: list[Row] = []
    verified: dict[str, int] = {}
    for endpoint in ("mortality", "respiratory"):
        details = status.get("endpoints", {}).get(endpoint)
        directory = source / endpoint
        marker = directory / "evaluation_complete.json"
        has_results = any(
            (directory / filename).exists()
            for filename in ("evaluation_started.json", "metrics.json", "predictions.npz")
        )
        if has_results and not marker.is_file():
            raise ValueError(f"{endpoint}: started or incomplete evaluation is not exportable.")
        if marker.exists():
            if details is None:
                raise ValueError(f"{endpoint}: completion conflicts with disabled endpoint status.")
            if not status["synthetic_only"] and details.get("review") != (
                "attested-not-independently-verified"
            ):
                raise ValueError(
                    f"{endpoint}: completed results conflict with clinical review gate."
                )
            verified[endpoint] = _check_endpoint(source, endpoint)
            completed.append(endpoint)
        else:
            unavailable.append(
                {
                    "endpoint": endpoint,
                    "role": "completed-performance",
                    "availability": "unavailable",
                    "reason": (
                        "endpoint disabled or absent from source status"
                        if details is None
                        else "no completed evaluation; review/audit evidence only"
                    ),
                }
            )
    if completed and not (source / "manifest.json").is_file():
        raise ValueError("Completed campaign source manifest is missing.")
    hashes = {"status.json": sha256(status_path)}
    for filename in ("manifest.json", "audit/audit.json"):
        path = source / filename
        if path.is_file():
            hashes[filename] = sha256(path)
    for endpoint in completed:
        for filename in ("freeze.json", "evaluation_complete.json", "models.joblib"):
            hashes[f"{endpoint}/{filename}"] = sha256(source / endpoint / filename)
    return {
        "source": source,
        "evidence_kind": "synthetic" if status["synthetic_only"] else "clinical-research",
        "completed": completed,
        "unavailable": unavailable,
        "hashes": hashes,
        "verified_seal_inputs": verified,
    }
