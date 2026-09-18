"""Establishes the recovery ceiling via three oracle probes, plus the
raw commitment-vs-utility correlation, per the author's instruction to
localize where information is lost (harness, label, features, or model
capacity) before touching any of them. Diagnostic-only: run as
`python -m eval.diagnostics.oracle_probes`, writes `oracle_results.json`
for `eval/diagnostics/bootstrap.py` to compute CIs from.

Deliberately a single **pooled** model for all three probes (no
per-mode split), unlike `eval/ranker.py`'s production training loop --
per-mode data scarcity is already a separately-documented open question
(STATE.md), and conflating it with "does the harness/label/features
carry information at all" would make the localization these probes
exist to provide ambiguous.

**Why oracle (a) (perfect feature, utility label) is not ~1.0, and what
that does and doesn't mean:** LightGBM's `lambdarank` objective needs a
small, fixed relevance scale shared across every training group, so a
continuous utility value has to be bucketed into a handful of discrete
grades (`UTILITY_LABEL_GRADES`) -- and LambdaRank's own objective only
ever compares pairs *within* a training group, with no mechanism to
calibrate predicted-score scale *across* groups. Both of those are true
of the real pipeline too, not artifacts of this diagnostic. The result:
oracle (a)'s **pooled** rho (0.54) undersells the harness badly, while
its **per-session mean** rho (0.86) is close to what "the harness
recovers a perfect signal near-perfectly" should look like. That gap
between pooled and per-session metrics for the *same* oracle run is the
finding that pooled rho is not the right number to hold the DoD bar
against -- see `eval/diagnostics/bootstrap.py`'s docstring.
"""
from __future__ import annotations

import json

import numpy as np
from lightgbm import LGBMRanker
from scipy.stats import pearsonr, spearmanr

from eval.corpus import build_corpus
from eval.ranker import SIGNAL_NAMES
from sim.embedding import build_item_vectors

SESSIONS_PER_CONDITION = 15
SEED_TRAIN = 0
SEED_HOLDOUT = 1
UTILITY_LABEL_GRADES = 30  # near LightGBM's default lambdarank label-mapping cap (~31)


def _utility_rank_label(rows) -> list[int]:
    """Ascending-utility rank within the session, bucketed into
    UTILITY_LABEL_GRADES discrete grades -- order-preserving, bounded."""
    n = len(rows)
    order = sorted(range(n), key=lambda i: rows[i].utility)
    grades = [0] * n
    for rank, i in enumerate(order):
        grades[i] = min(UTILITY_LABEL_GRADES - 1, (rank * UTILITY_LABEL_GRADES) // n)
    return grades


def _commitment_label(rows) -> list[int]:
    return [2 if row.committed else (0 if row.is_fast_skip else 1) for row in rows]


def _oracle_feature(row) -> list[float]:
    return [row.utility]


def _real_feature(row) -> list[float]:
    return [row.signals[name] if row.signals.get(name) is not None else np.nan for name in SIGNAL_NAMES]


def _build_xy(corpus_sessions, feature_fn, label_fn):
    X, y, groups = [], [], []
    for cs in corpus_sessions:
        rows = cs.rows
        if len(rows) < 2:
            continue
        for row, label in zip(rows, label_fn(rows)):
            X.append(feature_fn(row))
            y.append(label)
        groups.append(len(rows))
    return np.array(X, dtype=float), np.array(y, dtype=float), groups


def _train_and_predict(train, holdout, feature_fn, label_fn):
    X_train, y_train, groups_train = _build_xy(train, feature_fn, label_fn)
    model = LGBMRanker(objective="lambdarank", n_estimators=100, num_leaves=15, min_child_samples=5, learning_rate=0.1, verbosity=-1)
    model.fit(X_train, y_train, group=groups_train)
    holdout_rows = [row for cs in holdout for row in cs.rows]
    X_holdout = np.array([feature_fn(row) for row in holdout_rows], dtype=float)
    return holdout_rows, model.predict(X_holdout)


def _per_session_mean_rho(holdout_rows, preds) -> float | None:
    by_session: dict[str, list] = {}
    for row, p in zip(holdout_rows, preds):
        by_session.setdefault(row.session_id, []).append((row.utility, p))
    session_rhos = []
    for pairs in by_session.values():
        if len(pairs) < 3:
            continue
        u, p = zip(*pairs)
        if len(set(u)) < 2 or len(set(p)) < 2:
            continue
        session_rhos.append(spearmanr(u, p).correlation)
    return float(np.mean(session_rhos)) if session_rhos else None


def run_probe(train, holdout, feature_fn, label_fn, name):
    holdout_rows, preds = _train_and_predict(train, holdout, feature_fn, label_fn)
    utilities = [row.utility for row in holdout_rows]
    pooled = spearmanr(utilities, preds).correlation
    per_session = _per_session_mean_rho(holdout_rows, preds)
    print(f"[{name}] pooled rho = {pooled:.4f}   per-session mean rho = {per_session:.4f}")
    rows_out = [{"session_id": r.session_id, "utility": r.utility, "pred": float(p)} for r, p in zip(holdout_rows, preds)]
    return rows_out


def main():
    item_vectors = build_item_vectors()
    train = build_corpus(item_vectors, SESSIONS_PER_CONDITION, seed=SEED_TRAIN, shuffle_utility=False)
    holdout = build_corpus(item_vectors, SESSIONS_PER_CONDITION, seed=SEED_HOLDOUT, shuffle_utility=False)
    print(f"train sessions={len(train)}, holdout sessions={len(holdout)}")

    results = {
        "a_oracle_features_utility_labels": run_probe(train, holdout, _oracle_feature, _utility_rank_label, "a: oracle features, utility labels"),
        "b_oracle_features_commitment_labels": run_probe(train, holdout, _oracle_feature, _commitment_label, "b: oracle features, commitment labels"),
        "c_real_features_utility_labels": run_probe(train, holdout, _real_feature, _utility_rank_label, "c: real features, utility labels"),
    }

    holdout_rows_flat = [row for cs in holdout for row in cs.rows]
    utilities = np.array([row.utility for row in holdout_rows_flat])
    committed = np.array([1.0 if row.committed else 0.0 for row in holdout_rows_flat])
    r = pearsonr(utilities, committed)
    print(f"[commitment vs utility] pearson r = {r.statistic:.4f} (n={len(utilities)})")
    results["commitment_vs_utility"] = [
        {"session_id": row.session_id, "utility": row.utility, "committed": row.committed} for row in holdout_rows_flat
    ]

    with open("oracle_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f)
    print("wrote oracle_results.json")


if __name__ == "__main__":
    main()
