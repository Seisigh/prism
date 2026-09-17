"""Signal-weighting vector recovery (BUILD_BRIEF.md §11): "Five composite
weights, initialized at the prior fit on simulated data, updated within
session by online ridge regression, shrunk toward the prior by evidence
count."

This is the Gate 1 DoD's *recovery target*, separate from the ranker:
each simulated session carries a known, independently-parameterized
`signal_weighting_vector` (sim/agents.py) that this module tries to
recover purely from a session's own composite features and outcomes, via
ridge regression shrunk toward a population prior. A linear probe on the
recovered vectors classifying which of the five archetypes generated
each session (>70% required, §11 DoD item 2) is the actual correctness
check -- if the composites+ranker pipeline didn't preserve real
archetype-distinguishing information, this recovery has nothing to find.

Composites are already z-scored (mean ~0 within their stratum), so
mean-imputing a missing composite to 0.0 for this *linear-model input*
is a neutral "no evidence either way" input, not a resurrection of the
"missing == 0.0 feature value" mistake §9.2 forbids for signal
functions themselves -- that rule is about not asserting a raw
behavioral value when one wasn't observed; this is a numerical
convention for a regression that needs a dense matrix. The distinction
is deliberate and documented here so it isn't silently generalized back
into signals.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import Ridge

from eval.features import ViewFeatureRow
from server.features.composites import FAMILIES

RIDGE_ALPHA_PRIOR = 5.0  # heavier shrinkage for the population prior fit
RIDGE_ALPHA_SESSION = 2.0  # per-session fit, shrunk toward the prior separately


def _design_matrix(rows: list[ViewFeatureRow]) -> np.ndarray:
    return np.array([[row.composites[f] if row.composites[f] is not None else 0.0 for f in FAMILIES] for row in rows])


def _weak_labels(rows: list[ViewFeatureRow]) -> np.ndarray:
    """§9.1's tier-1 weak label as a 3-grade target for ridge: fast_skip
    -> 0, ambiguous (neither committed nor a fast skip) -> 1,
    committed -> 2. Never the row's own `utility` -- that's the hidden
    ground truth this whole pipeline is trying to recover from behavior,
    not something training is allowed to see."""
    out = []
    for row in rows:
        if row.committed:
            out.append(2.0)
        elif row.is_fast_skip:
            out.append(0.0)
        else:
            out.append(1.0)
    return np.array(out)


def fit_population_prior(rows: list[ViewFeatureRow]) -> np.ndarray:
    """One ridge fit pooling every training-split view, regardless of
    session or archetype -- the population starting point every
    session's online update shrinks toward before its own evidence
    accumulates."""
    X, y = _design_matrix(rows), _weak_labels(rows)
    model = Ridge(alpha=RIDGE_ALPHA_PRIOR)
    model.fit(X, y)
    return model.coef_


def recover_session_signal_weighting(rows: list[ViewFeatureRow], prior: np.ndarray) -> np.ndarray:
    """A session's own ridge fit, shrunk toward `prior` in proportion to
    how little evidence the session has (few views -> lean on the prior;
    many views -> lean on the session's own fit) -- the "shrunk toward
    the prior by evidence count" half of §11's spec. With fewer than 3
    views there's nothing to fit at all, so the prior is returned as-is,
    mirroring the taste vector's own "population prior below 3 scored
    views" rule."""
    if len(rows) < 3:
        return prior.copy()
    X, y = _design_matrix(rows), _weak_labels(rows)
    model = Ridge(alpha=RIDGE_ALPHA_SESSION)
    model.fit(X, y)
    session_fit = model.coef_

    evidence = len(rows)
    shrinkage = evidence / (evidence + 10.0)  # ~half-weighted at 10 views
    return shrinkage * session_fit + (1 - shrinkage) * prior


@dataclass(frozen=True)
class RecoveredSession:
    session_id: str
    archetype_name: str
    recovered_vector: np.ndarray
