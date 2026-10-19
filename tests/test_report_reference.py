"""Exact archive preservation and rejection tests against deterministic OOXML."""

import ast
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests.report_reference_fixture import (
    PNG,
    SCRIPT,
    VALUES,
    DocxFixture,
    paragraph,
    read_csv,
    reference,
)
from tests.report_reference_fixture import docx as docx


def test_exact_archive_preserves_source_images_and_all_display_values(
    docx: DocxFixture, tmp_path: Path
) -> None:
    source, _, _, _ = docx
    before = source.read_bytes()
    output = tmp_path / "reference"
    manifest = reference.import_reference(source, output, imported_at="2026-10-19T00:00:00+00:00")
    assert source.read_bytes() == before
    assert (output / manifest["source"]["archived_path"]).read_bytes() == before
    count = 0
    for number, path in reference.TABLE_FILES.items():
        rows = read_csv(output / path)
        actual = [row["display_value"] for row in rows]
        if number in ("5.18", "5.20"):
            expected = [
                part
                for row_index, row in enumerate(VALUES[number])
                for value in row
                for part in (value.split(" / ") if row_index == 1 else [value])
            ]
        else:
            expected = [value for row in VALUES[number] for value in row]
        assert actual == expected
        for row in rows:
            if row["value"]:
                assert Decimal(row["value"]) == Decimal(row["display_value"])
        assert {row["evidence_category"] for row in rows} == {"C"}
        assert {row["underlying_arrays_available"] for row in rows} == {"false"}
        count += len(rows)
    assert count == 104
    rank = read_csv(output / reference.TABLE_FILES["5.23"])
    assert [
        (row["vectors"], row["unique_pairs"])
        for row in rank
        if row["quantity"] == "Vectors / pairs"
    ] == [("10", "45"), ("10", "45")]
    for figure in manifest["figures"]:
        assert (output / figure["path"]).read_bytes() == PNG
        assert figure["sha256"] == reference.sha256(PNG)
        assert figure["evidence_category"] == "C"
    assert len(manifest["figures"]) == 8
    indexed = {entry["path"] for entry in manifest["files"]}
    present = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    assert present == indexed | {"reference_manifest.json"}
    assert len(present) == 19
    for entry in manifest["files"]:
        path = Path(entry["path"])
        assert not path.is_absolute() and ".." not in path.parts and "\\" not in entry["path"]
        assert entry["sha256"] == reference.sha256((output / path).read_bytes())
        assert entry["bytes"] == (output / path).stat().st_size
    assert manifest["original_inspected_revision"] == "1285f8409d5a0936c16f30eb964f33bbfe8e51f8"
    assert manifest["report_source_revision"] == "919a07506573b77a9113a54332379280c97a4d66"
    assert manifest["source"]["basename"] == source.name
    assert manifest["underlying_arrays_available"] is False
    assert str(tmp_path) not in json.dumps(manifest)
    assert not (
        {"metrics.json", "stability.json", "explain.json"}
        & {path.name for path in output.rglob("*")}
    )


def test_benchmark_and_evidence_cells_keep_qualifications_and_historical_dates(
    docx: DocxFixture, tmp_path: Path
) -> None:
    source, _, _, _ = docx
    output = tmp_path / "reference"
    reference.import_reference(source, output)
    benchmarks = read_csv(output / "tables/table_5_14_published_benchmarks.csv")
    assert {row["evidence_category"] for row in benchmarks} == {"B"}
    assert any(
        row["display_value"] == "mAP 0.48 / 0.50" and row["value"] == "" for row in benchmarks
    )
    assert any(row["display_value"] == "Not extracted" and row["value"] == "" for row in benchmarks)
    assert any(row["display_value"] == "0.9376" and row["value"] == "0.9376" for row in benchmarks)
    assert {"5.14", "5.15", "5.14-5.15"} == {row["report_table"] for row in benchmarks}
    evidence = read_csv(output / "tables/evidence_status.csv")
    assert {"5.12", "5.13", "5.16", "5.21", "5.22", "B.1", "C.1", "C.5", "Appendix B"} <= {
        row["report_table"] for row in evidence
    }
    historical = [row for row in evidence if row["status"] == "historical-record"]
    assert historical and {row["historical_date"] for row in historical} == {"2026-10-17"}
    assert all(row["qualification"] for row in historical)
    unavailable = [row for row in evidence if row["status"] == "unavailable"]
    assert unavailable and all(row["unavailable_reason"] for row in unavailable)
    assert {row["evidence_category"] for row in evidence if row["report_table"] == "C.1"} == {
        "A",
        "B",
        "C",
    }


def test_deterministic_output_with_fixed_timestamp(docx: DocxFixture, tmp_path: Path) -> None:
    source, _, _, _ = docx
    first, second = tmp_path / "first", tmp_path / "second"
    for output in (first, second):
        reference.import_reference(source, output, imported_at="2026-10-19T00:00:00+00:00")
    for path in first.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()


@pytest.mark.parametrize("destination_kind", ["empty_directory", "nonempty_directory", "file"])
def test_existing_destination_is_never_changed(
    docx: DocxFixture, tmp_path: Path, destination_kind: str
) -> None:
    source, _, _, _ = docx
    output = tmp_path / "existing"
    if destination_kind == "file":
        output.write_bytes(b"keep")
    else:
        output.mkdir()
        if destination_kind == "nonempty_directory":
            (output / "sentinel").write_bytes(b"keep")
    before = (
        sorted((path.name, path.read_bytes()) for path in output.iterdir())
        if output.is_dir()
        else output.read_bytes()
    )
    with pytest.raises(ValueError, match="fresh destination"):
        reference.import_reference(source, output)
    after = (
        sorted((path.name, path.read_bytes()) for path in output.iterdir())
        if output.is_dir()
        else output.read_bytes()
    )
    assert before == after


def test_wrong_source_hash_prevents_output(docx: DocxFixture, tmp_path: Path) -> None:
    source, _, _, _ = docx
    source.write_bytes(source.read_bytes() + b"tampered")
    output = tmp_path / "reference"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        reference.import_reference(source, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "damage", ["header", "display_value", "row_label", "missing_caption", "duplicate_caption"]
)
def test_caption_header_and_content_validation_is_independent_of_block_positions(
    docx: DocxFixture, tmp_path: Path, damage: str
) -> None:
    source, body, _, save = docx
    caption = next(
        node
        for node in body
        if node.tag == reference.W + "p" and reference.text(node) == reference.CAPTIONS["5.17"]
    )
    position = list(body).index(caption)
    result_table = list(body)[position + 1]
    if damage == "missing_caption":
        body.remove(caption)
    elif damage == "duplicate_caption":
        paragraph(body, reference.CAPTIONS["5.17"])
    else:
        row_index = 0 if damage == "header" else 1
        column = 0 if damage == "row_label" else 1
        row = result_table.findall(reference.W + "tr")[row_index]
        next(row.findall(reference.W + "tc")[column].iter(reference.W + "t")).text = "changed"
    save()  # Trust the fixture hash so this specifically exercises structural/content checks.
    output = tmp_path / "reference"
    with pytest.raises(ValueError, match="caption|headers|display values|row labels"):
        reference.import_reference(source, output)
    assert not output.exists()


def test_wrong_image_caption_relationship_rejected(docx: DocxFixture, tmp_path: Path) -> None:
    source, _, relationships, save = docx
    relationships[0].set("Target", "media/image99.png")
    save()
    output = tmp_path / "reference"
    with pytest.raises(ValueError, match="image relationship"):
        reference.import_reference(source, output)
    assert not output.exists()


def test_original_image_hash_is_required(
    docx: DocxFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _, _, _ = docx
    monkeypatch.setattr(
        reference, "FIGURES", [(*reference.FIGURES[0][:4], "0" * 64), *reference.FIGURES[1:]]
    )
    output = tmp_path / "reference"
    with pytest.raises(ValueError, match="original PNG hash"):
        reference.import_reference(source, output)
    assert not output.exists()


def test_actual_cli_wrong_hash_does_not_create_output(tmp_path: Path) -> None:
    source = tmp_path / "untrusted.docx"
    source.write_bytes(b"not the audited source")
    output = tmp_path / "reference"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert "Source SHA-256 mismatch" in result.stderr
    assert not output.exists()


def test_importer_has_only_standard_library_imports() -> None:
    # Every local helper is inspected too: moving an import cannot evade this boundary.
    for module in [SCRIPT, *SCRIPT.parent.glob("report_reference_*.py")]:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imports = {
            name.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for name in node.names
        }
        imports |= {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert imports <= sys.stdlib_module_names | {"__future__", "scripts"}
