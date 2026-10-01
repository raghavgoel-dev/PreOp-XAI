from pathlib import Path

from preop_xai.config import load_config
from preop_xai.doctor import ReadinessStatus, build_doctor_report


def test_doctor_separates_software_and_real_data_readiness(tmp_path: Path) -> None:
    # Given
    config_path = tmp_path / "config.yaml"
    content = """release: '1.4.2'
data_kind: synthetic
paths: {}
synthetic: {seed: 7, rows: 8}"""
    _ = config_path.write_text(
        content + "\n",
        encoding="utf-8",
    )
    config = load_config(config_path, repository_root=tmp_path / "repository")

    # When
    report = build_doctor_report(config)

    # Then
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["python"] is ReadinessStatus.READY
    assert statuses["real_data"] is ReadinessStatus.BLOCKED
    assert statuses["credentials"] is ReadinessStatus.NOT_REQUIRED
    assert report.data_status == "REAL_DATA_PENDING"
