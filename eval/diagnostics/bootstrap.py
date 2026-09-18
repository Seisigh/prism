"""Bootstrap confidence intervals for the Gate 1 recovery metrics --
diagnostic tooling, not part of the trained pipeline. Written after
three recovery reruns were reported (and reacted to) as bare point
estimates with no uncertainty attached; the author's instruction was
"confidence intervals, retroactively and from now on."

**Unit of analysis matters and changes the standard error by an order of
magnitude (author's explicit framing) — stated here, not left implicit:**

- Item-*views* are not independent draws: every view in a session shares
  that session's archetype, mode mix and taste vector, so resampling
  views directly (ignoring which session they came from) understates
  the true sampling uncertainty and produces an artificially narrow CI.
- *Sessions* are the actual independent unit the simulator generates.
  The correct bootstrap resamples sessions with replacement, then pools
  (or re-averages) whatever session-level or view-level quantity is
  being estimated.

Two different rho estimators are computed for the same reason
(`eval/diagnostics/oracle_probes.py`'s oracle-(a) result is what exposed
this): `pooled_rho` (every held-out view from every session lumped into
one Spearman correlation) is NOT the metric the ranker is actually
trained to optimize -- LambdaRank is a *within-group* objective with no
mechanism to calibrate predicted-score scale *across* sessions, so
pooling views from many sessions conflates real within-session ranking
quality with an artifact of cross-session scale never being trained to
line up. `per_session_mean_rho` (one Spearman rho per session, then
averaged) matches what the model was actually optimized for and should
be treated as the primary number; `pooled_rho` is reported alongside it
only because it is what was reported in every run before this one, not
because it is the metric to judge the DoD bar against going forward.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

N_BOOT_DEFAULT = 2000


def pooled_rho(rows: list[dict]) -> float | None:
    pairs = [(r["utility"], r["pred"]) for r in rows if r.get("pred") is not None]
    if len(pairs) < 3:
        return None
    u, p = zip(*pairs)
    if len(set(u)) < 2 or len(set(p)) < 2:
        return None
    return float(spearmanr(u, p).correlation)


def per_session_rhos(rows: list[dict]) -> np.ndarray:
    """One Spearman rho per session_id, for sessions with enough
    variation to compute one -- the array `per_session_mean_rho` and its
    bootstrap CI are built from."""
    by_session: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        if r.get("pred") is None:
            continue
        by_session.setdefault(r["session_id"], []).append((r["utility"], r["pred"]))
    out = []
    for pairs in by_session.values():
        if len(pairs) < 3:
            continue
        u, p = zip(*pairs)
        if len(set(u)) < 2 or len(set(p)) < 2:
            continue
        out.append(spearmanr(u, p).correlation)
    return np.array(out)


def view_level_bootstrap_rho(rows: list[dict], n_boot: int = N_BOOT_DEFAULT, rng: np.random.Generator | None = None) -> np.ndarray:
    """Resamples views directly -- ignores session clustering, produces
    an artificially narrow CI. Kept for contrast with the session-level
    version below, never as the number to report alone."""
    rng = rng or np.random.default_rng()
    pairs = [(r["utility"], r["pred"]) for r in rows if r.get("pred") is not None]
    u = np.array([p[0] for p in pairs])
    p = np.array([p[1] for p in pairs])
    n = len(u)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        uu, pp = u[idx], p[idx]
        if len(set(uu.tolist())) < 2 or len(set(pp.tolist())) < 2:
            continue
        boots.append(spearmanr(uu, pp).correlation)
    return np.array(boots)


def session_level_bootstrap_rho(rows: list[dict], n_boot: int = N_BOOT_DEFAULT, rng: np.random.Generator | None = None) -> np.ndarray:
    """The correct cluster bootstrap for `pooled_rho`: resamples whole
    sessions with replacement, pools their views, recomputes the pooled
    rho each time."""
    rng = rng or np.random.default_rng()
    by_session: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        if r.get("pred") is None:
            continue
        by_session.setdefault(r["session_id"], []).append((r["utility"], r["pred"]))
    session_ids = list(by_session.keys())
    n = len(session_ids)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        pooled: list[tuple[float, float]] = []
        for i in idx:
            pooled.extend(by_session[session_ids[i]])
        if len(pooled) < 3:
            continue
        u, p = zip(*pooled)
        if len(set(u)) < 2 or len(set(p)) < 2:
            continue
        boots.append(spearmanr(u, p).correlation)
    return np.array(boots)


def bootstrap_mean(values: np.ndarray, n_boot: int = N_BOOT_DEFAULT, rng: np.random.Generator | None = None) -> np.ndarray:
    """Generic bootstrap over an already-computed array of per-unit
    values (per-session rhos, or per-session probe-correctness
    booleans) -- resamples units with replacement, recomputes the mean."""
    rng = rng or np.random.default_rng()
    n = len(values)
    if n == 0:
        return np.array([])
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        boots.append(values[idx].mean())
    return np.array(boots)


def ci95(boots: np.ndarray, point: float | None = None) -> tuple[float | None, float | None, float | None]:
    """(lower, upper, point). `point` is the actual point estimate on
    the real (non-bootstrapped) sample when available -- the bootstrap
    mean is a reasonable fallback but is not the same quantity."""
    if len(boots) == 0:
        return (None, None, point)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return (float(lo), float(hi), point if point is not None else float(np.mean(boots)))
