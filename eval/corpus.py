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
    shuffle_utility: bool = False,
) -> list[CorpusSession]:
    """`shuffle_utility=True` is the negative control (§11 DoD item 3):
    permutes which item vector each item_id resolves to, so an agent's
    real decisions are still internally consistent (drift-diffusion over
    *some* utility) but that utility no longer has anything to do with
    the item the ranker's features describe -- exactly like
    test_generative.py's shuffled-utility control, propagated through
    the whole pipeline instead of just the raw dwell function.
    """
    item_vectors = item_vectors or build_item_vectors()
    rng = random.Random(seed)

    effective_vectors = item_vectors
    if shuffle_utility:
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
