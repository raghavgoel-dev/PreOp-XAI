from pathlib import Path

from preop_xai.config import load_config
from preop_xai.contracts import DataKind


def test_checked_in_profiles_are_valid_and_keep_research_budgets() -> None:
    # Given
    repository = Path.cwd()

    # When
    base = load_config(repository / "configs/base.yaml", repository_root=repository)
    smoke = load_config(repository / "configs/smoke.yaml", repository_root=repository)
    research = load_config(
        repository / "configs/research.yaml",
        repository_root=repository,
    )

    # Then
    assert base.release == "1.4.2"
    assert smoke.data_kind is DataKind.SYNTHETIC
    assert research.data_kind is DataKind.REAL
    assert research.evaluation is not None
    assert research.resources is not None
    assert research.evaluation.bootstrap_replicates == 1000
    assert research.evaluation.refit_seeds == 5
    assert research.evaluation.explanation_bootstrap_refits == 50
    assert research.resources.estimator_threads == 2
