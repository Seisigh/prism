"""Gate 1 Definition of Done — revised (author's ruling, retracting the
original fixed bar): rho > 0.6 sat above the measured ceiling of the
label the pipeline must use (oracle: perfect features + the commitment
label tops out at ~0.33 per-session rho — see STATE.md's ceiling
analysis). It was unreachable, not demanding, so it is retracted rather
than chased.

**Gate 1 now closes on two non-overlap gates**, each paired with a
reported efficiency metric (not a gate):

- **PRIMARY GATE (rho):** the real condition's per-session mean rho 95%
  CI must not overlap the CI of the corrected negative control
  (`eval/negative_control.py`) — the actual scientific claim (recovers
  signal rather than noise), with no magnitude to guess.
- **EFFICIENCY (rho, reported only):** achieved per-session mean rho /
  ceiling rho (oracle: perfect features + the commitment label). States
  performance relative to the information the label actually makes
  available, not against an arbitrary target.
- **Same treatment for archetype accuracy:** its own ceiling probe
  (ridge recovery against true utility instead of the sparse commitment
  label, otherwise identical), gated on non-overlap with its own
  corrected control, efficiency reported *chance-adjusted*
  (`(achieved - chance) / (ceiling - chance)`) since accuracy's floor is
  chance (0.20), not zero, and a raw ratio would be misleading.

`sessions_per_condition` is fixed at 25 (STATE.md's "Process" section) —
lowering it for runtime without flagging the change in the report is
exactly the mistake that produced the 625->375 discrepancy this file
used to have.

Per-session mean rho with a session-level bootstrap CI is the reporting
standard. Pooled rho is still computed and printed, but only ever as a
labeled diagnostic (see `eval/diagnostics/bootstrap.py`'s docstring for
why it systematically understates a model trained on a within-session
objective) — never the headline, per instruction.

Run as a script (`python -m eval.gate1_dod`): it trains several real
LightGBM/ridge models over several thousand simulated views, too slow
for every `pytest` invocation. `tests/eval/test_gate1_dod.py` exercises
the same code path at a tiny scale as a smoke test, not a DoD claim.
"""
from __future__ import annotations

import random
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression

from eval.corpus import build_corpus
from eval.negative_control import ci_overlap, permuted_archetype_labels, permuted_utility_by_session
from eval.ranker import predict, train_per_mode_rankers
from eval.signal_weighting import fit_population_prior, recover_session_signal_weighting
from sim.agents import ARCHETYPES
from sim.embedding import build_item_vectors

SESSIONS_PER_CONDITION = 25  # fixed -- see module docstring's "Process" note
CHANCE_ACCURACY = 1.0 / len(ARCHETYPES)
N_BOOT = 2000


# --- rho helpers -------------------------------------------------------------


def _pooled_rho(utilities, preds) -> float | None:
    pairs = [(u, p) for u, p in zip(utilities, preds) if p is not None]
    if len(pairs) < 3:
        return None
    u, p = zip(*pairs)
    if len(set(u)) < 2 or len(set(p)) < 2:
        return None
    return float(spearmanr(u, p).correlation)


def _per_session_rhos(rows, utilities, preds) -> np.ndarray:
    by_session = defaultdict(list)
    for row, u, p in zip(rows, utilities, preds):
        if p is not None:
            by_session[row.session_id].append((u, p))
    out = []
    for pairs in by_session.values():
        if len(pairs) < 3:
            continue
        u, p = zip(*pairs)
        if len(set(u)) < 2 or len(set(p)) < 2:
            continue
        out.append(spearmanr(u, p).correlation)
    return np.array(out)


def _bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = N_BOOT) -> tuple[float | None, float | None]:
    if len(values) == 0:
        return (None, None)
    n = len(values)
    boots = np.array([values[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return (float(lo), float(hi))


# --- archetype-accuracy ceiling: recover against true utility instead of the weak label ----


def _true_utility_labels(rows) -> np.ndarray:
    return np.array([row.utility for row in rows])


def _recovered_vectors(train, holdout, label_fn=None):
    """`label_fn=None` uses signal_weighting.py's own default (the real,
    production weak label) -- only the ceiling probe passes
    `_true_utility_labels` explicitly."""
    kwargs = {} if label_fn is None else {"label_fn": label_fn}
    train_rows = [row for cs in train for row in cs.rows]
    prior = fit_population_prior(train_rows, **kwargs)

    def _for(corpus_sessions):
        X, y = [], []
        for cs in corpus_sessions:
            X.append(recover_session_signal_weighting(cs.rows, prior, **kwargs))
            y.append(cs.session.archetype_name)
        return np.array(X), np.array(y)

    return _for(train), _for(holdout)


def _probe_accuracy(train, holdout, label_fn=None) -> tuple[float, np.ndarray, list[str], list[str]]:
    """Returns (accuracy, per-session-correct array, predicted labels, true labels)."""
    (X_train, y_train), (X_holdout, y_holdout) = _recovered_vectors(train, holdout, label_fn)
    probe = LogisticRegression(max_iter=1000)
    probe.fit(X_train, y_train)
    pred = probe.predict(X_holdout)
    correct = (pred == y_holdout).astype(float)
    return float(correct.mean()), correct, pred.tolist(), y_holdout.tolist()


def run(sessions_per_condition: int = SESSIONS_PER_CONDITION, seed_train: int = 0, seed_holdout: int = 1) -> dict:
    rng_np = np.random.default_rng(0)
    rng_py = random.Random(0)

    item_vectors = build_item_vectors()
    train = build_corpus(item_vectors, sessions_per_condition, seed=seed_train, relabel_world=False)
    holdout = build_corpus(item_vectors, sessions_per_condition, seed=seed_holdout, relabel_world=False)
    holdout_rows = [row for cs in holdout for row in cs.rows]

    # --- rho: real condition ---
    rankers = train_per_mode_rankers(train)
    real_preds = predict(rankers, holdout_rows)
    real_utilities = [row.utility for row in holdout_rows]

    real_pooled = _pooled_rho(real_utilities, real_preds)
    real_persession = _per_session_rhos(holdout_rows, real_utilities, real_preds)
    real_persession_ci = _bootstrap_mean_ci(real_persession, rng_np)
    real_persession_mean = float(real_persession.mean()) if len(real_persession) else None

    per_mode_persession_rho = {}
    by_mode = defaultdict(list)
    for row, u, p in zip(holdout_rows, real_utilities, real_preds):
        by_mode[row.mode].append((row, u, p))
    for mode, triples in by_mode.items():
        mrows, mu, mp = zip(*triples)
        mrhos = _per_session_rhos(list(mrows), list(mu), list(mp))
        per_mode_persession_rho[mode] = float(mrhos.mean()) if len(mrhos) else None

    # --- rho: corrected negative control (evaluation-target permutation) ---
    control_utilities = permuted_utility_by_session(holdout_rows, rng_py)
    control_pooled = _pooled_rho(control_utilities, real_preds)
    control_persession = _per_session_rhos(holdout_rows, control_utilities, real_preds)
    control_persession_ci = _bootstrap_mean_ci(control_persession, rng_np)
    control_persession_mean = float(control_persession.mean()) if len(control_persession) else None

    rho_gate_pass = (
        real_persession_ci[0] is not None
        and control_persession_ci[0] is not None
        and not ci_overlap(real_persession_ci, control_persession_ci)
    )

    # --- rho ceiling: oracle features (true utility) + the real commitment label, pooled model ---
    ceiling_rho_mean, ceiling_rho_ci = _rho_ceiling(train, holdout, rng_np)
    rho_efficiency = real_persession_mean / ceiling_rho_mean if (real_persession_mean is not None and ceiling_rho_mean) else None

    # --- archetype accuracy: real condition ---
    real_accuracy, real_correct, real_pred_labels, true_labels = _probe_accuracy(train, holdout)
    real_accuracy_ci = _bootstrap_mean_ci(real_correct, rng_np)

    # --- archetype accuracy: ceiling (recover against true utility, not the weak label) ---
    ceiling_accuracy, ceiling_correct, _, _ = _probe_accuracy(train, holdout, label_fn=_true_utility_labels)
    ceiling_accuracy_ci = _bootstrap_mean_ci(ceiling_correct, rng_np)

    # --- archetype accuracy: corrected negative control (shuffle true labels, keep real predictions) ---
    control_true_labels = permuted_archetype_labels(true_labels, rng_py)
    control_correct = np.array([1.0 if p == t else 0.0 for p, t in zip(real_pred_labels, control_true_labels)])
    control_accuracy = float(control_correct.mean())
    control_accuracy_ci = _bootstrap_mean_ci(control_correct, rng_np)

    accuracy_gate_pass = not ci_overlap(real_accuracy_ci, control_accuracy_ci)
    accuracy_denominator = ceiling_accuracy - CHANCE_ACCURACY
    accuracy_efficiency = (real_accuracy - CHANCE_ACCURACY) / accuracy_denominator if accuracy_denominator > 0 else None

    return {
        "n_train_sessions": len(train),
        "n_holdout_sessions": len(holdout),
        "sessions_per_condition": sessions_per_condition,
        "modes_with_rankers": sorted(rankers.keys()),
        "rho": {
            "real_pooled_diagnostic_only": real_pooled,
            "real_per_session_mean": real_persession_mean,
            "real_per_session_ci": real_persession_ci,
            "control_pooled_diagnostic_only": control_pooled,
            "control_per_session_mean": control_persession_mean,
            "control_per_session_ci": control_persession_ci,
            "gate_pass": rho_gate_pass,
            "ceiling_per_session_mean": ceiling_rho_mean,
            "ceiling_per_session_ci": ceiling_rho_ci,
            "efficiency": rho_efficiency,
            "per_mode_per_session_mean": per_mode_persession_rho,
        },
        "archetype_accuracy": {
            "real": real_accuracy,
            "real_ci": real_accuracy_ci,
            "control": control_accuracy,
            "control_ci": control_accuracy_ci,
            "gate_pass": accuracy_gate_pass,
            "ceiling": ceiling_accuracy,
            "ceiling_ci": ceiling_accuracy_ci,
            "chance": CHANCE_ACCURACY,
            "efficiency_chance_adjusted": accuracy_efficiency,
        },
        "gate1_closed": bool(rho_gate_pass and accuracy_gate_pass),
    }


def _rho_ceiling(train, holdout, rng_np: np.random.Generator) -> tuple[float | None, tuple[float | None, float | None]]:
    """Oracle (b) from the ceiling analysis: perfect feature (true
    utility itself), the real commitment label, a single pooled model
    (no per-mode split — per-mode data scarcity is a separate, already-
    documented question this ceiling is not trying to answer)."""
    from lightgbm import LGBMRanker

    def _commitment_label(rows):
        return [2 if row.committed else (0 if row.is_fast_skip else 1) for row in rows]

    X, y, groups = [], [], []
    for cs in train:
        rows = cs.rows
        if len(rows) < 2:
            continue
        for row, label in zip(rows, _commitment_label(rows)):
            X.append([row.utility])
            y.append(label)
        groups.append(len(rows))
    if not groups:
        return None, (None, None)

    model = LGBMRanker(objective="lambdarank", n_estimators=100, num_leaves=15, min_child_samples=5, learning_rate=0.1, verbosity=-1)
    model.fit(np.array(X, dtype=float), np.array(y, dtype=float), group=groups)

    holdout_rows = [row for cs in holdout for row in cs.rows]
    preds = model.predict(np.array([[row.utility] for row in holdout_rows], dtype=float))
    utilities = [row.utility for row in holdout_rows]
    persession = _per_session_rhos(holdout_rows, utilities, preds.tolist())
    mean = float(persession.mean()) if len(persession) else None
    ci = _bootstrap_mean_ci(persession, rng_np)
    return mean, ci


def _fmt_ci(ci: tuple[float | None, float | None]) -> str:
    lo, hi = ci
    if lo is None or hi is None:
        return "n/a"
    return f"[{lo:.3f}, {hi:.3f}]"


def _print_report(report: dict) -> None:
    rho, acc = report["rho"], report["archetype_accuracy"]
    print("=== Gate 1 DoD (revised bar) ===")
    print(f"sessions_per_condition = {report['sessions_per_condition']} (fixed; train={report['n_train_sessions']}, holdout={report['n_holdout_sessions']})")
    print(f"Modes with a trained ranker: {report['modes_with_rankers']}")
    print()
    print("--- rho ---")
    print(f"  pooled (diagnostic only, NOT the headline): real={rho['real_pooled_diagnostic_only']}, control={rho['control_pooled_diagnostic_only']}")
    print(f"  REAL    per-session mean rho = {rho['real_per_session_mean']:.4f}  95% CI {_fmt_ci(rho['real_per_session_ci'])}")
    print(f"  CONTROL per-session mean rho = {rho['control_per_session_mean']:.4f}  95% CI {_fmt_ci(rho['control_per_session_ci'])}")
    print(f"  PRIMARY GATE (non-overlap): {'PASS' if rho['gate_pass'] else 'FAIL'}")
    print(f"  Ceiling (oracle features, commitment label) per-session mean rho = {rho['ceiling_per_session_mean']:.4f}  95% CI {_fmt_ci(rho['ceiling_per_session_ci'])}")
    print(f"  Efficiency (achieved / ceiling) = {rho['efficiency']:.3f}" if rho["efficiency"] is not None else "  Efficiency: n/a")
    for mode, val in sorted(rho["per_mode_per_session_mean"].items()):
        print(f"    per-mode per-session mean rho: {mode:16s} {val if val is None else f'{val:.3f}'}")
    print()
    print("--- archetype accuracy ---")
    print(f"  REAL    = {acc['real']:.4f}  95% CI {_fmt_ci(acc['real_ci'])}")
    print(f"  CONTROL = {acc['control']:.4f}  95% CI {_fmt_ci(acc['control_ci'])}   (chance = {acc['chance']:.3f})")
    print(f"  GATE (non-overlap): {'PASS' if acc['gate_pass'] else 'FAIL'}")
    print(f"  Ceiling (recovery against true utility, not the weak label) = {acc['ceiling']:.4f}  95% CI {_fmt_ci(acc['ceiling_ci'])}")
    eff = acc["efficiency_chance_adjusted"]
    print(f"  Efficiency, chance-adjusted = {eff:.3f}" if eff is not None else "  Efficiency: n/a")
    print()
    print(f"=== GATE 1: {'CLOSED' if report['gate1_closed'] else 'NOT CLOSED'} ===")


if __name__ == "__main__":
    _print_report(run())
