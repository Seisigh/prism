"""Prints the bootstrap-CI report for a set of row-level JSON dumps
produced by `eval.diagnostics.extract_rows` (recovery runs, keyed by
label -> (real_path, shuffle_path)) and, if present, an
`oracle_results.json` from `eval.diagnostics.oracle_probes`. Diagnostic
only -- this is reporting, not part of the trained pipeline.
"""
from __future__ import annotations

import json
import sys

import numpy as np
from scipy.stats import pearsonr

from eval.diagnostics.bootstrap import (
    bootstrap_mean,
    ci95,
    per_session_rhos,
    pooled_rho,
    session_level_bootstrap_rho,
    view_level_bootstrap_rho,
)

RNG = np.random.default_rng(12345)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def report_recovery_run(label, real_path, shuffle_path):
    real = _load(real_path)
    shuffle = _load(shuffle_path)

    real_pooled = pooled_rho(real["rows"])
    shuffle_pooled = pooled_rho(shuffle["rows"])
    real_persession = per_session_rhos(real["rows"])
    shuffle_persession = per_session_rhos(shuffle["rows"])

    print(f"\n=== {label} ===")
    print(f"n_views={len(real['rows'])}, n_sessions={len(real['probe'])}")
    print(f"REAL    pooled rho = {real_pooled:.4f}")
    print(f"  view-level bootstrap 95% CI:    {ci95(view_level_bootstrap_rho(real['rows'], rng=RNG), real_pooled)}")
    print(f"  session-level bootstrap 95% CI: {ci95(session_level_bootstrap_rho(real['rows'], rng=RNG), real_pooled)}")
    print(f"REAL    per-session MEAN rho = {real_persession.mean():.4f} (n={len(real_persession)})")
    print(f"  bootstrap 95% CI: {ci95(bootstrap_mean(real_persession, rng=RNG), real_persession.mean())}")
    print(f"CONTROL pooled rho = {shuffle_pooled:.4f}")
    print(f"  view-level bootstrap 95% CI:    {ci95(view_level_bootstrap_rho(shuffle['rows'], rng=RNG), shuffle_pooled)}")
    print(f"  session-level bootstrap 95% CI: {ci95(session_level_bootstrap_rho(shuffle['rows'], rng=RNG), shuffle_pooled)}")
    print(f"CONTROL per-session MEAN rho = {shuffle_persession.mean():.4f} (n={len(shuffle_persession)})")
    print(f"  bootstrap 95% CI: {ci95(bootstrap_mean(shuffle_persession, rng=RNG), shuffle_persession.mean())}")

    real_acc = np.array([1.0 if r["correct"] else 0.0 for r in real["probe"]])
    shuffle_acc = np.array([1.0 if r["correct"] else 0.0 for r in shuffle["probe"]])
    print(f"REAL    archetype accuracy = {real_acc.mean():.4f}, 95% CI: {ci95(bootstrap_mean(real_acc, rng=RNG), real_acc.mean())}")
    print(f"CONTROL archetype accuracy = {shuffle_acc.mean():.4f}, 95% CI: {ci95(bootstrap_mean(shuffle_acc, rng=RNG), shuffle_acc.mean())}")


def report_oracle_results(path="oracle_results.json"):
    data = _load(path)

    def _probe(name, rows):
        pooled = pooled_rho(rows)
        persession = per_session_rhos(rows)
        print(f"\n[{name}]")
        print(f"  pooled rho = {pooled:.4f}, 95% CI: {ci95(view_level_bootstrap_rho(rows, rng=RNG), pooled)}")
        print(f"  per-session mean rho = {persession.mean():.4f} (n={len(persession)}), 95% CI: {ci95(bootstrap_mean(persession, rng=RNG), persession.mean())}")

    _probe("a: oracle features, utility labels", data["a_oracle_features_utility_labels"])
    _probe("b: oracle features, commitment labels", data["b_oracle_features_commitment_labels"])
    _probe("c: real features, utility labels", data["c_real_features_utility_labels"])

    rows = data["commitment_vs_utility"]
    u = np.array([r["utility"] for r in rows])
    c = np.array([1.0 if r["committed"] else 0.0 for r in rows])
    r = pearsonr(u, c).statistic
    n = len(u)
    view_boots = []
    for _ in range(2000):
        idx = RNG.integers(0, n, n)
        if len(set(c[idx].tolist())) > 1:
            view_boots.append(pearsonr(u[idx], c[idx]).statistic)
    print(f"\n[commitment vs utility] pearson r = {r:.4f} (n={n})")
    print(f"  view-level bootstrap 95% CI: {ci95(np.array(view_boots), r)}")


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    for commit, label in [
        ("c7348bd", "c7348bd (motor coupling fix, rho reported 0.074)"),
        ("7db852d", "7db852d (directional signals added, rho reported 0.099)"),
        ("HEAD", "dbb0e53 / HEAD (raw signals + polarity fix, rho reported 0.011)"),
    ]:
        report_recovery_run(label, f"{base}/{commit}/out_real.json", f"{base}/{commit}/out_shuffle.json")
    report_oracle_results()
