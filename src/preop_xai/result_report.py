"""Render only explicitly indexed and hash-validated aggregate export files."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from urllib.parse import quote

from preop_xai.result_io import aggregate_path
from preop_xai.result_manifest import ExportManifest, linked_source, validate_manifest

REPORT_MAP = {
    "campaign_summary": "Tables 5.12-5.13, 5.16, 5.21-5.22",
    "discrimination_calibration": "Tables 5.17 / 5.19",
    "operating_point": "Tables 5.18 / 5.20",
    "roc_pr": "Figures 5.7 / 5.11",
    "calibration_quantile": "Figures 5.8 / 5.12",
    "confusion_matrices": "Figures 5.9 / 5.13",
    "endpoint_comparison": "Figure 5.10",
    "stability": "Table 5.23 / Figure 5.14 (actual paired-refit evidence, not illustrations)",
}


def _table(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = list(reader)
    if not rows:
        return ["Unavailable: no supported rows in source evidence.", ""]

    def cell(value: str) -> str:
        if not value:
            return "unavailable"
        try:
            return f"{float(value):.6g}"
        except ValueError:
            return value.replace("|", "\\|").replace("\n", " ")

    return [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *["| " + " | ".join(cell(row[c]) for c in columns) + " |" for row in rows],
        "",
    ]


def build_export_report(output: Path, manifest: ExportManifest) -> Path:
    validate_manifest(output, manifest)
    source = manifest["source_campaign"]
    lines = [
        "# Saved campaign result artifacts",
        "",
        f"**Evidence: {source['evidence_kind']}; campaign: {source['identity']}.**",
        "Synthetic fixtures are software evidence, not clinical results. Clinical review "
        "and reliable prediction are not established by export or report completion.",
        "",
        f"Historical campaign revision: `{source['revision']}`. "
        f"Derivative exporter revision: `{manifest['exporter']['revision']}` "
        "(working-tree source hashes are recorded separately).",
        "",
        "## Report-number mapping",
        "",
        *[f"- {number}: `{role}`." for role, number in REPORT_MAP.items()],
        "",
        "## Availability and calibration",
        "",
    ]
    for row in manifest["unavailable"]:
        lines.append(
            f"- {row.get('endpoint', 'campaign')}: {row.get('role')}: {row.get('reason')}."
        )
    lines.extend(
        [
            "",
            "Finite nonpositive-slope fits are **invalid-diagnostic-only**, never valid risks. "
            "Unestimable calibration has no calibrated probabilities or operating point. "
            "Thresholds are validation-selected and applied using p >= threshold.",
            "",
            "AP is average precision, not trapezoidal PR area, and is prevalence-dependent. "
            "Brier is lower-is-better. Training-prevalence Brier and descriptive test-prevalence "
            "Brier are distinct. Quantile bins are descriptive, separate from five protocol bins. "
            "Stability error bars are across-refit sample SD (ddof=1), not confidence intervals.",
            "",
            "## Aggregate artifact index",
            "",
        ]
    )
    presentations = {
        "campaign_summary.csv",
        "discrimination_calibration.csv",
        "operating_point.csv",
        "confusion_counts.csv",
        "endpoint_comparison.csv",
        "stability_summary.csv",
        "stability_importance.csv",
    }
    for entry in manifest["artifacts"]:
        if entry["role"] == "report":
            continue
        relative = entry["path"]
        path = aggregate_path(output, relative)
        lines.extend([f"### {relative}", "", f"[Download {entry['role']}]({quote(relative)})", ""])
        if path.suffix == ".png":
            lines.extend([f"![{entry['role']}]({quote(relative)})", ""])
        elif path.name in presentations:
            lines.extend(_table(path))
    lines.extend(["## Provenance limitations", ""])
    for link in manifest["source_links"]:
        path = linked_source(output, manifest, link)
        relative = Path(os.path.relpath(path, output)).as_posix()
        lines.append(
            f"- [Source LR coefficients with original scaling/encoding]({quote(relative)})."
        )
    lines.extend(f"- {item}" for item in manifest["legacy_provenance_limitations"])
    lines.extend(
        [
            "",
            "Patient records, individual predictions, private arrays and local explanations "
            "are excluded. Aggregate storage is not permission to publish. Existing model "
            "coefficients retain their source scaling/encoding qualifications; no odds ratios "
            "or reference categories are inferred.",
            "",
        ]
    )
    target = output / "report.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
