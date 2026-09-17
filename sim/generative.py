"""The declared generative process (§11): a drift-diffusion utility
accumulator decides *how long* an agent looks at something and *which
way* the decision goes; a gaze-then-reach motor model couples to that
same accumulator's evolving evidence to decide how the cursor gets there;
a reading model couples to it too, to decide how scroll progresses.
Trajectory curvature, peak velocity, pause structure and scroll pacing
are never set directly — they fall out of coupling to the DDM's own
evidence path, never from utility, the decision, or any label.

**The coupling rule, stated precisely (author's ruling):**

- Coupling to the **evidence path** (the DDM's running accumulator state,
  at or before the current instant) is mechanism, and is required. This
  is the foundational claim of mouse-tracking as a method: the hand
  begins moving while evidence is still accumulating, so partial and
  sometimes-reversing evidence leaks into motor output before the
  decision resolves. Leontyev & Yamauchi (2021) — in BUILD_BRIEF.md's
  §16 references — map trajectory features onto DDM parameters in real
  people; a generator whose trajectories are independent of its own DDM
  asserts the opposite of that finding.
- Coupling to the **outcome, the label, or the true utility** is leakage,
  and is forbidden. `reach_trajectory`, `fixation_jitter` and
  `reading_scroll` below take `(archetype, accumulator_path, ...)` and
  nothing else decision-shaped — no `utility`, no `committed_positive`,
  no label. `tests/sim/test_generative.py`'s
  `test_motor_functions_never_take_a_forbidden_parameter` enforces this
  on the actual function signatures, the same way the feature-window
  leakage rule is enforced mechanically rather than by convention.
- **Causality**: output at time t depends only on `accumulator_path`
  entries with timestamp <= t — never a later sample, and never the
  path's own final length used to shape earlier output (that would leak
  "how long this took" into early motion, which is itself a fact about
  how the process resolves). `test_reach_and_scroll_are_causal_in_the_accumulator_path`
  enforces this by truncating the path and checking outputs at-or-before
  the truncation point are byte-identical to the untruncated run.

The evidence path's *value* at time t is not "the outcome" even at the
final sample — it is the same running mechanism the DDM always was; the
boolean `committed_positive` is a threshold read taken *of* that
mechanism, not a separate fact smuggled in from elsewhere. Reading the
path directly (including its last sample) is coupling to evidence, not
to a label — this is the whole point of Leontyev & Yamauchi's own
method.

Direction has to come from somewhere mechanical, so the accept and
reject actions live in different places on screen, matching a real
storefront: accept pulls the cursor toward the item's own action region
(zoom, specs, add to cart); reject pulls it toward the next item /
the forward scroll direction. The instantaneous evidence sign blends
which of the two the cursor is currently heading toward, producing
genuine curvature and reversals when evidence wavers before resolving —
mechanistically caused, never hand-set to match the eventual label.

Mode (§4) still only modulates the DDM's drift rate and boundary
separation (and, for `refind`, non-decision time) via
`sim/mode_priors.py` — see that module's docstring. Mode itself never
reaches the motor functions; only the accumulator path it shapes does.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from sim.agents import Archetype
from sim.mode_priors import MODE_PRIORS

DT_MS = 50.0
MAX_DWELL_MS = 20_000.0
POINTER_HZ = 60.0
POINTER_STEP_MS = 1000.0 / POINTER_HZ
SCROLL_STEP_MS = 200.0


@dataclass(frozen=True)
class AccumulatorSample:
    """One point on the DDM's own evidence trajectory. `t` is elapsed
    diffusion time (ms since the view's evidence accumulation began, NOT
    including the flat non-decision-time buffer added after
    termination)."""

    t: float
    evidence: float


@dataclass(frozen=True)
class DriftDiffusionResult:
    dwell_ms: float
    committed_positive: bool  # evidence crossed +threshold (interest) vs -threshold/timeout
    accumulator_path: tuple[AccumulatorSample, ...]  # the mechanism reach/fixation/scroll couple to


def dwell_via_drift_diffusion(utility: float, archetype: Archetype, mode: str, rng: random.Random) -> DriftDiffusionResult:
    """A random walk in evidence-space: drift proportional to utility
    (scaled by the archetype's baseline decision_rate and the mode's
    drift_multiplier), archetype-specific noise (never mode-scaled — the
    author's instruction is explicit that mode shifts drift and boundary
    only), stopping at +/-threshold (scaled by the mode's
    boundary_multiplier) or a timeout, plus the mode's non-decision time
    added flat at the end. This is the source of every dwell duration the
    simulator produces — nothing downstream hand-sets a dwell number.
    The full evidence trajectory is recorded and returned: it is the
    *only* channel through which the eventual decision direction may
    reach the motor/reading models (see module docstring)."""
    prior = MODE_PRIORS[mode]
    if rng.random() < prior.bimodal_decisive_prob:
        drift_scale = prior.drift_multiplier
    else:
        drift_scale = prior.bimodal_ambiguous_drift_scale
    effective_decision_rate = archetype.decision_rate * drift_scale
    effective_threshold = archetype.threshold * prior.boundary_multiplier

    evidence = 0.0
    t = 0.0
    dt_s = DT_MS / 1000.0
    path = [AccumulatorSample(t=0.0, evidence=0.0)]
    while t < MAX_DWELL_MS:
        evidence += effective_decision_rate * utility * dt_s + rng.gauss(0, archetype.noise_sigma) * math.sqrt(dt_s)
        t += DT_MS
        path.append(AccumulatorSample(t=t, evidence=evidence))
        if evidence >= effective_threshold:
            return DriftDiffusionResult(dwell_ms=prior.non_decision_time_ms + t, committed_positive=True, accumulator_path=tuple(path))
        if evidence <= -effective_threshold:
            return DriftDiffusionResult(dwell_ms=prior.non_decision_time_ms + t, committed_positive=False, accumulator_path=tuple(path))
    return DriftDiffusionResult(
        dwell_ms=prior.non_decision_time_ms + MAX_DWELL_MS, committed_positive=evidence > 0, accumulator_path=tuple(path)
    )


def _evidence_at_or_before(accumulator_path: tuple[AccumulatorSample, ...], t: float) -> float:
    """Zero-order hold on the last accumulator sample at or before `t` —
    never interpolates toward a later sample, so this is safe to call
    from a live, still-running trajectory without peeking ahead."""
    value = 0.0
    for sample in accumulator_path:
        if sample.t > t:
            break
        value = sample.evidence
    return value


def _pull(evidence: float, archetype: Archetype) -> float:
    """Evidence normalized against the archetype's own threshold scale
    and squashed to [-1, 1] via tanh — how strongly, and toward which
    side, the momentary evidence currently leans."""
    if archetype.threshold == 0:
        return 0.0
    return math.tanh(evidence / archetype.threshold)


@dataclass(frozen=True)
class PointerSample:
    t: float
    x: float
    y: float


def reach_trajectory(
    archetype: Archetype,
    accumulator_path: tuple[AccumulatorSample, ...],
    start: tuple[float, float],
    accept_pos: tuple[float, float],
    reject_pos: tuple[float, float],
    rng: random.Random,
    t0: float = 0.0,
) -> list[PointerSample]:
    """The cursor continuously pursues a target that is itself a blend of
    `accept_pos` and `reject_pos`, weighted by the *momentary* evidence
    pull (causal: only ever reads `accumulator_path` up to the current
    tick). Confident, low-conflict evidence produces a fast, nearly
    straight path toward the eventual target; evidence that wavers or
    reverses before resolving produces genuine curvature and
    direction-flips, mechanistically, the same way a real hand
    half-commits and corrects (Leontyev & Yamauchi 2021) — never because
    this function was told which way the decision went.

    `archetype.reach_noise` still scales perpendicular path noise
    (smoothed via the same AR(1) process as before) and
    `archetype.reach_duration_ms` still sets how quickly the cursor
    closes the distance to its instantaneous target — both archetype
    properties, independent of this item's outcome.
    """
    total_span = accumulator_path[-1].t if accumulator_path else 0.0
    n_steps = max(2, int(total_span / POINTER_STEP_MS))
    approach_rate = min(0.5, POINTER_STEP_MS / max(1.0, archetype.reach_duration_ms))

    x, y = start
    smoothed_noise = 0.0
    samples: list[PointerSample] = []
    for i in range(n_steps + 1):
        local_t = i * POINTER_STEP_MS
        evidence = _evidence_at_or_before(accumulator_path, local_t)
        weight_accept = (_pull(evidence, archetype) + 1.0) / 2.0
        target_x = weight_accept * accept_pos[0] + (1.0 - weight_accept) * reject_pos[0]
        target_y = weight_accept * accept_pos[1] + (1.0 - weight_accept) * reject_pos[1]

        dx, dy = target_x - x, target_y - y
        length = math.hypot(dx, dy) or 1.0
        perp = (-dy / length, dx / length)
        raw_noise = rng.gauss(0, archetype.reach_noise * length * 0.15)
        smoothed_noise = 0.7 * smoothed_noise + 0.3 * raw_noise

        x += dx * approach_rate + perp[0] * smoothed_noise * approach_rate
        y += dy * approach_rate + perp[1] * smoothed_noise * approach_rate
        samples.append(PointerSample(t=t0 + local_t, x=x, y=y))
    return samples


def fixation_jitter(
    archetype: Archetype,
    accumulator_path: tuple[AccumulatorSample, ...],
    center: tuple[float, float],
    duration_ms: float,
    rng: random.Random,
    t0: float = 0.0,
) -> list[PointerSample]:
    """Small-amplitude cursor drift during the flat non-decision-time
    tail after the accumulator has already terminated — a resting cursor
    never sits perfectly still. The resting point carries a small,
    steady lean along the direction the evidence path resolved toward
    (its own last sample — still the accumulator's mechanism, not a
    separately-passed outcome), matching the real finding that settle
    motion continues to track the decision state even as the process
    concludes."""
    cx, cy = center
    final_evidence = accumulator_path[-1].evidence if accumulator_path else 0.0
    lean = _pull(final_evidence, archetype) * 3.0  # a few px, deliberately small next to the tremor
    n_steps = max(1, int(duration_ms / POINTER_STEP_MS))
    samples = []
    x, y = cx, cy
    for i in range(n_steps):
        x += rng.gauss(0, 1.5) + lean * 0.05
        y += rng.gauss(0, 1.5)
        # Gentle pull back toward center so it drifts, not walks away.
        x += (cx - x) * 0.05
        y += (cy - y) * 0.05
        samples.append(PointerSample(t=t0 + i * POINTER_STEP_MS, x=x, y=y))
    return samples


@dataclass(frozen=True)
class ScrollSample:
    t: float
    y_ratio: float


def reading_scroll(
    archetype: Archetype,
    accumulator_path: tuple[AccumulatorSample, ...],
    rng: random.Random,
    t0: float = 0.0,
    start_ratio: float = 0.0,
) -> list[ScrollSample]:
    """A reading-driven scroll model: progresses downward at
    `reading_speed`, with `scroll_pause_prob` chance per step of pausing
    (a fixation) and a small chance of a brief upward re-read — this is
    where scroll reversals come from, not a hand-set reversal count.
    Evidence currently leaning toward accept nudges pacing toward
    lingering (higher pause probability, slower forward progress, as if
    reading specs more closely); evidence leaning toward reject nudges
    pacing toward moving on (lower pause probability, faster forward
    progress toward the next item) — read causally off `accumulator_path`
    at each step, never off the eventual outcome."""
    total_span = accumulator_path[-1].t if accumulator_path else 0.0
    n_steps = max(1, int(total_span / SCROLL_STEP_MS))
    ratio = start_ratio
    samples = [ScrollSample(t=t0, y_ratio=ratio)]
    for i in range(1, n_steps + 1):
        local_t = i * SCROLL_STEP_MS
        evidence = _evidence_at_or_before(accumulator_path, local_t)
        pull = _pull(evidence, archetype)

        pause_prob = min(0.95, max(0.0, archetype.scroll_pause_prob * (1.0 + 0.5 * pull)))
        speed_scale = max(0.2, 1.0 - 0.4 * pull)

        t = t0 + local_t
        if rng.random() < pause_prob:
            samples.append(ScrollSample(t=t, y_ratio=ratio))
            continue
        step = archetype.reading_speed * speed_scale * 0.03 * rng.uniform(0.6, 1.4)
        if rng.random() < 0.12:
            step = -step * rng.uniform(0.3, 0.8)  # a re-read reversal
        ratio = min(1.0, max(0.0, ratio + step))
        samples.append(ScrollSample(t=t, y_ratio=ratio))
    return samples
