import hashlib
import json
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from preop_xai.acquire.plan import DownloadPlan
from preop_xai.capabilities import CapabilityManifest
from preop_xai.cli import app


def _config(path: Path, raw_root: Path, work_root: Path, *, synthetic: bool) -> None:
    data_kind = "synthetic" if synthetic else "real"
    content = f"""release: '1.4.2'
data_kind: {data_kind}
paths:
  inspire_data_dir: '{raw_root.as_posix()}'
  private_work_dir: '{work_root.as_posix()}'
synthetic: {{seed: 17, rows: 9}}"""
    _ = path.write_text(content + "\n", encoding="utf-8")


def test_acquisition_commands_are_registered() -> None:
    # Given / When
    result = CliRunner().invoke(app, ["--help"])

    # Then
    assert result.exit_code == 0
    for command in (
        "plan-download",
        "download-data",
        "verify-data",
        "prepare-data",
        "audit-data",
    ):
        assert command in result.stdout


def test_plan_download_writes_external_plan(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    raw_root.mkdir()
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=False)
    inventory = {
        "release": "1.4.2",
        "files": [
            {
                "logical_role": "operations",
                "relative_path": "release/table.csv",
                "url": "https://physionet.org/files/inspire/1.4.2/table.csv",
                "size_bytes": 12,
                "sha256": "0" * 64,
            }
        ],
    }
    _ = (raw_root / "inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

    # When
    result = CliRunner().invoke(
        app,
        ["plan-download", "--config", str(config), "--scope", "full-release"],
    )

    # Then
    assert result.exit_code == 0
    assert "12" in result.stdout
    plan = DownloadPlan.model_validate_json(
        (raw_root / "download-plan.json").read_text(encoding="utf-8")
    )
    assert plan.entries[0].logical_role == "operations"


def test_plan_download_rejects_inventory_release_mismatch(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    raw_root.mkdir()
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=False)
    inventory: dict[str, object] = {"release": "9.9.9", "files": []}
    _ = (raw_root / "inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

    # When
    result = CliRunner().invoke(app, ["plan-download", "--config", str(config)])

    # Then
    assert result.exit_code != 0
    assert not (raw_root / "download-plan.json").exists()


def test_verify_and_prepare_write_only_external_artifacts(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    source = raw_root / "release" / "table.csv"
    source.parent.mkdir(parents=True)
    content = b"patient_id,value\n1,2\n"
    _ = source.write_bytes(content)
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=False)
    plan = {
        "release": "1.4.2",
        "entries": [
            {
                "logical_role": "operations",
                "relative_path": "release/table.csv",
                "url": "https://physionet.org/files/inspire/1.4.2/table.csv",
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    _ = (raw_root / "download-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    work_root.mkdir()
    mappings = [
        {
            "logical_role": "operations",
            "relative_path": "release/table.csv",
            "format": "csv",
        }
    ]
    _ = (work_root / "table-mappings.json").write_text(
        json.dumps(mappings), encoding="utf-8"
    )

    # When
    verify_result = CliRunner().invoke(app, ["verify-data", "--config", str(config)])
    prepare_result = CliRunner().invoke(app, ["prepare-data", "--config", str(config)])

    # Then
    assert verify_result.exit_code == 0
    assert prepare_result.exit_code == 0
    assert (raw_root / "verification-manifest.json").is_file()
    derived = work_root / "derived" / "operations.parquet"
    assert pl.read_parquet(derived).to_dicts() == [{"patient_id": 1, "value": 2}]


def test_audit_data_writes_synthetic_capability_report(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    raw_root.mkdir()
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=True)

    # When
    result = CliRunner().invoke(app, ["audit-data", "--config", str(config)])

    # Then
    assert result.exit_code == 0
    report = CapabilityManifest.model_validate_json(
        (work_root / "audit-report.json").read_text(encoding="utf-8")
    )
    assert report.data_kind == "synthetic"
    assert report.mortality.status == "supported"


def test_prepare_data_requires_verification_manifest(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    source = raw_root / "release" / "table.csv"
    source.parent.mkdir(parents=True)
    _ = source.write_text("patient_id,value\n1,2\n", encoding="utf-8")
    work_root.mkdir()
    _ = (work_root / "table-mappings.json").write_text(
        json.dumps(
            [
                {
                    "logical_role": "operations",
                    "relative_path": "release/table.csv",
                    "format": "csv",
                }
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=False)

    # When
    result = CliRunner().invoke(app, ["prepare-data", "--config", str(config)])

    # Then
    assert result.exit_code != 0
    assert not (work_root / "derived" / "operations.parquet").exists()


def test_real_audit_rejects_synthetic_evidence(tmp_path: Path) -> None:
    # Given
    raw_root = tmp_path / "raw"
    work_root = tmp_path / "work"
    raw_root.mkdir()
    work_root.mkdir()
    _ = (work_root / "audit-evidence.json").write_text(
        json.dumps({"data_kind": "synthetic"}), encoding="utf-8"
    )
    config = tmp_path / "config.yaml"
    _config(config, raw_root, work_root, synthetic=False)

    # When
    result = CliRunner().invoke(app, ["audit-data", "--config", str(config)])

    # Then
    assert result.exit_code != 0
    assert not (work_root / "audit-report.json").exists()
