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
    assert "rho" in report and "archetype_accuracy" in report
    for key in (
        "real_per_session_mean", "real_per_session_ci", "control_per_session_mean", "control_per_session_ci",
        "gate_pass", "ceiling_per_session_mean", "efficiency", "per_mode_per_session_mean",
    ):
        assert key in report["rho"]
    for key in ("real", "real_ci", "control", "control_ci", "gate_pass", "ceiling", "efficiency_chance_adjusted"):
        assert key in report["archetype_accuracy"]
    assert "gate1_closed" in report
