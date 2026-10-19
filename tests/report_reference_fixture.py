"""Deterministic OOXML input and independent numerical reference snapshots."""

import base64
import csv
import importlib.util
import io
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_report_reference.py"
SPEC = importlib.util.spec_from_file_location("report_reference_importer", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
DocxFixture = tuple[Path, ET.Element, ET.Element, Callable[[], Path]]

# Independent audit snapshots, including composite Word cells and trailing zeros.
VALUES = {
    "5.17": [
        ["0.8796", "0.8796", "0.9023", "0.9023"],
        ["0.1092", "0.1092", "0.1384", "0.1384"],
        ["0.0095", "0.0094", "0.0094", "0.0092"],
        ["-0.4054", "0.0296", "0.1617", "0.0150"],
        ["-0.1490", "0.4485", "-0.4823", "0.2995"],
        ["1.0815", "1.1160", "0.8056", "1.0830"],
    ],
    "5.18": [
        ["0.006810", "0.011601"],
        ["89 / 3188 / 6712 / 11", "80 / 1842 / 8058 / 20"],
        ["0.8900", "0.8000"],
        ["0.6780", "0.8139"],
        ["0.0272", "0.0416"],
        ["0.9984", "0.9975"],
        ["0.6801", "0.8138"],
        ["0.0527", "0.0791"],
        ["3277", "1922"],
    ],
    "5.19": [
        ["0.8513", "0.8513", "0.8773", "0.8773"],
        ["0.4049", "0.4049", "0.4706", "0.4706"],
        ["0.0593", "0.0588", "0.0562", "0.0551"],
        ["-0.2778", "-0.0084", "-0.1765", "-0.0048"],
        ["-0.1933", "-0.1004", "-0.4523", "-0.0339"],
        ["1.0548", "0.9481", "0.8074", "0.9827"],
    ],
    "5.20": [
        ["0.072946", "0.080390"],
        ["619 / 2267 / 6933 / 181", "628 / 1890 / 7310 / 172"],
        ["0.7738", "0.7850"],
        ["0.7536", "0.7946"],
        ["0.2145", "0.2494"],
        ["0.9746", "0.9770"],
        ["0.7552", "0.7938"],
        ["0.3359", "0.3785"],
        ["2886", "2518"],
    ],
    "5.23": [["10 / 45", "0.9830", "1.0000", "0.0140"], ["10 / 45", "0.8139", "0.7630", "0.0395"]],
}
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII="
)


def paragraph(parent: ET.Element, value: str) -> ET.Element:
    node = ET.SubElement(parent, reference.W + "p")
    ET.SubElement(ET.SubElement(node, reference.W + "r"), reference.W + "t").text = value
    return node


def table(parent: ET.Element, rows: list[list[str]]) -> ET.Element:
    node = ET.SubElement(parent, reference.W + "tbl")
    for row in rows:
        tr = ET.SubElement(node, reference.W + "tr")
        for value in row:
            paragraph(ET.SubElement(tr, reference.W + "tc"), value)
    return node


@pytest.fixture
def docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DocxFixture:
    document = ET.Element(reference.W + "document")
    body = ET.SubElement(document, reference.W + "body")
    # A table-of-contents caption and unrelated tables cannot act as body captions.
    table(body, [[reference.CAPTIONS["5.17"]]])
    table(body, [["unrelated", "not result data"]])
    for number, caption in reference.CAPTIONS.items():
        paragraph(body, caption)
        values = VALUES.get(
            number,
            [
                ["source context"] * (len(reference.HEADERS[number]) - 1)
                for _ in reference.ROW_LABELS[number]
            ],
        )
        if number == "5.14":
            values = [
                [
                    "30-day mortality; XGBoost SNUH model",
                    "0.9376",
                    "0.1593",
                    "Best external AUROC 0.941",
                ],
                [
                    "XGBoost internal / external",
                    "0.960 / 0.932",
                    "0.216 / 0.122",
                    "Brier 0.0015 / 0.0036",
                ],
                ["Complete LR / XGBoost", "0.894 / 0.900", "mAP 0.48 / 0.50", "Prevalence 8.8%"],
                [
                    "Sparse LR / XGBoost",
                    "0.836 / 0.836",
                    "Not extracted",
                    "Probability-plot slopes 0.862 / 0.975",
                ],
                [
                    "MySurgeryRisk",
                    "Comp. 0.82-0.94; death 0.77-0.83",
                    "Not extracted",
                    "Mortality horizons 1-24 months",
                ],
            ]
        rows = [reference.HEADERS[number]] + [
            [label, *value]
            for label, value in zip(reference.ROW_LABELS[number], values, strict=True)
        ]
        table(body, rows)
    headings = [
        "5.15 Project observations and current evidence",
        "5.16.1 Published numerical benchmarks",
        "5.16.3 Respiratory endpoint evidence decision",
        "5.20 Explainability evidence and interpretation",
        "5.20.4 Controlled rank sensitivity illustration",
        "APPENDIX BDATA REVIEW AND PROTOCOL RECORD",
        "APPENDIX CRESULT PROVENANCE AND NUMERICAL REPRODUCIBILITY",
        *reference.APPENDIX_HEADINGS,
    ]
    for heading in headings:
        paragraph(body, heading)
        paragraph(body, "Preserve original qualification for " + heading)
    relationships = ET.Element("Relationships")
    for number, suffix, _, image, _ in reference.FIGURES:
        picture = paragraph(body, "")
        ET.SubElement(picture, reference.A + "blip", {reference.R + "embed": f"rId{image}"})
        ET.SubElement(
            relationships,
            "Relationship",
            {"Id": f"rId{image}", "Target": f"media/image{image}.png"},
        )
        paragraph(body, f"Figure {number} Illustrative {suffix} category C")
    path = tmp_path / "source.docx"

    def save() -> Path:
        stream = io.BytesIO()
        with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
            members = {
                "word/document.xml": ET.tostring(document),
                "word/_rels/document.xml.rels": ET.tostring(relationships),
            }
            members.update(
                {f"word/media/image{image}.png": PNG for _, _, _, image, _ in reference.FIGURES}
            )
            for name, data in sorted(members.items()):
                archive.writestr(ZipInfo(name, date_time=(2026, 10, 19, 0, 0, 0)), data)
        path.write_bytes(stream.getvalue())
        monkeypatch.setattr(reference, "SOURCE_SHA256", reference.sha256(path.read_bytes()))
        return path

    monkeypatch.setattr(
        reference, "FIGURES", [(*item[:4], reference.sha256(PNG)) for item in reference.FIGURES]
    )
    save()
    return path, body, relationships, save


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))
