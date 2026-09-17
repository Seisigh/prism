"""Five archetypes (§11), each with a known taste vector and a known
signal-weighting vector, parameterized *independently of the feature
set*. None of these parameters says "curvature proportional to conflict"
— that would make recovery tautological. Instead each archetype gets:

  - a taste_vector: weights over sim/embedding.py's 7 real catalog
    dimensions, used only to compute item utility.
  - motor/timing parameters (decision_rate, noise_sigma, threshold,
    reach_noise, reading_speed) that drive the *generative* process in
    generative.py — a drift-diffusion utility-accumulator, a
    gaze-then-reach motor model, and a scroll/reading model. Curvature,
    velocity and pause structure emerge from those physically-motivated
    processes; they are never assigned directly.
  - a signal_weighting_vector (the five families from §11: attention,
    motor_conflict, exploration, comparison, availability) — this is the
    *recovery target* for Gate 1's DoD ("a linear probe on recovered
    signal-weighting vectors classifies the five archetypes at > 70%"),
    kept separate from the generative parameters above so recovering it
    from simulated behavior is a real test, not a tautology.
"""
from __future__ import annotations

from dataclasses import dataclass

from sim.embedding import DIMENSIONS

SignalFamily = str  # "attention" | "motor_conflict" | "exploration" | "comparison" | "availability"
FAMILIES = ["attention", "motor_conflict", "exploration", "comparison", "availability"]


@dataclass(frozen=True)
class Archetype:
    name: str
    taste_vector: dict[str, float]  # DIMENSIONS -> weight
    signal_weighting_vector: dict[str, float]  # FAMILIES -> weight (recovery target)
    # Drift-diffusion params (generative.dwell_via_drift_diffusion)
    decision_rate: float  # how strongly utility drives evidence accumulation
    noise_sigma: float  # accumulation noise (independent of "motor_conflict" label above)
    threshold: float  # evidence needed to commit — higher = slower, more deliberate
    # Gaze-then-reach motor params (generative.reach_trajectory)
    reach_noise: float  # perpendicular path noise scale — higher = more curvature
    reach_duration_ms: float  # baseline time to complete a reach
    # Reading/scroll params (generative.reading_scroll)
    reading_speed: float  # scroll progression per unit time
    scroll_pause_prob: float  # chance of a reading pause per scroll step


def _taste(**weights: float) -> dict[str, float]:
    out = {d: 0.0 for d in DIMENSIONS}
    out.update(weights)
    return out


ARCHETYPES: dict[str, Archetype] = {
    "skimmer": Archetype(
        name="skimmer",
        taste_vector=_taste(rating=0.6, review_count_log=0.3),
        signal_weighting_vector={"attention": 0.15, "motor_conflict": 0.1, "exploration": 0.5, "comparison": 0.1, "availability": 0.15},
        decision_rate=1.8,
        noise_sigma=0.9,
        threshold=1.0,
        reach_noise=0.15,
        reach_duration_ms=350,
        reading_speed=1.6,
        scroll_pause_prob=0.08,
    ),
    "deliberator": Archetype(
        name="deliberator",
        taste_vector=_taste(rating=0.5, review_count_log=0.4, description_length=0.3, on_sale=0.2),
        signal_weighting_vector={"attention": 0.4, "motor_conflict": 0.15, "exploration": 0.1, "comparison": 0.25, "availability": 0.1},
        decision_rate=0.6,
        noise_sigma=0.5,
        threshold=2.6,
        reach_noise=0.08,
        reach_duration_ms=650,
        reading_speed=0.6,
        scroll_pause_prob=0.35,
    ),
    "price_hunter": Archetype(
        name="price_hunter",
        taste_vector=_taste(price_z=-0.9, on_sale=0.6),
        signal_weighting_vector={"attention": 0.2, "motor_conflict": 0.1, "exploration": 0.2, "comparison": 0.4, "availability": 0.1},
        decision_rate=1.1,
        noise_sigma=0.6,
        threshold=1.6,
        reach_noise=0.1,
        reach_duration_ms=450,
        reading_speed=1.1,
        scroll_pause_prob=0.15,
    ),
    "image_driven": Archetype(
        name="image_driven",
        taste_vector=_taste(gallery_size=0.8, brand_tier=0.3),
        signal_weighting_vector={"attention": 0.3, "motor_conflict": 0.35, "exploration": 0.15, "comparison": 0.05, "availability": 0.15},
        decision_rate=1.0,
        noise_sigma=0.7,
        threshold=1.4,
        reach_noise=0.22,
        reach_duration_ms=400,
        reading_speed=1.2,
        scroll_pause_prob=0.12,
    ),
    "spec_reader": Archetype(
        name="spec_reader",
        taste_vector=_taste(description_length=0.7, review_count_log=0.35, brand_tier=0.2),
        signal_weighting_vector={"attention": 0.45, "motor_conflict": 0.1, "exploration": 0.05, "comparison": 0.1, "availability": 0.3},
        decision_rate=0.5,
        noise_sigma=0.45,
        threshold=2.8,
        reach_noise=0.07,
        reach_duration_ms=700,
        reading_speed=0.5,
        scroll_pause_prob=0.4,
    ),
}


def utility(archetype: Archetype, item_vector: tuple[float, ...]) -> float:
    return sum(archetype.taste_vector[d] * v for d, v in zip(DIMENSIONS, item_vector))
