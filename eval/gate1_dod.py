"""Gate 1 Definition of Done (BUILD_BRIEF.md §11), run end to end:

    1. Spearman rho > 0.6 between predicted interest and known utility
       on held-out simulated sessions
    2. Archetype separation: linear probe on recovered signal-weighting
       vectors classifies the five archetypes at > 70%
    3. Negative control: shuffle injected utilities, assert rho ~= 0 and
       archetype accuracy ~= chance
    4. Per-mode metrics reported separately

Run as a script (`python -m eval.gate1_dod`) rather than a pytest test:
it trains real LightGBM models over a few thousand simulated views,
which is a fine one-off report to regenerate and paste into STATE.md but
too slow (and not usefully deterministic-across-versions) to run on
every `pytest` invocation. tests/eval/test_gate1_dod.py exercises the
same code path at a tiny scale as a smoke test, not a DoD claim.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression

from eval.corpus import build_corpus
from eval.ranker import predict, train_per_mode_rankers
from eval.signal_weighting import fit_population_prior, recover_session_signal_weighting
from sim.agents import ARCHETYPES
from sim.embedding import build_item_vectors


def _rho(rows, predicted) -> float | None:
    pairs = [(u, p) for row, p in zip(rows, predicted) for u in [row.utility] if p is not None]
    if len(pairs) < 3:
        return None
    utilities, scores = zip(*pairs)
    if len(set(scores)) < 2 or len(set(utilities)) < 2:
        return None
    return float(spearmanr(utilities, scores).correlation)


def _per_session_mean_rho(corpus, predicted_flat) -> float | None:
    idx = 0
    session_rhos = []
    for cs in corpus:
        n = len(cs.rows)
        preds = predicted_flat[idx : idx + n]
        idx += n
        rho = _rho(cs.rows, preds)
        if rho is not None:
            session_rhos.append(rho)
    return float(np.mean(session_rhos)) if session_rhos else None


def run(sessions_per_condition: int = 10, seed_train: int = 0, seed_holdout: int = 1) -> dict:
    item_vectors = build_item_vectors()

    def _build(shuffle: bool):
        train = build_corpus(item_vectors, sessions_per_condition, seed=seed_train, shuffle_utility=shuffle)
        holdout = build_corpus(item_vectors, sessions_per_condition, seed=seed_holdout, shuffle_utility=shuffle)
        return train, holdout

    def _evaluate(train, holdout) -> dict:
        rankers = train_per_mode_rankers(train)

        holdout_rows = [row for cs in holdout for row in cs.rows]
        holdout_pred = predict(rankers, holdout_rows)
        overall_rho = _rho(holdout_rows, holdout_pred)
        per_session_rho = _per_session_mean_rho(holdout, holdout_pred)

        per_mode_rho = {}
        by_mode_rows = defaultdict(list)
        by_mode_pred = defaultdict(list)
        for row, pred in zip(holdout_rows, holdout_pred):
            by_mode_rows[row.mode].append(row)
            by_mode_pred[row.mode].append(pred)
        for mode in by_mode_rows:
            per_mode_rho[mode] = _rho(by_mode_rows[mode], by_mode_pred[mode])

        train_rows = [row for cs in train for row in cs.rows]
        prior = fit_population_prior(train_rows)

        def _recovered(corpus_sessions):
            X, y = [], []
            for cs in corpus_sessions:
                vec = recover_session_signal_weighting(cs.rows, prior)
                X.append(vec)
                y.append(cs.session.archetype_name)
            return np.array(X), np.array(y)

        X_train, y_train = _recovered(train)
        X_holdout, y_holdout = _recovered(holdout)

        probe = LogisticRegression(max_iter=1000)
        probe.fit(X_train, y_train)
        archetype_accuracy = float(probe.score(X_holdout, y_holdout))

        return {
            "overall_rho": overall_rho,
            "per_session_mean_rho": per_session_rho,
            "per_mode_rho": per_mode_rho,
            "archetype_accuracy": archetype_accuracy,
            "n_train_sessions": len(train),
            "n_holdout_sessions": len(holdout),
            "modes_with_rankers": sorted(rankers.keys()),
        }

    real_train, real_holdout = _build(shuffle=False)
    real = _evaluate(real_train, real_holdout)

    shuffled_train, shuffled_holdout = _build(shuffle=True)
    shuffled = _evaluate(shuffled_train, shuffled_holdout)

    return {"real": real, "negative_control": shuffled, "n_archetypes": len(ARCHETYPES)}


def _print_report(report: dict) -> None:
    real, control = report["real"], report["negative_control"]
    print("=== Gate 1 DoD ===")
    print(f"Train sessions: {real['n_train_sessions']}, Held-out sessions: {real['n_holdout_sessions']}")
    print(f"Modes with a trained ranker: {real['modes_with_rankers']}")
    print()
    print(f"[1] Overall Spearman rho (predicted vs utility, held-out): {real['overall_rho']:.3f} (need > 0.6)")
    print(f"    Per-session mean rho: {real['per_session_mean_rho']:.3f}")
    for mode, rho in sorted(real["per_mode_rho"].items()):
        print(f"    [4] {mode:16s} rho = {rho if rho is None else f'{rho:.3f}'}")
    print()
    chance = 1.0 / report["n_archetypes"]
    print(f"[2] Archetype separation accuracy: {real['archetype_accuracy']:.3f} (need > 0.7, chance = {chance:.2f})")
    print()
    print("--- Negative control (shuffled utility) ---")
    print(f"[3] rho (should be ~0): {control['overall_rho']}")
    print(f"[3] archetype accuracy (should be ~chance): {control['archetype_accuracy']:.3f}")


if __name__ == "__main__":
    _print_report(run())
