from pathlib import Path

from typer.testing import CliRunner

from preop_xai.cli import app


def _config(path: Path) -> None:
    content = """release: '1.4.2'
data_kind: synthetic
paths: {}
synthetic: {seed: 17, rows: 9}"""
    _ = path.write_text(
        content + "\n",
        encoding="utf-8",
    )


def test_doctor_cli_reports_status_without_environment_values(tmp_path: Path) -> None:
    # Given
    config_path = tmp_path / "config.yaml"
    _config(config_path)

    # When
    result = CliRunner().invoke(app, ["doctor", "--config", str(config_path)])

    # Then
    assert result.exit_code == 0
    assert "REAL_DATA_PENDING" in result.stdout
    assert "password" not in result.stdout.lower()


def test_synthetic_cli_writes_external_artifacts(tmp_path: Path) -> None:
    # Given
    repository = Path.cwd().resolve()
    run_root = tmp_path.resolve()
    assert repository not in run_root.parents
    config_path = tmp_path / "config.yaml"
    _config(config_path)

    # When
    result = CliRunner().invoke(
        app,
        [
            "synthetic",
            "--config",
            str(config_path),
            "--runs-dir",
            str(run_root),
        ],
    )

    # Then
    assert result.exit_code == 0
    assert "synthetic" in result.stdout.lower()
    assert (run_root / "synthetic" / "manifest.json").is_file()
