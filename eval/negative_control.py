"""The negative control (author's ruling, replacing the retracted
`build_corpus(relabel_world=True)` usage as a leakage check -- see that
function's docstring for why it never was one). The correct permutation
test holds behavior fixed and permutes ONLY the evaluation target:
sessions are generated from true utility, the ranker (or the
signal-weighting probe) is trained and predicts normally, and only then
is that fixed set of predictions scored against a shuffled utility
vector (or, for archetype accuracy, a shuffled label vector). This
severs prediction from truth while leaving the trained model, its real
predictions, and the real generative behavior completely untouched, so
any nonzero correlation/accuracy under this shuffle is leakage or
artifact by construction -- there is no other mechanism left that could
produce one.

Utility is permuted *within* each session (not globally across the
held-out pool) so the resulting rows still support a per-session rho the
same way the real condition's do, and so the control is directly
comparable stratum-for-stratum rather than mixing session sizes/modes
together in a way the real condition never does.
"""
from __future__ import annotations

import random

import numpy as np


def permuted_utility_by_session(rows, rng: random.Random) -> list[float]:
    """Returns a new utility list, same length and order as `rows`, with
    each session's own utility values shuffled among that session's own
    rows -- predictions (not returned here, already fixed on the caller
    side) are left completely alone."""
    by_session: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        by_session.setdefault(row.session_id, []).append(i)

    shuffled = [0.0] * len(rows)
    for indices in by_session.values():
        utilities = [rows[i].utility for i in indices]
        rng.shuffle(utilities)
        for i, u in zip(indices, utilities):
            shuffled[i] = u
    return shuffled


def permuted_archetype_labels(true_labels: list[str], rng: random.Random) -> list[str]:
    """The archetype-accuracy analogue: the probe's real predictions
    (from real recovered vectors) stay fixed; only the true-label vector
    they are scored against gets shuffled, globally (there is no
    per-session structure to preserve here -- one label per session
    already)."""
    shuffled = true_labels[:]
    rng.shuffle(shuffled)
    return shuffled


def ci_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Whether two (lo, hi) confidence intervals overlap at all."""
    a_lo, a_hi = a
    b_lo, b_hi = b
    return not (a_hi < b_lo or b_hi < a_lo)
