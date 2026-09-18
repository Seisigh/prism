"""Trains and persists the per-mode ranker + calibrator artifacts the
live scoring path (`server/models/ranker_store.py`) loads at process
startup. Run once at image-build time (`python -m server.models.train_ranker`,
called from the Dockerfile the same way `python -m catalog.build` bakes
the catalog in) -- **not** at every container start, since training
takes ~2 minutes at the fixed 625-session scale and doesn't need to
repeat on every restart of the same image.

Artifacts are written to `server/models/artifacts/` and are a *build
artifact*, not source: gitignored, exactly like the catalog build output
and for the same reason (reproducible from `sim/` + `eval/` + this
script, and a trained model binary has no business in version control).

**Calibration, stated precisely since §11 doesn't specify a method:**
Platt scaling (one-feature logistic regression, raw ranker score ->
P(committed)) fit per mode. Fit **in-sample**, on the same sessions the
ranker itself trained on -- a real, documented simplification (an
honest calibration would hold out a separate calibration split), noted
here rather than silently assumed away. `p_i` from this calibrator feeds
`server/models/taste_vector.py`'s `weight_from_calibrated_interest`
directly.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import asdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from eval.corpus import build_corpus
from eval.ranker import SIGNAL_NAMES, _feature_row, train_per_mode_rankers
from sim.embedding import build_item_vectors

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
SESSIONS_PER_CONDITION = 25  # matches STATE.md's fixed Gate 1 evaluation standard
SEED = 0


def train_and_save(output_dir: Path = ARTIFACTS_DIR, sessions_per_condition: int = SESSIONS_PER_CONDITION) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    item_vectors = build_item_vectors()
    train = build_corpus(item_vectors, sessions_per_condition, seed=SEED, relabel_world=False)
    rankers = train_per_mode_rankers(train)

    manifest = {"signal_names": SIGNAL_NAMES, "modes": sorted(rankers.keys()), "sessions_per_condition": sessions_per_condition}

    for mode, mode_ranker in rankers.items():
        booster_path = output_dir / f"ranker_{mode}.txt"
        mode_ranker.model.booster_.save_model(str(booster_path))

        # In-sample Platt scaling: raw score -> P(committed) for this mode.
        rows = [row for cs in train for row in cs.rows if row.mode == mode]
        X = np.array([_feature_row(row) for row in rows])
        scores = mode_ranker.model.predict(X)
        committed = np.array([1 if row.committed else 0 for row in rows])
        calibrator = LogisticRegression()
        if len(set(committed.tolist())) < 2:
            calibrator = None  # degenerate mode (all-commit or none) -- no calibration possible
        else:
            calibrator.fit(scores.reshape(-1, 1), committed)
        with open(output_dir / f"calibrator_{mode}.pkl", "wb") as f:
            pickle.dump(calibrator, f)

    with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Trained and saved rankers for modes: {manifest['modes']}")
    print(f"Artifacts written to {output_dir}")


if __name__ == "__main__":
    train_and_save()
