"""Build an aggregate Markdown report without reading private patient artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

LIMITATIONS = [
    "Retrospective internal evaluation, when completed, is not prospective "
    "clinical validation or evidence of deployment readiness.",
    "Mortality is in-hospital mortality, not 30-day mortality. Respiratory analysis "
    "requires reviewed postoperative and explicit-negative semantics; absence of "
    "documentation is not a negative outcome.",
    "Clinical review gates, hospitalization linkage and preanesthetic availability "
    "must be established independently. This report does not approve those gates. "
    "A collection-time proxy requires an explicitly documented 24-hour-lag choice.",
    "SHAP explains model predictions under an interventional background convention. "
    "Correlated predictors can divide attribution. Contributions are log-odds, not "
    "additive probability percentage points, causal effects or treatment advice.",
    "Missingness can encode care processes and limit transportability. Unexpected "
    "directions require mapping, timing and clinical review.",
    "Bootstrap refits use fixed hyperparameters and fixed validation patients. "
    "They exclude recalibration uncertainty; ten refits support exploratory "
    "stability conclusions only.",
    "Single-center, patient-independent splits do not establish temporal or external "
    "validity. VitalDB is outside this core implementation.",
    "Patient-level arrays and local explanations are restricted artifacts and are "
    "not embedded in this aggregate report.",
]


def _load(path: Path):
    def reject_constant(value):
        raise ValueError(f"Non-standard JSON constant in {path.name}: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def build_report(output: Path, export_manifest: Path | None = None) -> Path:
    """Read metrics/explain/stability JSON below output and write report.md.

    Multiple endpoint subdirectories are supported. Missing stages are explicitly
    identified; no clinical or methodological completion is inferred.
    """
    output = Path(output)
    if export_manifest is not None:
        from preop_xai.result_manifest import read_manifest
        from preop_xai.result_report import build_export_report

        return build_export_report(output, read_manifest(export_manifest))
    output.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Preoperative prediction: aggregate research report",
        "",
        "MOVER EPIC core study. Generated from available aggregate artifacts; "
        "not a clinical approval or an endpoint-review determination.",
        "",
    ]
    status_path = output / "status.json"
    lines.extend(["## Execution and reliability status", ""])
    if status_path.exists():
        status = _load(status_path)
        if status["synthetic_only"]:
            lines.extend(["**SYNTHETIC SOFTWARE DEMONSTRATION ONLY - NO CLINICAL RESULTS.**", ""])
        lines.extend(
            [
                f"- Pipeline execution: **{status['pipeline_execution']}**.",
                f"- Data review: **{status['data_review']}**.",
                f"- Clinical use: **{status['clinical_use']}**.",
                "",
            ]
        )
        for endpoint, details in status["endpoints"].items():
            lines.extend(
                [
                    f"### {endpoint}",
                    "",
                    f"- Endpoint review: **{details['review']}**.",
                    f"- Internal evaluation: **{details['internal_validation']}**.",
                    f"- Predictive reliability: **{details['predictive_reliability']}**.",
                ]
            )
            for model, diagnostic in details["calibration"].items():
                lines.append(
                    f"- {model} calibration: **{diagnostic['calibration_status']}**; "
                    f"n={diagnostic.get('calibration_n')}, "
                    f"events={diagnostic.get('calibration_events')}, "
                    f"non-events={diagnostic.get('calibration_nonevents')}, "
                    f"intercept={diagnostic.get('calibration_intercept')}, "
                    f"slope={diagnostic.get('calibration_slope')}."
                )
            lines.append("")
        lines.extend(
            [
                "A completed run is not evidence of reliable prediction. Nonpositive-slope "
                "calibrated metrics, thresholds and SHAP are **invalid-fit research diagnostics "
                "only**. Inference rejects them by default; explicit research-only inference "
                "returns raw scores without calibrated probabilities or classifications. "
                "Unestimable calibration is unavailable, not silently replaced.",
                "",
                "Bootstrap intervals condition on fitted models, calibrators and thresholds; "
                "they exclude model-selection/recalibration uncertainty. Calibration parameter "
                "intervals are not implemented. A positive slope alone establishes "
                "no performance target.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Status evidence unavailable; execution, review and validation "
                "are not established.",
                "",
            ]
        )
    figure_index = []
    # A campaign report must not recursively ingest nested reference/other campaigns.
    aggregate_directories = [
        output,
        *(output / endpoint for endpoint in ("mortality", "respiratory")),
        *(output / endpoint / "test_explanations" for endpoint in ("mortality", "respiratory")),
    ]
    for filename, heading in (
        ("metrics.json", "Predictive performance"),
        ("stability.json", "Explanation stability"),
        ("explain.json", "SHAP explanations"),
    ):
        lines.extend([f"## {heading}", ""])
        paths = sorted(
            directory / filename
            for directory in aggregate_directories
            if (directory / filename).is_file()
        )
        if not paths:
            lines.extend([f"Not available: `{filename}`.", ""])
            continue
        for path in paths:
            relative = path.relative_to(output).as_posix()
            data = _load(path)
            lines.extend(
                [
                    f"### `{relative}`",
                    "",
                    "```json",
                    json.dumps(data, indent=2, allow_nan=False),
                    "```",
                    "",
                ]
            )
            if filename == "explain.json":
                for figure in data.get("figures", []):
                    candidate = (path.parent / figure).resolve()
                    try:
                        local = candidate.relative_to(output.resolve())
                    except ValueError:
                        raise ValueError("Figure reference escapes report directory.") from None
                    if "private" in local.parts:
                        continue
                    figure_index.append((local.as_posix(), candidate.is_file()))
    lines.extend(["## Figure index", ""])
    figure_index.extend(
        (path.relative_to(output).as_posix(), True)
        for path in sorted(directory / "calibration.png" for directory in aggregate_directories)
        if path.is_file()
    )
    if not figure_index:
        lines.extend(["No aggregate explanation figures were indexed.", ""])
    for figure, exists in dict(figure_index).items():
        status = "" if exists else " — missing file"
        lines.append(f"- [{figure}]({quote(figure)}){status}")
    lines.extend(["", "## Interpretation and limitations", ""])
    lines.extend(f"- {item}" for item in LIMITATIONS)
    lines.append("")
    target = output / "report.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
