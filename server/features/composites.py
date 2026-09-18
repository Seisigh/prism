"""Five family composites (BUILD_BRIEF.md §11): attention, motor_conflict,
exploration, comparison, availability. "Raw signals are stored for
ablation; the deployed model uses composites."

The signal -> family assignment below is a **declared measurement
model**, written down before any ranker was trained against it, for the
same reason sim/mode_priors.py's DDM priors are declared up front: a
family-composite mapping chosen or adjusted *after* seeing recovery
results would make the Gate 1 DoD's "archetype separation" and "Spearman
rho" numbers partly an artifact of curve-fitting the measurement model
to the answer, not a real recovery test. If a family's assignment looks
wrong once real numbers exist, that is a reason to flag it, not to
silently reassign a signal to a different family until a metric improves.

Reasoning per family:

- **attention**: sustained looking at the item itself -- dwell, viewport
  time, hover, and focused idle time on the target.
- **motor_conflict**: hesitation and correction in the pointer's motion
  -- curvature, direction reversals, peak velocity, abrupt acceleration
  changes, and pause count. A confident, low-conflict interaction is a
  straight fast reach; a conflicted one wanders, slows, and corrects.
- **exploration**: breadth of looking, on the page and across the
  session -- scroll depth, scroll reversals, and how many categories the
  visitor has ranged across so far. Query specificity enters here too,
  sign-flipped: a highly specific query signals a *narrower*, less
  exploratory session (directed_search's whole premise), so specificity
  is subtracted rather than added.
- **comparison**: behavior that indicates weighing this item against
  alternatives -- revisits of this same item, and how many other
  near-substitute-set items were viewed nearby in time.
- **directional** (`server/features/signals_directional.py`, added after
  Gate 1's ranker recovery stalled -- see STATE.md's "Eighteen signals
  that measure magnitude, none that measure direction" section): the
  only family whose constituents can distinguish *which way* a
  trajectory leaned, not just how confidently or how erratically it
  moved. Deliberately its own family rather than folded into
  motor_conflict: averaging a directional signal into a family of
  magnitude-only signals would launder away the exact distinction this
  family exists to keep visible, and a future ablation over families
  needs to be able to attribute recovery to direction specifically
  rather than to "motor behavior" generally.
- **availability**: not a behavioral signal at all -- the fraction of
  the other five families' constituent raw signals that were actually
  computable (non-None) for this view. A structural meta-signal per
  §9.2's "carry availability as its own indicator," not a stand-in value
  for missing data.

**Guard, stated explicitly because it is the exact place direction died
the first time:** nothing in this module may take `abs()` or any other
magnitude of `early_direction_bias` or `direction_lock_in_speed`
before averaging it into the `directional` composite. A signed signal
averaged together with unsigned ones is fine (that's what happens below);
discarding the sign is not.
`tests/features/test_composites.py::test_composites_module_never_takes_an_absolute_value`
enforces this on the module's own source, the same way
`tests/sim/test_session.py::test_session_never_assigns_mode_directly`
enforces its own rule by inspecting source rather than trusting a
docstring.

Composite values are the mean of their *z-scored* constituent signals
(z-scored within (session, mode, surface) via normalize.z_score) that
are available; a composite is None only when every one of its
constituents is None for this view.
"""
from __future__ import annotations

from dataclasses import dataclass

FAMILIES = ["attention", "motor_conflict", "exploration", "comparison", "directional", "availability"]

# name -> (family, sign). Sign -1 means "subtract this signal's z-score"
# rather than add it -- used only for query_specificity's inverse
# relationship to exploration, documented above.
SIGNAL_FAMILY_MAP: dict[str, tuple[str, float]] = {
    "item_dwell": ("attention", 1.0),
    "viewport_time": ("attention", 1.0),
    "hover_dwell_on_target": ("attention", 1.0),
    "focused_idle": ("attention", 1.0),
    "peak_pointer_velocity_on_approach": ("motor_conflict", 1.0),
    "trajectory_curvature_auc": ("motor_conflict", 1.0),
    "trajectory_x_flips": ("motor_conflict", 1.0),
    "acceleration_profile": ("motor_conflict", 1.0),
    "pause_count": ("motor_conflict", 1.0),
    "max_scroll_depth": ("exploration", 1.0),
    "scroll_reversals": ("exploration", 1.0),
    "category_breadth": ("exploration", 1.0),
    "query_specificity": ("exploration", -1.0),
    "revisit_count": ("comparison", 1.0),
    "near_substitute_coview_count": ("comparison", 1.0),
    "early_direction_bias": ("directional", 1.0),
    "direction_lock_in_speed": ("directional", 1.0),
}

# Signals with no family (fed to the ranker raw, or consumed elsewhere):
# none at present -- every registered Gate 0 + Gate 1 signal maps to a
# family above.


@dataclass(frozen=True)
class CompositeResult:
    value: float | None
    availability: float  # fraction of this family's constituents that were non-None, in [0, 1]


def compute_composites(normalized_signals: dict[str, float | None]) -> dict[str, CompositeResult]:
    """`normalized_signals` maps raw signal name -> its within-(session,
    mode, surface) z-score (or None if that signal was itself None or
    z-score-uncomputable, per normalize.z_score). Returns one
    CompositeResult per family in FAMILIES, `availability` always
    computed over the behavioral four; the `availability` *family*
    itself is handled by `availability_composite` below since it isn't a
    z-scored behavioral signal.
    """
    by_family: dict[str, list[float]] = {f: [] for f in FAMILIES if f != "availability"}
    counts: dict[str, int] = {f: 0 for f in by_family}

    for name, (family, sign) in SIGNAL_FAMILY_MAP.items():
        if family == "availability":
            continue
        z = normalized_signals.get(name)
        counts[family] += 1
        if z is not None:
            by_family[family].append(sign * z)

    out: dict[str, CompositeResult] = {}
    for family in by_family:
        n_constituents = counts[family]
        n_available = len(by_family[family])
        availability = n_available / n_constituents if n_constituents else 0.0
        value = sum(by_family[family]) / n_available if n_available else None
        out[family] = CompositeResult(value=value, availability=availability)

    out["availability"] = availability_composite(normalized_signals)
    return out


def availability_composite(normalized_signals: dict[str, float | None]) -> CompositeResult:
    """Fraction of ALL registered signals (across every behavioral
    family) that were non-None for this view -- a single number
    summarizing how much signal this view even offered, independent of
    what the signal said. Never None itself: even zero available signals
    is a real, known fact (0.0), not a missing one."""
    behavioral = [name for name, (family, _s) in SIGNAL_FAMILY_MAP.items() if family != "availability"]
    if not behavioral:
        return CompositeResult(value=0.0, availability=1.0)
    n_available = sum(1 for name in behavioral if normalized_signals.get(name) is not None)
    rate = n_available / len(behavioral)
    return CompositeResult(value=rate, availability=1.0)
