"""Smoke test for eval/ablation.py -- confirms the leave-one-out /
leave-one-family-out loop runs end to end at a tiny scale. Not a claim
about the real contribution numbers: those are reported in STATE.md and
README.md from a real-scale run (`python -m eval.ablation`), too slow
for pytest.
"""
import pytest

from eval.ablation import run_ablation
from eval.ranker import SIGNAL_NAMES
from server.features.composites import FAMILIES
from sim.embedding import build_item_vectors

try:
    build_item_vectors()
    _CATALOG_BUILT = True
except FileNotFoundError:
    _CATALOG_BUILT = False

pytestmark = pytest.mark.skipif(not _CATALOG_BUILT, reason="data/catalog.json not built — run `python -m catalog.build`")


def test_ablation_runs_end_to_end_and_covers_every_signal_and_family():
    report = run_ablation(sessions_per_condition=2)
    assert set(report["signal_contributions"].keys()) == set(SIGNAL_NAMES)
    expected_families = {f for f in FAMILIES if f != "availability"}
    assert set(report["family_contributions"].keys()) == expected_families
    for r in report["signal_contributions"].values():
        assert "mean_contribution" in r and "ci" in r
