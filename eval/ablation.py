"""The ablation harness (BUILD_BRIEF.md §12): "For each non-excluded
signal and each family, retrain and remeasure recovery with it removed.
Output a ranked contribution table." Per the author's framing, this is
the most interesting artifact in the repository — it is what actually
answers "what does trajectory curvature buy you," "what does the
directional pair buy you," under a fully declared generative model, with
no human participants required.

**Deliberately a single pooled model** (no per-mode split), the same
choice `eval/gate1_dod.py`'s ceiling probes make and for the same
reason: an ablation is trying to isolate the marginal contribution of
one signal or family, and a per-mode split multiplies the number of
models trained by five for a question that doesn't need per-mode
calibration to answer. This is a deliberate divergence from the
*deployed* ranker (which is per-mode, per §11), not an oversight —
stated once here rather than re-justified at every call site.

**Paired bootstrap, not two independent CIs.** Removing a signal and
retraining on the *same* train/holdout split produces per-session rho
arrays that are naturally paired (session i's rho with vs. without the
signal). The contribution's confidence interval is bootstrapped on the
*paired difference* (baseline rho - ablated rho, per session, resampled
together), which is tighter and more honest than treating the two as
independent when they share every other source of variance.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from lightgbm import LGBMRanker
from scipy.stats import spearmanr

from eval.corpus import CorpusSession, build_corpus
from eval.ranker import RELEVANCE_AMBIGUOUS, RELEVANCE_COMMITTED, RELEVANCE_FAST_SKIP, SIGNAL_NAMES
from server.features.composites import FAMILIES, SIGNAL_FAMILY_MAP
from sim.embedding import build_item_vectors

N_BOOT = 2000


def _relevance(row) -> int:
    if row.committed:
        return RELEVANCE_COMMITTED
    if row.is_fast_skip:
        return RELEVANCE_FAST_SKIP
    return RELEVANCE_AMBIGUOUS


def _feature_row(row, excluded_names: frozenset[str]) -> list[float]:
    return [row.signals.get(name) if (row.signals.get(name) is not None and name not in excluded_names) else np.nan for name in SIGNAL_NAMES]


def _train_and_predict(train: list[CorpusSession], holdout_rows, excluded_names: frozenset[str]):
    X, y, groups = [], [], []
    for cs in train:
        rows = cs.rows
        if len(rows) < 2:
            continue
        for row in rows:
            X.append(_feature_row(row, excluded_names))
            y.append(_relevance(row))
        groups.append(len(rows))
    model = LGBMRanker(objective="lambdarank", n_estimators=100, num_leaves=15, min_child_samples=5, learning_rate=0.1, verbosity=-1)
    model.fit(np.array(X), np.array(y), group=groups)
    X_holdout = np.array([_feature_row(row, excluded_names) for row in holdout_rows])
    return model.predict(X_holdout)


def _per_session_rhos(holdout_rows, preds) -> dict[str, float]:
    """session_id -> rho, for sessions with enough variation."""
    by_session = defaultdict(list)
    for row, p in zip(holdout_rows, preds):
        by_session[row.session_id].append((row.utility, p))
    out = {}
    for sid, pairs in by_session.items():
        if len(pairs) < 3:
            continue
        u, p = zip(*pairs)
        if len(set(u)) < 2 or len(set(p)) < 2:
            continue
        out[sid] = spearmanr(u, p).correlation
    return out


def _paired_delta_ci(baseline: dict[str, float], ablated: dict[str, float], rng: np.random.Generator) -> tuple[float, float, float]:
    """(mean_delta, ci_lo, ci_hi) for baseline - ablated, paired by
    session_id, bootstrapped over the shared session set."""
    shared = sorted(set(baseline) & set(ablated))
    if not shared:
        return (float("nan"), float("nan"), float("nan"))
    deltas = np.array([baseline[sid] - ablated[sid] for sid in shared])
    mean_delta = float(deltas.mean())
    n = len(deltas)
    boots = np.array([deltas[rng.integers(0, n, n)].mean() for _ in range(N_BOOT)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return (mean_delta, float(lo), float(hi))


def run_ablation(sessions_per_condition: int = 25, seed_train: int = 0, seed_holdout: int = 1) -> dict:
    rng = np.random.default_rng(0)
    item_vectors = build_item_vectors()
    train = build_corpus(item_vectors, sessions_per_condition, seed=seed_train, relabel_world=False)
    holdout = build_corpus(item_vectors, sessions_per_condition, seed=seed_holdout, relabel_world=False)
    holdout_rows = [row for cs in holdout for row in cs.rows]

    baseline_preds = _train_and_predict(train, holdout_rows, frozenset())
    baseline_rhos = _per_session_rhos(holdout_rows, baseline_preds)
    baseline_mean = float(np.mean(list(baseline_rhos.values())))

    signal_contributions = {}
    for name in SIGNAL_NAMES:
        preds = _train_and_predict(train, holdout_rows, frozenset({name}))
        rhos = _per_session_rhos(holdout_rows, preds)
        mean_delta, lo, hi = _paired_delta_ci(baseline_rhos, rhos, rng)
        signal_contributions[name] = {
            "family": SIGNAL_FAMILY_MAP.get(name, (None, None))[0],
            "mean_contribution": mean_delta,
            "ci": (lo, hi),
            "ablated_mean_rho": float(np.mean(list(rhos.values()))) if rhos else None,
        }

    family_contributions = {}
    for family in FAMILIES:
        if family == "availability":
            continue  # not a behavioral signal family -- see composites.py
        members = frozenset(name for name, (f, _s) in SIGNAL_FAMILY_MAP.items() if f == family)
        preds = _train_and_predict(train, holdout_rows, members)
        rhos = _per_session_rhos(holdout_rows, preds)
        mean_delta, lo, hi = _paired_delta_ci(baseline_rhos, rhos, rng)
        family_contributions[family] = {
            "members": sorted(members),
            "mean_contribution": mean_delta,
            "ci": (lo, hi),
            "ablated_mean_rho": float(np.mean(list(rhos.values()))) if rhos else None,
        }

    return {
        "baseline_mean_rho": baseline_mean,
        "n_train_sessions": len(train),
        "n_holdout_sessions": len(holdout),
        "signal_contributions": signal_contributions,
        "family_contributions": family_contributions,
    }


def _print_report(report: dict) -> None:
    print("=== Ablation harness ===")
    print(f"Baseline per-session mean rho (all 17 signals) = {report['baseline_mean_rho']:.4f}")
    print(f"train={report['n_train_sessions']} holdout={report['n_holdout_sessions']} sessions")
    print()
    print("--- Family contribution (rho lost when the whole family is removed) ---")
    ranked = sorted(report["family_contributions"].items(), key=lambda kv: -kv[1]["mean_contribution"])
    for family, r in ranked:
        lo, hi = r["ci"]
        print(f"  {family:15s} contribution = {r['mean_contribution']:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  ({len(r['members'])} signals)")
    print()
    print("--- Signal contribution (rho lost when that one signal is removed) ---")
    ranked = sorted(report["signal_contributions"].items(), key=lambda kv: -kv[1]["mean_contribution"])
    for name, r in ranked:
        lo, hi = r["ci"]
        print(f"  {name:36s} [{r['family']}]  contribution = {r['mean_contribution']:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]")


if __name__ == "__main__":
    _print_report(run_ablation())
