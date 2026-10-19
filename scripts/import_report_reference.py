"""Archive audited DOCX illustrations verbatim, without clinical/model imports."""

from __future__ import annotations

import io
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

# Support the documented direct script command as well as package-based test imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import report_reference_extract as extract
from scripts import report_reference_inventory as inventory
from scripts.report_reference_construction import construction
from scripts.report_reference_inventory import Json, ReferenceManifest

A, R, W = inventory.A, inventory.R, inventory.W
CAPTIONS, HEADERS, ROW_LABELS = inventory.CAPTIONS, inventory.HEADERS, inventory.ROW_LABELS
APPENDIX_HEADINGS = inventory.APPENDIX_HEADINGS
FIGURES, SOURCE_SHA256, TABLE_FILES = (
    inventory.FIGURES,
    inventory.SOURCE_SHA256,
    inventory.TABLE_FILES,
)
sha256, text = extract.sha256, extract.text


def import_reference(
    source: Path, output: Path, *, imported_at: str | None = None
) -> ReferenceManifest:
    """Validate all evidence in memory, then write a fresh archive and manifest last."""
    if output.exists() or output.is_symlink():
        raise ValueError(f"Output already exists; a fresh destination is required: {output}")
    source_bytes = source.read_bytes()
    source_hash = sha256(source_bytes)
    if source_hash != SOURCE_SHA256:
        raise ValueError(f"Source SHA-256 mismatch: expected {SOURCE_SHA256}; got {source_hash}")
    files = {"source/PreOp_XAI_Minor_Project_Report.docx": source_bytes}
    with ZipFile(io.BytesIO(source_bytes)) as document:
        body = ET.fromstring(document.read("word/document.xml")).find(W + "body")
        if body is None:
            raise ValueError("DOCX has no document body")
        blocks = list(body)
        tables = {number: extract.extract_table(blocks, number) for number in CAPTIONS}
        relationships = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in ET.fromstring(document.read("word/_rels/document.xml.rels"))
        }
        figures: list[dict[str, str | bool]] = []
        for number, suffix, filename, image_number, image_hash in FIGURES:
            caption = f"Figure {number} Illustrative {suffix} category C"
            position = extract.caption_position(blocks, caption) - 1
            while (
                position >= 0
                and not text(blocks[position])
                and not list(blocks[position].iter(A + "blip"))
            ):
                position -= 1
            if position < 0:
                raise ValueError(f"Figure {number}: missing image before caption")
            image_references = list(blocks[position].iter(A + "blip"))
            targets = [
                relationships.get(node.attrib.get(R + "embed", "")) for node in image_references
            ]
            member = f"word/media/image{image_number}.png"
            if targets != [member.removeprefix("word/")]:
                raise ValueError(f"Figure {number}: image relationship does not match {member}")
            image = document.read(member)
            if not image.startswith(b"\x89PNG\r\n\x1a\n") or sha256(image) != image_hash:
                raise ValueError(f"Figure {number}: original PNG hash/content mismatch")
            path = f"figures/figure_{number.replace('.', '_')}_{filename}.png"
            files[path] = image
            figures.append(
                {
                    "report_figure": number,
                    "source_caption": caption,
                    "docx_member": member,
                    "evidence_category": "C",
                    "path": path,
                    "sha256": image_hash,
                    "underlying_arrays_available": False,
                }
            )
        exported_tables: list[dict[str, Json]] = []
        display_count = 0
        for number, path in TABLE_FILES.items():
            rows = extract.illustration_rows(number, tables[number])
            display_count += len(rows)
            files[path] = extract.csv_bytes(rows, inventory.ILLUSTRATION_FIELDS)
            exported_tables.append(
                {
                    "report_table": number,
                    "source_caption": CAPTIONS[number],
                    "evidence_category": "C",
                    "docx_member": "word/document.xml",
                    "path": path,
                    "sha256": sha256(files[path]),
                    "display_value_count": len(rows),
                    "underlying_arrays_available": False,
                }
            )
        if display_count != 104:
            raise ValueError("Expected exactly 104 illustrative display values")
        benchmarks: list[dict[str, str]] = []
        for number in ("5.14", "5.15"):
            benchmarks.extend(extract.context_rows(number, tables[number], "B"))
        benchmarks.extend(
            extract.paragraph_rows(
                "5.14-5.15",
                extract.section(
                    blocks,
                    "5.16.1 Published numerical benchmarks",
                    "5.16.3 Respiratory endpoint evidence decision",
                ),
                "B",
            )
        )
        benchmark_path = "tables/table_5_14_published_benchmarks.csv"
        files[benchmark_path] = extract.csv_bytes(benchmarks, inventory.CONTEXT_FIELDS)
        evidence: list[dict[str, str]] = []
        evidence_tables = ("5.12", "5.13", "5.16", "5.21", "5.22", "B.1", "C.1")
        for number in evidence_tables:
            evidence.extend(extract.context_rows(number, tables[number], "A"))
        for reference, start, end in (
            (
                "5.12-5.13",
                "5.15 Project observations and current evidence",
                "5.16.1 Published numerical benchmarks",
            ),
            (
                "5.21-5.22",
                "5.20 Explainability evidence and interpretation",
                "5.20.4 Controlled rank sensitivity illustration",
            ),
            (
                "Appendix B",
                "APPENDIX BDATA REVIEW AND PROTOCOL RECORD",
                "APPENDIX CRESULT PROVENANCE AND NUMERICAL REPRODUCIBILITY",
            ),
        ):
            evidence.extend(
                extract.paragraph_rows(reference, extract.section(blocks, start, end), "A")
            )
        metadata, appendix = construction(blocks, tables)
        for reference in ("C.1", "C.5"):
            for row in extract.paragraph_rows(reference, appendix[reference], "A"):
                if reference == "C.5":
                    row.update(status="unavailable", unavailable_reason=row["display_value"])
                evidence.append(row)
        evidence_path = "tables/evidence_status.csv"
        files[evidence_path] = extract.csv_bytes(evidence, inventory.CONTEXT_FIELDS)
        for number in ("5.14", "5.15", *evidence_tables):
            path = benchmark_path if number in ("5.14", "5.15") else evidence_path
            categories = (
                ["A", "B", "C"] if number == "C.1" else ["B" if path == benchmark_path else "A"]
            )
            exported_tables.append(
                {
                    "report_table": number,
                    "source_caption": CAPTIONS[number],
                    "evidence_categories": categories,
                    "docx_member": "word/document.xml",
                    "path": path,
                    "sha256": sha256(files[path]),
                    "underlying_arrays_available": False,
                }
            )
    files["construction.json"] = extract.json_bytes(metadata)
    exported_tables.append(
        {
            "report_table": "5.6",
            "source_caption": CAPTIONS["5.6"],
            "evidence_category": "A",
            "docx_member": "word/document.xml",
            "path": "construction.json",
            "sha256": sha256(files["construction.json"]),
            "underlying_arrays_available": False,
        }
    )
    files["README.md"] = inventory.REFERENCE_README
    manifest: ReferenceManifest = {
        "schema_version": 1,
        "evidence_kind": "report-illustration-reference",
        "source": {
            "basename": source.name,
            "sha256": source_hash,
            "bytes": len(source_bytes),
            "archived_path": "source/PreOp_XAI_Minor_Project_Report.docx",
        },
        "import_timestamp": imported_at or datetime.now(UTC).isoformat(),
        "original_inspected_revision": inventory.INSPECTED_REVISION,
        "report_source_revision": inventory.REPORT_REVISION,
        "source_inspection_date": inventory.INSPECTION_DATE,
        "historical_verification_date": inventory.HISTORICAL_DATE,
        "historical_qualification": inventory.QUALIFICATION,
        "importer_sha256": sha256(Path(__file__).read_bytes()),
        "importer_source_sha256": {
            path.name: sha256(path.read_bytes())
            for path in [
                Path(__file__),
                *sorted(Path(__file__).parent.glob("report_reference_*.py")),
            ]
        },
        "underlying_arrays_available": False,
        "tables": exported_tables,
        "figures": figures,
        "sections": [
            {
                "report_section": reference,
                "evidence_categories": ["A", "B", "C"] if reference == "C.1" else ["A"],
                "docx_member": "word/document.xml",
                "path": evidence_path,
                "sha256": sha256(files[evidence_path]),
                "underlying_arrays_available": False,
            }
            for reference in ("Appendix B", "C.1", "C.5")
        ],
        "evidence_categories": {
            "A": "Attributed project/source verification, not clinical scores.",
            "B": "Published benchmark context, not project metrics or acceptance targets.",
            "C": "Artificial report examples, not trained project model outputs.",
        },
        "files": [
            {
                "path": path,
                "sha256": sha256(data),
                "bytes": len(data),
                "evidence_categories": ["C"]
                if path.startswith("figures/") or path in TABLE_FILES.values()
                else (["B"] if path == benchmark_path else ["A", "B", "C"]),
                "underlying_arrays_available": False,
            }
            for path, data in sorted(files.items())
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    for relative, data in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = destination.write_bytes(data)
    _ = (output / "reference_manifest.json").write_bytes(extract.json_bytes(manifest))
    return manifest


def main(argv: list[str] | None = None) -> int:
    return extract.run_cli(import_reference, argv)


if __name__ == "__main__":
    raise SystemExit(main())
