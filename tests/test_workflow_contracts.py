"""Boundaries that keep clinical review and frozen test access explicit."""

from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from preop_xai.cli import app
from preop_xai.config import load_settings, require_review
from preop_xai.workflow import run_stage


def test_default_clinical_training_is_rejected_before_data_access():
    # Given: the shipped unreviewed configuration, with no fitted data products.
    runner = CliRunner()
    # When: requesting the actual training command.
    result = runner.invoke(app, ["train", "--config", "configs/study.yaml"])
    # Then: review, not a missing data file, blocks training.
    assert result.exit_code == 1
    assert "Clinical review required" in result.output


def test_respiratory_stays_disabled_without_its_own_review():
    # Given: mortality review alone is approved.
    settings = replace(load_settings(Path("configs/study.yaml")), approved=True)
    # When/Then: respiratory still requires its independent ascertainment decision.
    with pytest.raises(ValueError, match="Respiratory endpoint stopped"):
        require_review(settings, "respiratory")


def test_test_partition_is_unreadable_before_freeze(tmp_path):
    # Given: review is approved, but there is no frozen analysis or test table.
    settings = replace(
        load_settings(Path("configs/study.yaml")),
        approved=True,
        output_dir=tmp_path,
    )
    # When/Then: evaluation fails at the freeze gate, before attempting test I/O.
    with pytest.raises(ValueError, match="Freeze models"):
        run_stage("evaluate", settings, partition="test")
    assert not (tmp_path / "mortality/evaluation_started.json").exists()


def test_training_cannot_modify_frozen_analysis(tmp_path):
    # Given: a frozen experiment already exists.
    directory = tmp_path / "mortality"
    directory.mkdir()
    (directory / "freeze.json").write_text("{}")
    settings = replace(
        load_settings(Path("configs/study.yaml")),
        approved=True,
        output_dir=tmp_path,
    )
    # When/Then: development stops before reading or fitting any training table.
    with pytest.raises(ValueError, match="Analysis is frozen"):
        run_stage("train", settings)
