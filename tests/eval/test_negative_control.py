"""eval/negative_control.py: the corrected permutation-based negative
control (author's ruling, replacing build_corpus(relabel_world=True) as
a leakage check). Behavior and predictions stay fixed; only the
evaluation target gets shuffled.
"""
import random
from dataclasses import dataclass

from eval.negative_control import ci_overlap, permuted_archetype_labels, permuted_utility_by_session


@dataclass
class _FakeRow:
    session_id: str
    utility: float


def test_permuted_utility_stays_within_its_own_session():
    rows = [
        _FakeRow("s1", 1.0), _FakeRow("s1", 2.0), _FakeRow("s1", 3.0),
        _FakeRow("s2", 10.0), _FakeRow("s2", 20.0),
    ]
    shuffled = permuted_utility_by_session(rows, random.Random(0))
    assert sorted(shuffled[:3]) == [1.0, 2.0, 3.0]
    assert sorted(shuffled[3:]) == [10.0, 20.0]


def test_permuted_utility_actually_reshuffles_with_enough_sessions():
    """A weak randomness check: across many sessions, at least one
    session's own order should change (vanishingly unlikely not to)."""
    rows = []
    for i in range(50):
        sid = f"s{i}"
        rows += [_FakeRow(sid, 1.0), _FakeRow(sid, 2.0), _FakeRow(sid, 3.0), _FakeRow(sid, 4.0)]
    original = [r.utility for r in rows]
    shuffled = permuted_utility_by_session(rows, random.Random(1))
    assert shuffled != original


def test_permuted_archetype_labels_is_a_permutation_of_the_input():
    labels = ["skimmer", "deliberator", "price_hunter", "image_driven", "spec_reader"] * 10
    shuffled = permuted_archetype_labels(labels, random.Random(2))
    assert sorted(shuffled) == sorted(labels)
    assert shuffled != labels  # vanishingly unlikely to match by chance at n=50


def test_ci_overlap_true_when_intervals_intersect():
    assert ci_overlap((0.0, 0.1), (0.05, 0.2)) is True


def test_ci_overlap_false_when_intervals_disjoint():
    assert ci_overlap((0.0, 0.05), (0.1, 0.2)) is False


def test_ci_overlap_true_when_touching_at_an_endpoint():
    assert ci_overlap((0.0, 0.1), (0.1, 0.2)) is True
