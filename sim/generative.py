"""The declared generative process (§11): a drift-diffusion utility
accumulator decides *how long* an agent looks at something, a
gaze-then-reach motor model with signal-dependent noise decides *how the
cursor gets there*, and a reading model decides how scroll progresses.
Trajectory curvature, peak velocity and pause structure are never set
directly — they fall out of these physically-motivated processes, which
is the whole point: it makes "does curvature carry information beyond
dwell" (the ablation's central question) a real empirical question
instead of one this module quietly answers by construction.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from sim.agents import Archetype

DT_MS = 50.0
MAX_DWELL_MS = 20_000.0
POINTER_HZ = 60.0
POINTER_STEP_MS = 1000.0 / POINTER_HZ


@dataclass(frozen=True)
class DriftDiffusionResult:
    dwell_ms: float
    committed_positive: bool  # evidence crossed +threshold (interest) vs -threshold/timeout


def dwell_via_drift_diffusion(utility: float, archetype: Archetype, rng: random.Random) -> DriftDiffusionResult:
    """A random walk in evidence-space: drift proportional to utility,
    archetype-specific noise, stopping at +/-threshold or a timeout. This
    is the source of every dwell duration the simulator produces —
    nothing downstream hand-sets a dwell number."""
    evidence = 0.0
    t = 0.0
    dt_s = DT_MS / 1000.0
    while t < MAX_DWELL_MS:
        evidence += archetype.decision_rate * utility * dt_s + rng.gauss(0, archetype.noise_sigma) * math.sqrt(dt_s)
        t += DT_MS
        if evidence >= archetype.threshold:
            return DriftDiffusionResult(dwell_ms=t, committed_positive=True)
        if evidence <= -archetype.threshold:
            return DriftDiffusionResult(dwell_ms=t, committed_positive=False)
    return DriftDiffusionResult(dwell_ms=MAX_DWELL_MS, committed_positive=evidence > 0)


@dataclass(frozen=True)
class PointerSample:
    t: float
    x: float
    y: float


def reach_trajectory(
    start: tuple[float, float],
    target: tuple[float, float],
    archetype: Archetype,
    rng: random.Random,
    t0: float = 0.0,
) -> list[PointerSample]:
    """Gaze-then-reach: a minimum-jerk-shaped path from start to target,
    perturbed by smoothed (not white) perpendicular noise scaled by the
    archetype's `reach_noise` — smoothing (an AR(1) process on the noise
    term) is what makes the resulting path *curve* rather than jitter,
    matching how real reaching movements deviate from a straight line in
    smooth arcs, not high-frequency noise."""
    x0, y0 = start
    x1, y1 = target
    duration = archetype.reach_duration_ms
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    perp = (-dy / length, dx / length)

    samples: list[PointerSample] = []
    smoothed_noise = 0.0
    n_steps = max(2, int(duration / POINTER_STEP_MS))
    for i in range(n_steps + 1):
        frac = i / n_steps
        # Minimum-jerk profile: 10s^3 - 15s^4 + 6s^5
        s = 10 * frac**3 - 15 * frac**4 + 6 * frac**5
        raw_noise = rng.gauss(0, archetype.reach_noise * length * 0.15)
        smoothed_noise = 0.7 * smoothed_noise + 0.3 * raw_noise
        # Noise peaks mid-reach and vanishes at the endpoints, since a
        # real reach corrects onto the target rather than ending wide.
        envelope = math.sin(math.pi * frac)
        offset = smoothed_noise * envelope
        x = x0 + dx * s + perp[0] * offset
        y = y0 + dy * s + perp[1] * offset
        samples.append(PointerSample(t=t0 + i * POINTER_STEP_MS, x=x, y=y))
    return samples


def fixation_jitter(
    center: tuple[float, float],
    duration_ms: float,
    archetype: Archetype,
    rng: random.Random,
    t0: float = 0.0,
) -> list[PointerSample]:
    """Small-amplitude cursor drift while "reading" a fixed target — a
    proxy for the fact that a resting cursor never sits perfectly still."""
    cx, cy = center
    n_steps = max(1, int(duration_ms / POINTER_STEP_MS))
    samples = []
    x, y = cx, cy
    for i in range(n_steps):
        x += rng.gauss(0, 1.5)
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
    duration_ms: float,
    archetype: Archetype,
    rng: random.Random,
    t0: float = 0.0,
    start_ratio: float = 0.0,
) -> list[ScrollSample]:
    """A reading-driven scroll model: progresses downward at
    `reading_speed`, with `scroll_pause_prob` chance per step of pausing
    (a fixation), and a small chance of a brief upward re-read — this is
    where scroll reversals come from, not a hand-set reversal count."""
    step_ms = 200.0
    n_steps = max(1, int(duration_ms / step_ms))
    ratio = start_ratio
    samples = [ScrollSample(t=t0, y_ratio=ratio)]
    for i in range(1, n_steps + 1):
        t = t0 + i * step_ms
        if rng.random() < archetype.scroll_pause_prob:
            samples.append(ScrollSample(t=t, y_ratio=ratio))
            continue
        step = archetype.reading_speed * 0.03 * rng.uniform(0.6, 1.4)
        if rng.random() < 0.12:
            step = -step * rng.uniform(0.3, 0.8)  # a re-read reversal
        ratio = min(1.0, max(0.0, ratio + step))
        samples.append(ScrollSample(t=t, y_ratio=ratio))
    return samples
