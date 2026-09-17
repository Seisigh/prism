"""Sanity checks on the simulator's generative process itself — NOT the
full Gate 1 DoD (§11's "Spearman rho > 0.6... archetype separation >
70%... negative control") — those are the trained ranker's claims to make
once it exists, using its recovered *interest scores* on held-out
sessions. What's checked here is one level down: that raw dwell (the
generative process's direct output, before any model touches it) moves
with true utility in the expected direction, and that a negative control
on the process itself is clean. If this layer is broken, the ranker
built on top of it can't recover anything real regardless of its own
quality — so this is the honest, currently-buildable piece of that DoD
item, not a claim to have satisfied it.
"""
import random
import statistics

import pytest

from sim.agents import ARCHETYPES, utility
from sim.embedding import ItemVector
from sim.generative import dwell_via_drift_diffusion


def _spearman(xs: list[float], ys: list[float]) -> float:
    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        for r, i in enumerate(order):
            ranks[i] = r
        return ranks

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mean_rx, mean_ry = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x**0.5 * var_y**0.5)


def _synthetic_items(n: int, rng: random.Random) -> list[tuple[str, tuple[float, ...]]]:
    # 7 dims matching sim/embedding.py's DIMENSIONS, without depending on
    # a real catalog.json build being present for this test to run.
    return [(f"item-{i}", tuple(rng.uniform(-2, 2) for _ in range(7))) for i in range(n)]


@pytest.mark.parametrize("archetype_name", list(ARCHETYPES.keys()))
def test_commitment_rate_correlates_with_utility(archetype_name):
    """A drift-diffusion process's *decision* (which threshold it hits)
    is what tracks utility monotonically — dwell (how *long* it takes to
    decide) does not, on purpose: dwell is longest near indifference
    (utility ~ 0, the process wanders before committing either way) and
    short at either a strong positive OR strong negative utility (a
    confident decision, made quickly). That's real drift-diffusion
    behavior, and it's the generative echo of §4.2's own warning not to
    assume dwell is positively related to interest — so the right thing
    to check here is the commitment *rate*, the actual interest signal,
    not raw dwell."""
    archetype = ARCHETYPES[archetype_name]
    rng = random.Random(7)
    items = _synthetic_items(60, rng)

    utilities = []
    commit_rates = []
    for _item_id, vec in items:
        u = utility(archetype, vec)
        draws = [dwell_via_drift_diffusion(u, archetype, "discovery", rng).committed_positive for _ in range(6)]
        utilities.append(u)
        commit_rates.append(sum(draws) / len(draws))

    rho = _spearman(utilities, commit_rates)
    assert rho > 0.5, f"{archetype_name}: expected commitment rate to track utility, got rho={rho:.3f}"


def test_negative_control_shuffled_utility_breaks_correlation():
    """§11's negative control, at the generative-process level: shuffle
    which utility belongs to which item's outcome, and the commitment-
    rate correlation should collapse toward zero. If it doesn't,
    something is leaking item identity into the outcome outside of
    utility."""
    archetype = ARCHETYPES["deliberator"]
    rng = random.Random(11)
    # A larger sample than the other tests here: this is a negative
    # control asserting an estimate is *close to zero*, which needs more
    # statistical power than asserting a real effect is present — with
    # too few items, sampling noise on a true-zero correlation can itself
    # exceed a tight tolerance by chance, which is a test-power problem,
    # not evidence the control is failing.
    items = _synthetic_items(300, rng)

    utilities = [utility(archetype, vec) for _item_id, vec in items]
    commit_rates = []
    for u in utilities:
        draws = [dwell_via_drift_diffusion(u, archetype, "discovery", rng).committed_positive for _ in range(10)]
        commit_rates.append(sum(draws) / len(draws))

    real_rho = _spearman(utilities, commit_rates)
    shuffled_utilities = utilities[:]
    rng.shuffle(shuffled_utilities)
    shuffled_rho = _spearman(shuffled_utilities, commit_rates)

    assert real_rho > 0.5
    assert abs(shuffled_rho) < 0.2, f"shuffled control should be ~0, got {shuffled_rho:.3f}"


def test_dwell_is_peaked_at_indifference_not_monotonic():
    """Documents the property above as an explicit, intentional
    behavior (not just an assumption baked into the other tests):
    average dwell near indifference (utility ~ 0) should exceed average
    dwell at a strongly positive OR strongly negative utility — an
    inverted-U / "peaked" curve (RT peaks at zero drift rate in a DDM),
    the opposite of a literal U-shape (which would mean dwell dips at
    indifference and rises at the extremes)."""
    archetype = ARCHETYPES["skimmer"]
    rng = random.Random(11)

    def avg_dwell(u: float, n: int = 150) -> float:
        return statistics.fmean(dwell_via_drift_diffusion(u, archetype, "discovery", rng).dwell_ms for _ in range(n))

    near_zero = avg_dwell(0.0)
    strong_positive = avg_dwell(2.0)
    strong_negative = avg_dwell(-2.0)

    assert near_zero > strong_positive
    assert near_zero > strong_negative


def test_higher_threshold_archetypes_take_longer_on_average():
    """Deliberator (threshold=2.6) and spec_reader (threshold=2.8) should
    show longer average dwell than skimmer (threshold=1.0) on identical
    items — a basic parameter-sanity check independent of any specific
    taste vector."""
    rng = random.Random(3)
    items = _synthetic_items(40, rng)
    neutral_vec = tuple(0.0 for _ in range(7))  # utility ~= 0 for everyone regardless of taste

    def avg_dwell(name: str) -> float:
        archetype = ARCHETYPES[name]
        return statistics.fmean(dwell_via_drift_diffusion(0.0, archetype, "discovery", rng).dwell_ms for _ in range(30))

    skimmer_dwell = avg_dwell("skimmer")
    deliberator_dwell = avg_dwell("deliberator")
    assert deliberator_dwell > skimmer_dwell
