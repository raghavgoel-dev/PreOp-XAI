"""Build an aggregate Markdown report without reading private patient artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

LIMITATIONS = [
    "This is retrospective internal validation in MOVER EPIC, not prospective "
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


def build_report(output: Path) -> Path:
    """Read metrics/explain/stability JSON below output and write report.md.

    Multiple endpoint subdirectories are supported. Missing stages are explicitly
    identified; no clinical or methodological completion is inferred.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Preoperative prediction: aggregate research report",
        "",
        "MOVER EPIC core study. Generated from available aggregate artifacts; "
        "not a clinical approval or an endpoint-review determination.",
        "",
    ]
    figure_index = []
    for filename, heading in (
        ("metrics.json", "Predictive performance"),
        ("stability.json", "Explanation stability"),
        ("explain.json", "SHAP explanations"),
    ):
        lines.extend([f"## {heading}", ""])
        paths = sorted(
            path
            for path in output.rglob(filename)
            if "private" not in path.relative_to(output).parts
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
