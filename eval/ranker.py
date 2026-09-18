"""The ranker (BUILD_BRIEF.md §11): "LambdaRank over within-session item
pairs, not pointwise classification... Calibrated per mode." One
LightGBM LambdaRank model *per mode*, trained only on that mode's views
pooled across many sessions -- not one shared model with mode as a
feature -- because the whole thesis of this project (§4) is that the
same raw behavior means different things in different modes; a single
shared model would have to learn that interaction from data instead of
having it built into the training split, and a per-mode split is the
more honest, more identifiable way to "calibrate per mode."

Features are the raw (normalized) signals, never the five family
composites and never `utility` (the hidden ground truth). This changed
from an earlier version that fed the ranker composites, per the author's
explicit correction (BUILD_BRIEF.md §11, updated; see STATE.md's "Two
consumers, two representations" section): composite-averaging was
written for variance reduction on a small human corpus, and it does not
apply to a gradient-boosted ranker trained on hundreds of synthetic
sessions, where hand-averaging signals into five numbers before a tree
model sees them destroys exactly the interactions trees exist to find.
`eval/signal_weighting.py` is the one consumer that still uses
composites, for a genuinely different reason (see that module).

Missing signals are passed to LightGBM as NaN, which it treats as a
first-class missing value with a learned split direction -- unlike the
ridge recovery in signal_weighting.py, this does not need a numeric
imputation convention.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from lightgbm import LGBMRanker

from eval.corpus import CorpusSession
from eval.features import ALL_SIGNALS

# A fixed, sorted column order -- every feature row and every trained
# model must agree on which position is which signal.
SIGNAL_NAMES = sorted(ALL_SIGNALS.keys())

RELEVANCE_COMMITTED = 2
RELEVANCE_AMBIGUOUS = 1
RELEVANCE_FAST_SKIP = 0


def _feature_row(row) -> list[float]:
    return [row.signals[name] if row.signals.get(name) is not None else np.nan for name in SIGNAL_NAMES]


def _relevance(row) -> int:
    if row.committed:
        return RELEVANCE_COMMITTED
    if row.is_fast_skip:
        return RELEVANCE_FAST_SKIP
    return RELEVANCE_AMBIGUOUS


@dataclass
class ModeRanker:
    mode: str
    model: LGBMRanker
    n_train_sessions: int


def train_per_mode_rankers(corpus: list[CorpusSession], min_sessions_per_mode: int = 5) -> dict[str, ModeRanker]:
    by_mode: dict[str, list] = defaultdict(list)  # mode -> list of (session_id, rows)
    for cs in corpus:
        rows_by_mode: dict[str, list] = defaultdict(list)
        for row in cs.rows:
            rows_by_mode[row.mode].append(row)
        for mode, rows in rows_by_mode.items():
            by_mode[mode].append(rows)

    rankers: dict[str, ModeRanker] = {}
    for mode, per_session_rows in by_mode.items():
        if len(per_session_rows) < min_sessions_per_mode:
            continue
        X, y, groups = [], [], []
        for rows in per_session_rows:
            if len(rows) < 2:
                continue  # LambdaRank needs >=2 items per group to form a pair
            for row in rows:
                X.append(_feature_row(row))
                y.append(_relevance(row))
            groups.append(len(rows))
        if not groups:
            continue
        model = LGBMRanker(
            objective="lambdarank",
            n_estimators=100,
            num_leaves=15,
            min_child_samples=5,
            learning_rate=0.1,
            verbosity=-1,
        )
        model.fit(np.array(X), np.array(y), group=groups)
        rankers[mode] = ModeRanker(mode=mode, model=model, n_train_sessions=len(groups))
    return rankers


def predict(rankers: dict[str, ModeRanker], rows: list) -> list[float | None]:
    """Predicted interest score per row, `None` for a mode with no
    trained ranker (too few training sessions in that mode's stratum --
    an honest "can't score this yet", not a fabricated 0.0)."""
    out: list[float | None] = []
    by_mode_indices: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        by_mode_indices[row.mode].append(i)
    out = [None] * len(rows)
    for mode, indices in by_mode_indices.items():
        ranker = rankers.get(mode)
        if ranker is None:
            continue
        X = np.array([_feature_row(rows[i]) for i in indices])
        scores = ranker.model.predict(X)
        for i, score in zip(indices, scores):
            out[i] = float(score)
    return out
