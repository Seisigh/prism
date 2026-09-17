"""Smoke test for eval/gate1_dod.py's full pipeline at a tiny scale --
confirms it runs end to end without crashing (corpus -> ranker training
-> prediction -> signal-weighting recovery -> archetype probe -> negative
control). Not a DoD claim: see STATE.md for the real-scale run and its
numbers, and eval/gate1_dod.py's own docstring for why the real run isn't
a pytest test.
"""
import pytest

from eval.gate1_dod import run
from sim.embedding import build_item_vectors

try:
    build_item_vectors()
    _CATALOG_BUILT = True
except FileNotFoundError:
    _CATALOG_BUILT = False

pytestmark = pytest.mark.skipif(not _CATALOG_BUILT, reason="data/catalog.json not built — run `python -m catalog.build`")


def test_pipeline_runs_end_to_end_without_crashing():
    report = run(sessions_per_condition=2)
    assert "real" in report and "negative_control" in report
    for key in ("overall_rho", "per_session_mean_rho", "archetype_accuracy", "per_mode_rho"):
        assert key in report["real"]
        assert key in report["negative_control"]
