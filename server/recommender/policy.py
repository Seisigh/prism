"""Epsilon-greedy recommendation policy with a permanent random-policy
session fraction (BUILD_BRIEF.md §12: "Epsilon-greedy recommender...
A permanent fraction of sessions served a uniformly random policy") and
propensity logging (§7.2's `rec_impression`: "Log propensities from the
first commit, including while the policy is random.").

**`RANDOM_POLICY_SESSION_FRACTION = 0.05` is a declared default, not a
measured or tuned value** — the brief specifies that a permanent holdout
fraction must exist (for later off-policy evaluation, §13), not what
size it should be. Flagged as a value to revisit rather than treated as
settled; changing it only affects the fraction of sessions used as an
unbiased evaluation holdout, never the ranker or taste vector themselves.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from server.recommender.catalog_view import CatalogItem
from server.recommender.mmr import mmr_rerank, rank_by_cosine

RANDOM_POLICY_SESSION_FRACTION = 0.05
DEFAULT_EPSILON = 0.1
DEFAULT_DIVERSITY_LAMBDA = 0.5


def is_random_policy_session(session_id: str, fraction: float = RANDOM_POLICY_SESSION_FRACTION) -> bool:
    """Deterministic and stable for the life of the session: hash
    `session_id` to a value in [0, 1) and compare against `fraction`, so
    a session's holdout assignment never changes mid-session and never
    needs to be persisted anywhere separately from the session_id
    itself."""
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    fraction_point = int(digest[:8], 16) / 0xFFFFFFFF
    return fraction_point < fraction


@dataclass(frozen=True)
class RecommendationSlate:
    item_ids: list[str]
    policy_id: str  # "random" | "epsilon_greedy" -- logged verbatim in rec_impression
    propensities: list[float]  # P(item shown at this slot | policy), same order as item_ids


def recommend(
    session_id: str,
    taste_vector: tuple[float, ...],
    candidates: dict[str, CatalogItem],
    k: int,
    rng: random.Random,
    epsilon: float = DEFAULT_EPSILON,
    diversity_lambda: float = DEFAULT_DIVERSITY_LAMBDA,
) -> RecommendationSlate:
    """§7.2 requires propensities logged "from the first commit,
    including while the policy is random" -- both branches below always
    return one, never `None`, so there is no code path where a
    rec_impression could be logged without one."""
    pool_ids = list(candidates.keys())
    n = min(k, len(pool_ids))
    if n == 0:
        return RecommendationSlate(item_ids=[], policy_id="epsilon_greedy", propensities=[])

    if is_random_policy_session(session_id):
        chosen = rng.sample(pool_ids, n)
        # Sequential sampling without replacement from a pool of size m:
        # slot i's marginal propensity is 1/(m - i). Exact, not approximated.
        propensities = [1.0 / (len(pool_ids) - i) for i in range(n)]
        return RecommendationSlate(item_ids=chosen, policy_id="random", propensities=propensities)

    exploit_slate = mmr_rerank(rank_by_cosine(taste_vector, candidates), candidates, n, diversity_lambda)

    slate: list[str] = []
    propensities: list[float] = []
    for i in range(n):
        exploit_pick = exploit_slate[i]
        remaining_pool_size = len(pool_ids) - i
        if rng.random() < epsilon:
            unchosen = [c for c in pool_ids if c not in slate]
            choice = rng.choice(unchosen)
        else:
            choice = exploit_pick
        # Mixture propensity of the ACTION taken, independent of which
        # branch produced it: P(choice) = epsilon * uniform + (1-epsilon)
        # * indicator(choice is the deterministic exploit pick).
        prop = epsilon * (1.0 / remaining_pool_size) + (1 - epsilon) * (1.0 if choice == exploit_pick else 0.0)
        slate.append(choice)
        propensities.append(prop)

    return RecommendationSlate(item_ids=slate, policy_id="epsilon_greedy", propensities=propensities)
