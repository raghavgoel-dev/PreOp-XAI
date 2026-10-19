"""Independent source-to-archive QA, including actual CLI rejection receipts.

Run: uv run --locked python tests/reference_verification.py --source DOCX
     --archive ARCHIVE --receipt NEW_JSON
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
Json = str | int | float | bool | None | Sequence["Json"] | Mapping[str, "Json"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify(source: Path, archive: Path) -> dict[str, Json]:
    source_bytes = source.read_bytes()
    expected = "b20b62dc2e612846c59eba6a3fa7e37876dc70bbb5de48460c89e26d0c19a8c9"
    assert digest(source_bytes) == expected
    manifest = json.loads((archive / "reference_manifest.json").read_text(encoding="utf-8"))
    assert manifest["underlying_arrays_available"] is False
    assert (archive / manifest["source"]["archived_path"]).read_bytes() == source_bytes
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        assert digest((archive / relative).read_bytes()) == entry["sha256"]
    values = 0
    with ZipFile(source) as document:
        body = ET.fromstring(document.read("word/document.xml")).find(W + "body")
        assert body is not None
        blocks = list(body)

        def text(element):
            return "".join(part.text or "" for part in element.iter(W + "t"))

        for table in manifest["tables"]:
            if table["path"] == "construction.json":
                continue
            caption = table["source_caption"]
            positions = [
                i for i, node in enumerate(blocks) if node.tag == W + "p" and text(node) == caption
            ]
            assert len(positions) == 1
            position = positions[0] + 1
            while blocks[position].tag == W + "p" and not text(blocks[position]):
                position += 1
            assert blocks[position].tag == W + "tbl"
            original = [
                [text(cell) for cell in row.findall(W + "tc")]
                for row in blocks[position].findall(W + "tr")
            ]
            exported = [
                row
                for row in rows(archive / table["path"])
                if row["report_table"] == table["report_table"]
            ]
            if table.get("evidence_category") == "C":
                expected_values = [
                    part
                    for row in original[1:]
                    for value in row[1:]
                    for part in (value.split(" / ") if row[0] == "TP / FP / TN / FN" else [value])
                ]
                assert [row["display_value"] for row in exported] == expected_values
                assert all(row["evidence_category"] == "C" for row in exported)
                for row in exported:
                    if row["value"]:
                        assert Decimal(row["value"]) == Decimal(row["display_value"])
                values += len(expected_values)
            else:
                expected_cells = {
                    (row[0], field): value
                    for row in original[1:]
                    for field, value in zip(original[0][1:], row[1:], strict=True)
                }
                assert {
                    (row["row_label"], row["field"]): row["display_value"]
                    for row in exported
                    if row["record_type"] == "table_cell"
                } == expected_cells
        for figure in manifest["figures"]:
            assert figure["evidence_category"] == "C"
            assert document.read(figure["docx_member"]) == (archive / figure["path"]).read_bytes()
    assert values == 104 and len(manifest["figures"]) == 8
    assert source.read_bytes() == source_bytes
    return {
        "status": "PASS",
        "display_values": values,
        "byte_identical_images": 8,
        "hashed_archive_files": len(manifest["files"]),
        "source_sha256": expected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError("Receipt already exists.")
    result = verify(args.source, args.archive)
    command = [
        sys.executable,
        "scripts/import_report_reference.py",
        "--source",
        str(args.source),
        "--output",
        str(args.archive),
    ]
    before = {
        p.relative_to(args.archive).as_posix(): digest(p.read_bytes())
        for p in args.archive.rglob("*")
        if p.is_file()
    }
    rejection = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert rejection.returncode == 2 and "already exists" in rejection.stderr
    assert before == {
        p.relative_to(args.archive).as_posix(): digest(p.read_bytes())
        for p in args.archive.rglob("*")
        if p.is_file()
    }
    result["overwrite"] = {"command": command, "exit": 2, "stderr": rejection.stderr}
    with tempfile.TemporaryDirectory(
        prefix="reference-rejection-", dir=os.environ["TMPDIR"]
    ) as tmp:
        wrong = Path(tmp) / "wrong.docx"
        wrong.write_bytes(b"not the supplied source")
        command = [
            sys.executable,
            "scripts/import_report_reference.py",
            "--source",
            str(wrong),
            "--output",
            str(Path(tmp) / "rejected"),
        ]
        rejection = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
        assert rejection.returncode == 2 and "SHA-256 mismatch" in rejection.stderr
        assert not (Path(tmp) / "rejected").exists()
        result["wrong_source"] = {"command": command, "exit": 2, "stderr": rejection.stderr}
    result["temporary_cleanup"] = not Path(tmp).exists()
    args.receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
