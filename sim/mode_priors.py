"""Per-mode DDM priors — an explicit, stated modeling hypothesis about
shopper behavior (author-specified), not a tuning knob. See STATE.md's
"Per-mode DDM priors" section for the full reasoning behind each number.

**These must not be adjusted to make a downstream metric look better.**
If a result looks wrong once the ranker exists, that is a signal to stop
and raise it with the author, not to retune these values until the
metric improves — treating a stated hypothesis as a free parameter would
silently convert a falsifiable claim about shopper behavior into curve
fitting.

Mode modulates exactly three things: drift rate, boundary separation,
and (for refind only) non-decision time. It never touches dwell,
curvature, or any other feature directly — mode's only reach into
`sim/generative.py` is shaping the DDM's evidence path via the three
parameters below; `reach_trajectory`, `fixation_jitter` and
`reading_scroll` never receive `mode` itself, only the `archetype` and
the resulting `accumulator_path` (see that module's docstring for the
evidence-path coupling rule and why it isn't the same thing as touching
a feature directly). Touching a feature directly would reintroduce the
exact circularity §11's "parameterize the agent independently of the
feature set" rule exists to prevent (see sim/agents.py's docstring).
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_NON_DECISION_TIME_MS = 250.0


@dataclass(frozen=True)
class ModePrior:
    drift_multiplier: float
    boundary_multiplier: float
    non_decision_time_ms: float = DEFAULT_NON_DECISION_TIME_MS
    # Bimodal drift regime (directed_search only, see below): with
    # probability `bimodal_decisive_prob` the agent is decisive (drift
    # scaled by `drift_multiplier`); otherwise drift is scaled toward
    # near-zero by `bimodal_ambiguous_drift_scale`, independent of the
    # item's own utility — a perceptual/matching ambiguity ("is this
    # really the thing I'm looking for?"), not a statement that the item
    # itself is mediocre.
    bimodal_decisive_prob: float = 1.0
    bimodal_ambiguous_drift_scale: float = 1.0


MODE_PRIORS: dict[str, ModePrior] = {
    # High |drift| on average — checking a known target against a
    # candidate is verification, not preference formation, so evidence
    # accumulates fast when the match is genuine. Lower boundary: less
    # accumulated evidence is needed to act on a check than to form a
    # preference from scratch. Bimodal: mostly decisive, but a real
    # 25% tail where drift collapses toward zero regardless of the
    # item's underlying utility — the close-but-wrong item that *looks*
    # plausible enough to cause hesitation. That tail is the mechanism
    # behind §4.2's "failure to find": long dwell in directed_search
    # comes from this ambiguous regime, not from genuine interest, which
    # is exactly why dwell means something different here than in
    # discovery.
    "directed_search": ModePrior(
        drift_multiplier=1.8,
        boundary_multiplier=0.7,
        bimodal_decisive_prob=0.75,
        bimodal_ambiguous_drift_scale=0.12,
    ),
    # Between directed_search and discovery on both axes: the agent has
    # a category-level goal (some preference structure to check against)
    # but no single verified target, so neither the fast-verification
    # dynamics of directed_search nor the from-scratch construction of
    # discovery fully apply.
    "broad_search": ModePrior(drift_multiplier=1.2, boundary_multiplier=0.85),
    # Lower |drift| overall — there is no target to verify against, so
    # utility has to be *constructed* from the item's attributes as
    # they're encountered, which is a noisier, slower-accumulating
    # process than verification. Higher boundary: more evidence is
    # required before committing either way, since there's no prior
    # target-match signal to lean on.
    "discovery": ModePrior(drift_multiplier=0.7, boundary_multiplier=1.3),
    # Drift concentrated near zero *by construction*: near-substitute
    # items are close in utility to begin with (they're deliberately
    # controlled to vary one attribute at a time — see catalog/core_sets.py),
    # and comparison mode's own drift_multiplier suppresses it further,
    # modeling the genuine difficulty of choosing between close
    # alternatives. Highest boundary of any mode: the longest dwell,
    # because resolving a close call takes the most accumulated evidence.
    "comparison": ModePrior(drift_multiplier=0.5, boundary_multiplier=1.4),
    # High |drift|, low boundary, AND reduced non-decision time: the
    # evaluation largely already happened on the first view, so a refind
    # is mostly re-confirming a conclusion rather than reaching a new
    # one — fast on every axis, including the encoding/motor overhead
    # that's constant across the other modes.
    "refind": ModePrior(
        drift_multiplier=1.6,
        boundary_multiplier=0.6,
        non_decision_time_ms=80.0,
    ),
}
