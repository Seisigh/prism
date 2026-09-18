"""Extracts row-level held-out results (utility, prediction, mode,
session_id) using only the stable public `eval.*` API
(`build_corpus`/`train_per_mode_rankers`/`predict`/
`fit_population_prior`/`recover_session_signal_weighting`), so the exact
same script can be pointed at a different git worktree/commit and still
run -- that stability is what made retroactive bootstrap CIs for prior
recovery runs possible without re-deriving each run's row-level data by
hand. Diagnostic-only; writes a JSON dump rather than returning to a
caller, since its usual invocation is `python -m eval.diagnostics.extract_rows`
from within a specific worktree.
"""
from __future__ import annotations

import json
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

from eval.corpus import build_corpus
from eval.ranker import predict, train_per_mode_rankers
from eval.signal_weighting import fit_population_prior, recover_session_signal_weighting
from sim.embedding import build_item_vectors


def run_once(sessions_per_condition: int, seed_train: int, seed_holdout: int, shuffle: bool) -> dict:
    item_vectors = build_item_vectors()
    train = build_corpus(item_vectors, sessions_per_condition, seed=seed_train, shuffle_utility=shuffle)
    holdout = build_corpus(item_vectors, sessions_per_condition, seed=seed_holdout, shuffle_utility=shuffle)

    rankers = train_per_mode_rankers(train)
    holdout_rows = [row for cs in holdout for row in cs.rows]
    holdout_pred = predict(rankers, holdout_rows)

    train_rows = [row for cs in train for row in cs.rows]
    prior = fit_population_prior(train_rows)

    def _recovered(corpus_sessions):
        X, y = [], []
        for cs in corpus_sessions:
            X.append(recover_session_signal_weighting(cs.rows, prior).tolist())
            y.append(cs.session.archetype_name)
        return X, y

    X_train, y_train = _recovered(train)
    X_holdout, y_holdout = _recovered(holdout)
    probe = LogisticRegression(max_iter=1000)
    probe.fit(np.array(X_train), y_train)
    probe_pred = probe.predict(np.array(X_holdout)).tolist()

    rows_out = [
        {"session_id": row.session_id, "mode": row.mode, "utility": row.utility, "committed": row.committed, "pred": pred}
        for row, pred in zip(holdout_rows, holdout_pred)
    ]
    probe_out = [
        {"session_id": cs.session.session_id, "correct": bool(p == t)}
        for cs, p, t in zip(holdout, probe_pred, y_holdout)
    ]
    return {"rows": rows_out, "probe": probe_out}


if __name__ == "__main__":
    sessions_per_condition = int(sys.argv[1])
    seed_train = int(sys.argv[2])
    seed_holdout = int(sys.argv[3])
    shuffle = sys.argv[4] == "shuffle"
    out_path = sys.argv[5]
    result = run_once(sessions_per_condition, seed_train, seed_holdout, shuffle)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(f"wrote {len(result['rows'])} rows, {len(result['probe'])} probe entries to {out_path}")
