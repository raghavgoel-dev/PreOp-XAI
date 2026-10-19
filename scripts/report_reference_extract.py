"""Caption-driven DOCX extraction and archive command parsing; standard library only."""

import argparse
import csv
import hashlib
import io
import json
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile

from scripts.report_reference_inventory import (
    CAPTIONS,
    DISPLAY_ROWS,
    HEADERS,
    HISTORICAL_DATE,
    INSPECTION_DATE,
    QUALIFICATION,
    REPORT_REVISION,
    ROW_LABELS,
    ReferenceManifest,
    W,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text(node: ET.Element) -> str:
    return "".join(item.text or "" for item in node.iter(W + "t"))


def caption_position(blocks: list[ET.Element], caption: str) -> int:
    matches = [i for i, node in enumerate(blocks) if node.tag == W + "p" and text(node) == caption]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one caption {caption!r}; found {len(matches)}")
    return matches[0]


def extract_table(blocks: list[ET.Element], number: str) -> list[list[str]]:
    position = caption_position(blocks, CAPTIONS[number]) + 1
    while position < len(blocks) and blocks[position].tag == W + "p" and not text(blocks[position]):
        position += 1
    if position == len(blocks) or blocks[position].tag != W + "tbl":
        raise ValueError(f"Table {number}: caption is not followed by a table")
    rows = [
        [text(cell) for cell in row.findall(W + "tc")] for row in blocks[position].findall(W + "tr")
    ]
    if not rows or rows[0] != HEADERS[number]:
        raise ValueError(f"Table {number}: headers do not match the audited report")
    if [row[0] for row in rows[1:] if row] != ROW_LABELS[number]:
        raise ValueError(f"Table {number}: row labels do not match the audited report")
    if any(len(row) != len(rows[0]) or any(not cell for cell in row) for row in rows):
        raise ValueError(f"Table {number}: invalid row width or empty content")
    if number in DISPLAY_ROWS:
        expected = [line.split("|") for line in DISPLAY_ROWS[number].splitlines()]
        if [row[1:] for row in rows[1:]] != expected:
            raise ValueError(f"Table {number}: display values do not match the audit")
    return rows


def section(blocks: list[ET.Element], start: str, end: str | None) -> list[str]:
    first = caption_position(blocks, start) + 1
    last = len(blocks) if end is None else caption_position(blocks, end)
    if last <= first:
        raise ValueError(f"Invalid section bounds: {start!r}, {end!r}")
    return [text(node) for node in blocks[first:last] if node.tag == W + "p" and text(node)]


def numeric(display: str) -> str:
    try:
        value = Decimal(display)
    except InvalidOperation:
        return ""
    if not value.is_finite():
        raise ValueError(f"Nonfinite report value: {display!r}")
    return format(value.normalize(), "f")


def csv_bytes(rows: list[dict[str, str]], fields: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def illustration_rows(number: str, table: list[list[str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    endpoint = {
        "5.17": "mortality",
        "5.18": "mortality",
        "5.19": "respiratory",
        "5.20": "respiratory",
    }.get(number, "")
    cells = [
        (column, row[0], row[column], row[0] if number == "5.23" else table[0][column])
        for row in table[1:]
        for column in range(1, len(row))
    ]
    for column, label, display, series in cells:
        quantity = table[0][column] if number == "5.23" else label
        values = (
            zip(("TP", "FP", "TN", "FN"), display.split(" / "), strict=True)
            if quantity == "TP / FP / TN / FN"
            else [(quantity, display)]
        )
        for name, value in values:
            model = "" if number == "5.23" else ("LR" if series.startswith("LR") else "XGBoost")
            variant = series.rsplit(" ", 1)[-1] if number in ("5.17", "5.19") else "scenario"
            vectors, pairs = display.split(" / ") if quantity == "Vectors / pairs" else ("", "")
            rows.append(
                {
                    "report_table": number,
                    "evidence_category": "C",
                    "endpoint": endpoint,
                    "model": model,
                    "variant": variant,
                    "condition": label if number == "5.23" else "",
                    "quantity": name,
                    "value": numeric(value),
                    "display_value": value,
                    "vectors": vectors,
                    "unique_pairs": pairs,
                    "source_quantity": label,
                    "source_column": table[0][column],
                    "source_display_value": display,
                    "underlying_arrays_available": "false",
                }
            )
    return rows


def context_rows(number: str, table: list[list[str]], category: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in table[1:]:
        for field, display in zip(table[0][1:], row[1:], strict=True):
            evidence = row[0][0] if number == "C.1" else category
            historical = (
                row[0].startswith("Repository-recorded")
                or (
                    number == "5.13"
                    and row[0]
                    in (
                        "Raw source size",
                        "Duplicate and timing flags",
                        "Software demonstration",
                        "Verification status",
                    )
                )
                or (number == "5.21" and row[0] in ("Global and local SHAP", "Refits and pairs"))
                or (number == "C.1" and evidence == "A")
            )
            unavailable = number == "B.1" or (
                (number, row[0])
                in {
                    ("5.12", "Clinical evaluation"),
                    ("5.13", "Indexed cohort and exclusions"),
                    ("5.13", "Clinical events and prevalence"),
                    ("5.13", "Clinical partitions and model scores"),
                    ("5.13", "Availability and mapping"),
                    ("5.16", "Postoperative meaning"),
                    ("5.16", "Explicit positives and negatives"),
                    ("5.16", "Assessability, contradictions and events"),
                    ("5.16", "Modeling decision"),
                    ("5.21", "LR coefficients and odds"),
                    ("5.21", "Global and local SHAP"),
                    ("5.21", "Clinical rank Spearman / top-five Jaccard"),
                    ("5.21", "Clinical SHAP variability"),
                    ("5.21", "Cross-model agreement"),
                }
            )
            rows.append(
                {
                    "report_table": number,
                    "evidence_category": evidence,
                    "record_type": "table_cell",
                    "row_label": row[0],
                    "field": field,
                    "value": numeric(display),
                    "display_value": display,
                    "status": "unavailable"
                    if unavailable
                    else ("historical-record" if historical else "source-evidence-only"),
                    "unavailable_reason": display if unavailable else "",
                    "historical_date": HISTORICAL_DATE if historical else "",
                    "source_inspection_date": INSPECTION_DATE,
                    "source_revision": REPORT_REVISION,
                    "qualification": QUALIFICATION
                    if evidence == "A"
                    else (
                        "Attributed report context; not independently publication-verified "
                        "or a campaign score."
                        if evidence == "B"
                        else "Artificial report example, not trained project models."
                    ),
                }
            )
    return rows


def paragraph_rows(reference: str, paragraphs: list[str], category: str) -> list[dict[str, str]]:
    return [
        {
            "report_table": reference,
            "evidence_category": category,
            "record_type": "source_paragraph",
            "row_label": str(index),
            "field": "source_text",
            "value": "",
            "display_value": paragraph,
            "status": "source-context-only",
            "unavailable_reason": "",
            "historical_date": "",
            "source_inspection_date": INSPECTION_DATE,
            "source_revision": REPORT_REVISION,
            "qualification": QUALIFICATION
            if category == "A"
            else (
                "Published context only; preserve metric definitions, "
                "variants, horizons and populations."
            ),
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def run_cli(
    import_reference: Callable[[Path, Path], ReferenceManifest], argv: list[str] | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", type=Path, required=True)
    _ = parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = import_reference(args.source, args.output)
    except (OSError, ValueError, BadZipFile, ET.ParseError, KeyError) as error:
        parser.exit(2, f"Reference import rejected: {error}\n")
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "source_sha256": manifest["source"]["sha256"],
                "illustrative_display_values": 104,
                "original_pngs": len(manifest["figures"]),
                "archived_files": len(manifest["files"]) + 1,
                "underlying_arrays_available": False,
            },
            indent=2,
        )
    )
    return 0
