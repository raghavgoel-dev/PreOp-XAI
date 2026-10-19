"""Read-only completed-campaign derivative export; never fit or unlock evaluation."""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from preop_xai.result_context import campaign_summary, explanation_figures
from preop_xai.result_integrity import REPOSITORY_ROOT, inspect_campaign, validate_destination
from preop_xai.result_io import ArtifactTables, Row, aggregate_path, load_json, save_json, sha256
from preop_xai.result_io import write_table as _write_table
from preop_xai.result_manifest import ArtifactEntry, ExportManifest
from preop_xai.result_report import build_export_report


def _revision() -> str:
    return subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _entry(output: Path, relative: str, sources: list[str], n=None) -> ArtifactEntry:
    path = aggregate_path(output, relative)
    return {
        "path": relative,
        "sha256": sha256(path),
        "role": path.stem,
        "source_files": sources,
        "endpoint": Path(relative).parts[0] if "/" in relative else None,
        "model": "all-available; keyed in table",
        "variant": "all-available; keyed in table",
        "denominator": n,
        "units_scale": (
            "raw model log-odds; sample SD ddof=1, not CI"
            if "stability" in relative
            else "probabilities/rates or integer counts; see columns"
        ),
        "availability": "available",
        "calibration_status": "per-model/variant; see table and endpoint metadata",
    }


def export_results(source: Path, output: Path) -> Path:
    """Export saved evidence into a fresh ignored sibling tree after full preflight."""
    from preop_xai.result_numerics import TABLE_FIELDS, numerical_tables
    from preop_xai.result_plots import plot_comparison, plot_endpoint
    from preop_xai.result_stability import STABILITY_FIELDS, plot_stability, stability_tables

    source, output = Path(source).resolve(), Path(output).resolve()
    validate_destination(source, output)
    evidence = inspect_campaign(source)
    summary, context_inputs = campaign_summary(source)
    batches: dict[str, tuple[ArtifactTables, ArtifactTables]] = {}
    figures: list[tuple[Path, str]] = []
    missing_figures: list[Row] = []
    for endpoint in evidence["completed"]:
        batches[endpoint] = (
            numerical_tables(source / endpoint, endpoint, evidence["evidence_kind"]),
            stability_tables(source / endpoint, endpoint),
        )
        available_figures, missing = explanation_figures(source, endpoint)
        figures.extend(available_figures)
        missing_figures.extend(missing)
    source_hashes = dict(evidence["hashes"])
    for relative in context_inputs:
        source_hashes[relative] = sha256(source / relative)
    for endpoint in evidence["completed"]:
        for filename in (
            "metrics.json",
            "predictions.npz",
            "intervals.csv",
            "explain.json",
            "stability.json",
            "calibration.json",
            "bundle.json",
        ):
            path = source / endpoint / filename
            if path.is_file():
                source_hashes[f"{endpoint}/{filename}"] = sha256(path)
        for model in ("lr", "xgboost"):
            path = source / endpoint / "private" / f"{model}_stability.npz"
            if path.is_file():
                source_hashes[f"{endpoint}/restricted-{model}-stability"] = sha256(path)
    for candidate, _ in figures:
        source_hashes[candidate.relative_to(source).as_posix()] = sha256(candidate)
    historical = load_json(source / "manifest.json") if (source / "manifest.json").is_file() else {}
    manifest: ExportManifest = {
        "schema_version": 1,
        "source_campaign": {
            "identity": source.name,
            "revision": historical.get("code_commit", "unavailable"),
            "evidence_kind": evidence["evidence_kind"],
        },
        "exporter": {
            "revision": _revision(),
            "source_sha256": {
                p.relative_to(REPOSITORY_ROOT).as_posix(): sha256(p)
                for p in sorted((REPOSITORY_ROOT / "src/preop_xai").glob("*.py"))
            },
            "packages": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "scipy", "scikit-learn", "matplotlib", "typer")
            },
        },
        "created_at": datetime.now(UTC).isoformat(),
        "source_hashes": source_hashes,
        "verified_seal_input_counts": evidence["verified_seal_inputs"],
        "endpoints": {},
        "artifacts": [],
        "source_links": [],
        "unavailable": [*evidence["unavailable"], *missing_figures],
        "definitions": {
            "threshold_policy": "validation-selected; p >= threshold; never test-selected",
            "average_precision": "sklearn average_precision_score, not trapezoidal PR area",
            "roc": "complete distinct thresholds; drop_intermediate=False; infinity blank + kind",
            "pr": "terminal threshold blank + threshold_kind=none",
            "fixed_bins": "[0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]; empty rows retained",
            "quantile_bins": (
                "10 requested; unique edges; minimum included; subsequent right-closed"
            ),
            "display_precision": "CSV full precision; figures four decimal scores including Brier",
            "figure_axes": {"roc": [0, 1], "pr": [0, 1], "calibration_quantile": [0, 1]},
            "stability_sd": "sample SD across per-refit mean absolute grouped importance; ddof=1",
        },
        "legacy_provenance_limitations": [
            "Historical source revision/hashes are not derivative exporter provenance.",
            "Legacy completion markers seal model bytes, not prediction/metric bytes; consumed "
            "artifact hashes establish the derivative snapshot, not a retroactive historical seal.",
            "No calibration fitting, model prediction, partition loading, SHAP or bootstrap "
            "refitting occurs during export. Missing historical intervals are not reconstructed.",
            "Clinical runtime/peak memory are unavailable without source measurement receipts.",
        ],
    }
    for row in evidence["unavailable"]:
        for role in (
            "discrimination_calibration",
            "operating_point",
            "roc_pr",
            "calibration_quantile",
            "confusion_matrices",
            "stability",
        ):
            manifest["unavailable"].append({**row, "role": role})
    from preop_xai import result_integrity

    if source.is_relative_to(result_integrity.ARTIFACTS_ROOT.resolve()):
        manifest["source_campaign"]["storage_path"] = source.relative_to(
            result_integrity.ARTIFACTS_ROOT.resolve()
        ).as_posix()
        for endpoint in evidence["completed"]:
            relative = f"{endpoint}/lr_coefficients.csv"
            if (source / relative).is_file():
                digest = sha256(source / relative)
                source_hashes[relative] = digest
                manifest["source_links"].append(
                    {"path": relative, "sha256": digest, "role": "original-scaled-lr-coefficients"}
                )
    # No result files are created until all endpoint numerics, arrays and references validate.
    output.mkdir(parents=True, exist_ok=False)
    _write_table(output / "campaign_summary.csv", summary)
    manifest["artifacts"].append(_entry(output, "campaign_summary.csv", context_inputs))
    comparison: list[Row] = []
    for endpoint, (numerical, stability) in batches.items():
        directory = output / endpoint
        directory.mkdir()
        consumed = [key for key in source_hashes if key.startswith(f"{endpoint}/")]
        for batch in (numerical, stability):
            for filename, rows in batch["tables"].items():
                fields = {**TABLE_FIELDS, **STABILITY_FIELDS}[filename]
                _write_table(directory / filename, rows, fields)
            manifest["unavailable"].extend(
                {**row, "role": row.get("role", row.get("artifact"))}
                for row in batch["unavailable"]
            )
        metrics = load_json(source / endpoint / "metrics.json")
        manifest["endpoints"][endpoint] = {
            "partition": "test",
            "n": metrics["n"],
            "events": metrics["events"],
            "evidence_kind": evidence["evidence_kind"],
            "numerical": numerical["metadata"],
            "stability": stability["metadata"],
        }
        comparison.extend(numerical["tables"]["discrimination_calibration.csv"])
        intervals = source / endpoint / "intervals.csv"
        if intervals.is_file():
            shutil.copyfile(intervals, directory / "intervals.csv")
        else:
            manifest["unavailable"].append(
                {
                    "endpoint": endpoint,
                    "role": "intervals",
                    "reason": "source intervals.csv unavailable; no historical bootstrap rerun",
                }
            )
        plot_endpoint(directory, endpoint)
        plot_stability(directory, endpoint)
        stability_summary = stability["tables"]["stability_summary.csv"]
        validation_n = stability_summary[0]["validation_n"] if stability_summary else None
        for path in sorted(directory.iterdir()):
            manifest["artifacts"].append(
                _entry(
                    output,
                    path.relative_to(output).as_posix(),
                    consumed,
                    validation_n if path.name.startswith("stability") else metrics["n"],
                )
            )
    for candidate, relative in figures:
        target = aggregate_path(output, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, target)
        manifest["artifacts"].append(
            _entry(output, relative, [candidate.relative_to(source).as_posix()])
        )
    _write_table(
        output / "endpoint_comparison.csv",
        comparison,
        (list(comparison[0]) if comparison else ["endpoint", "model", "variant"]),
    )
    unavailable = [f"{r['endpoint']}: {r['reason']}" for r in evidence["unavailable"]]
    plot_comparison(output, unavailable)
    for name in ("endpoint_comparison.csv", "endpoint_comparison.png"):
        manifest["artifacts"].append(
            _entry(output, name, [f"{endpoint}/metrics.json" for endpoint in evidence["completed"]])
        )
    build_export_report(output, manifest)
    report = _entry(output, "report.md", ["explicit aggregate manifest"])
    report["role"] = "report"
    manifest["artifacts"].append(report)
    save_json(output / "report_artifacts.json", manifest)
    return output / "report_artifacts.json"
