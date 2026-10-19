"""Read-only derivative workflow against completed saved-array evidence."""

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from preop_xai import result_integrity
from preop_xai.cli import app
from preop_xai.reporting import build_report
from preop_xai.result_artifacts import export_results
from preop_xai.result_io import load_json, save_json, sha256
from tests.result_fixture import create_fixture


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    storage = tmp_path / "artifacts"
    storage.mkdir()
    monkeypatch.setattr(result_integrity, "ARTIFACTS_ROOT", storage)
    return create_fixture(storage / "completed")


def snapshot(directory: Path) -> dict[str, str]:
    return {
        p.relative_to(directory).as_posix(): sha256(p) for p in directory.rglob("*") if p.is_file()
    }


def test_cli_exports_named_predictions_without_mutating_source(campaign):
    # Given: a completed fixture whose model bytes cannot be deserialized.
    before = snapshot(campaign)
    output = campaign.with_name("exports")
    # When: running the actual Typer command.
    result = CliRunner().invoke(
        app, ["export-results", "--source", str(campaign), "--output", str(output)]
    )
    # Then: real aggregate files have valid hashes and no source byte or file changed.
    assert result.exit_code == 0, result.output
    assert snapshot(campaign) == before
    manifest = load_json(output / "report_artifacts.json")
    assert manifest["source_campaign"]["revision"] == "deterministic-export-contract-fixture"
    for artifact in manifest["artifacts"]:
        assert sha256(output / artifact["path"]) == artifact["sha256"]
        if artifact["path"].startswith("mortality/stability"):
            assert artifact["denominator"] == 4  # fixed validation n, not the test n=8
    assert not list(output.rglob("*.npz"))
    assert not list(output.rglob("*.joblib"))
    assert not list(output.rglob("private"))
    for path in output.rglob("*"):
        if path.suffix in {".json", ".csv", ".md"}:
            assert "PRIVATE_SENTINEL_PATIENT" not in path.read_text(encoding="utf-8")
    assert build_report(output, output / "report_artifacts.json").is_file()


@pytest.mark.parametrize("tamper", ["sealed", "model", "incomplete"])
def test_required_integrity_failure_creates_no_derivative(campaign, tamper):
    # Given: one independently damaged completion contract.
    if tamper == "sealed":
        (campaign / "manifest.json").write_text("{}")
    elif tamper == "model":
        (campaign / "mortality/models.joblib").write_bytes(b"changed")
    else:
        (campaign / "mortality/evaluation_complete.json").unlink()
    output = campaign.with_name("rejected")
    # When/Then: preflight fails before writing any result files.
    with pytest.raises(ValueError, match="mismatch|incomplete"):
        export_results(campaign, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "relative", ["../outside.png", "private/local.png", "PRIVATE/local.png", "C:/patient.png"]
)
def test_manifest_rejects_escaping_or_private_figure_links(campaign, relative):
    # Given: otherwise valid completed aggregate evidence with a malicious index entry.
    output = campaign.with_name("exports")
    manifest_path = export_results(campaign, output)
    manifest = load_json(manifest_path)
    manifest["artifacts"][0]["path"] = relative
    save_json(manifest_path, manifest)
    # When/Then: reporting rejects the index rather than following it.
    with pytest.raises(ValueError, match="Unsafe|escapes"):
        build_report(output, manifest_path)


def test_mortality_only_export_records_disabled_respiratory(tmp_path, monkeypatch):
    # Given: a completed mortality-only fixture.
    monkeypatch.setattr(result_integrity, "ARTIFACTS_ROOT", tmp_path)
    source = create_fixture(tmp_path / "mortality-only", respiratory=False)
    # When: exporting this campaign only.
    manifest_path = export_results(source, tmp_path / "export")
    # Then: absent endpoint is unavailable, not borrowed or replaced by zero scores.
    manifest = load_json(manifest_path)
    assert set(manifest["endpoints"]) == {"mortality"}
    assert any(r["endpoint"] == "respiratory" for r in manifest["unavailable"])
    assert not (manifest_path.parent / "respiratory").exists()


def test_export_refuses_overwrite_source_child_and_unauthorized_storage(campaign, tmp_path):
    # Given: valid saved source evidence.
    # When/Then: invalid destinations are rejected before any data are consumed.
    for destination in (campaign, campaign / "derivative", tmp_path / "outside"):
        with pytest.raises(ValueError):
            export_results(campaign, destination)


def test_legacy_report_does_not_discover_nested_campaigns(tmp_path):
    # Given: a nested campaign with invalid JSON that must not be read.
    nested = tmp_path / "other-campaign" / "mortality"
    nested.mkdir(parents=True)
    (nested / "metrics.json").write_text("not json", encoding="utf-8")
    # When: reporting the explicitly selected parent campaign.
    report = build_report(tmp_path)
    # Then: another campaign's invalid evidence cannot affect this report.
    assert report.is_file()


def test_status_only_campaign_exports_no_performance(tmp_path, monkeypatch):
    # Given: only review/audit status, without completed evaluation.
    monkeypatch.setattr(result_integrity, "ARTIFACTS_ROOT", tmp_path)
    source = tmp_path / "review-only"
    source.mkdir()
    save_json(
        source / "status.json",
        {
            "synthetic_only": False,
            "data_review": "blocked",
            "endpoints": {"mortality": {"review": "blocked"}},
        },
    )
    # When: exporting available context.
    manifest_path = export_results(source, tmp_path / "exports")
    # Then: report completion cannot invent endpoint metric rows.
    manifest = load_json(manifest_path)
    assert not manifest["endpoints"]
    assert len(manifest["unavailable"]) >= 2
    assert not (manifest_path.parent / "mortality").exists()


@pytest.mark.parametrize(
    "value",
    [
        {"schema_version": True},
        {"schema_version": 1, "source_campaign": []},
    ],
)
def test_malformed_manifest_is_rejected_at_reporting_boundary(tmp_path, value):
    # Given: malformed machine-consumed manifest data, not aggregate outputs.
    path = tmp_path / "report_artifacts.json"
    save_json(path, value)
    # When/Then: validation rejects before indexing any files.
    with pytest.raises(ValueError, match="manifest"):
        build_report(tmp_path, path)


def test_raw_only_fixture_keeps_unavailable_operating_point(campaign):
    # Given: a new synthetic fixture with explicitly unestimable mortality calibration.
    directory = campaign / "mortality"
    metrics = load_json(directory / "metrics.json")
    for model in metrics["models"].values():
        for key in (
            "calibrated",
            "calibration",
            "threshold",
            "tp",
            "fp",
            "tn",
            "fn",
            "sensitivity",
            "specificity",
            "ppv",
            "npv",
            "f1",
        ):
            model[key] = None
        model["calibration_status"] = "constant-scores"
    save_json(directory / "metrics.json", metrics)
    with np.load(directory / "predictions.npz", allow_pickle=False) as archive:
        names = archive["names"]
        keep = np.array([str(name).endswith("_raw") for name in names])
        y, probabilities = archive["y"], archive["probabilities"][keep]
    np.savez_compressed(
        directory / "predictions.npz", y=y, names=names[keep], probabilities=probabilities
    )
    # When: exporting this completed raw-only contract.
    output = campaign.with_name("raw-only-export")
    manifest = load_json(export_results(campaign, output))
    # Then: unavailable calibration is not an identity prediction or all-negative classifier.
    assert (output / "mortality/operating_point.csv").read_text().count("\n") == 1
    assert (output / "mortality/confusion_matrices.png").is_file()
    assert any(
        row.get("variant") == "calibrated" and row.get("reason") == "constant-scores"
        for row in manifest["unavailable"]
    )
