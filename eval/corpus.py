"""Builds the simulated training/eval corpus for Gate 1: many sessions
across all five archetypes and a mix of goal conditions, so every
browsing mode gets meaningful representation (BUILD_BRIEF.md §11's
"Per-mode metrics reported separately" requires enough per-mode data to
report on in the first place).

Goal-condition mix per archetype, mirroring tests/sim/test_session.py's
own recipe for getting each mode to actually emerge:

- goalless, short pool               -> discovery
- item-goal                           -> directed_search
- category-goal                       -> broad_search
- near-substitute-heavy pool           -> comparison (+ discovery)
- long, slow, revisit-heavy session   -> refind (+ discovery)
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from eval.features import ViewFeatureRow, extract_session_features
from sim.agents import ARCHETYPES
from sim.embedding import ItemVector, build_item_vectors
from sim.session import SessionGoal, SimulatedSession, simulate_session


@dataclass(frozen=True)
class CorpusSession:
    session: SimulatedSession
    rows: list[ViewFeatureRow]


def _substitute_pools(item_vectors: dict[str, ItemVector]) -> list[list[ItemVector]]:
    by_set: dict[str, list[ItemVector]] = {}
    for v in item_vectors.values():
        if v.near_substitute_set_id is not None:
            by_set.setdefault(v.near_substitute_set_id, []).append(v)
    return [items for items in by_set.values() if len(items) >= 2]


def build_corpus(
    item_vectors: dict[str, ItemVector] | None = None,
    sessions_per_condition: int = 8,
    seed: int = 0,
    relabel_world: bool = False,
) -> list[CorpusSession]:
    """`relabel_world=True` -- renamed from `shuffle_utility` after the
    author's ruling that it had been miscited as a leakage-detecting
    negative control, which it never was. **What it does:** permutes
    which item vector each item_id resolves to, then generates *both*
    the simulated behavior *and* the evaluation target (`row.utility`)
    from that same permuted mapping -- a fully self-consistent replay of
    the real generative mechanism against an arbitrarily relabeled
    catalog. Mode assignment, archetype identity, and the taste-vector
    structure are all still real and intact under the permutation; only
    the item_id <-> vector mapping changes.

    **What it tests:** whether the pipeline is keyed to specific item
    identities rather than to the behavior->feature->utility mechanism
    itself -- a legitimate and useful robustness check, still run and
    still worth reporting.

    **What it does NOT test, and must never again be cited as testing:**
    leakage. Because both the behavior and its own evaluation target come
    from the same permuted mapping, there is no reason a well-functioning
    pipeline should collapse to zero rho under this permutation, and
    empirically it does not (see STATE.md's "Rebuilding the negative
    control" section) -- a diagnostic pass found this condition producing
    reliably nonzero, sometimes higher-than-real rho across three
    independent runs, which is what triggered the rebuild. The actual
    leakage / signal-vs-noise check is `eval/negative_control.py`'s
    evaluation-target permutation, which holds real behavior and real
    predictions fixed and shuffles only what those predictions are
    scored against.
    """
    item_vectors = item_vectors or build_item_vectors()
    rng = random.Random(seed)

    effective_vectors = item_vectors
    if relabel_world:
        ids = list(item_vectors.keys())
        shuffled_ids = ids[:]
        rng.shuffle(shuffled_ids)
        effective_vectors = {
            real_id: ItemVector(
                item_id=real_id,
                category=item_vectors[real_id].category,
                vector=item_vectors[shuffled_id].vector,
                near_substitute_set_id=item_vectors[real_id].near_substitute_set_id,
            )
            for real_id, shuffled_id in zip(ids, shuffled_ids)
        }

    kitchen = [v for v in effective_vectors.values() if v.category == "Kitchen & Dining"]
    pools = _substitute_pools(effective_vectors)

    corpus: list[CorpusSession] = []
    session_counter = 0

    def _run(archetype_name: str, goal: SessionGoal | None, pool: list[ItemVector], n_items: int, revisit_prob: float = 0.15):
        nonlocal session_counter
        session_counter += 1
        sid = f"sess-{session_counter:05d}"
        session = simulate_session(
            sid, ARCHETYPES[archetype_name], pool, n_items, rng, goal=goal or SessionGoal(), revisit_prob=revisit_prob
        )
        rows = extract_session_features(session, effective_vectors)
        if rows:
            corpus.append(CorpusSession(session=session, rows=rows))

    for archetype_name in ARCHETYPES:
        for _ in range(sessions_per_condition):
            _run(archetype_name, None, kitchen, 15)
            target = rng.choice(kitchen)
            _run(archetype_name, SessionGoal(target_item_id=target.item_id), kitchen, 15)
            _run(archetype_name, SessionGoal(target_category="Kitchen & Dining"), kitchen, 15)
            if pools:
                pool = rng.choice(pools)
                _run(archetype_name, None, pool, len(pool))
            _run(archetype_name, None, kitchen, 60, revisit_prob=0.35)

    return corpus
