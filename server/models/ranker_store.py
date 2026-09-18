"""Loads the per-mode ranker + calibrator artifacts `train_ranker.py`
produces, once per process (mirrors `server/catalog_store.py`'s lazy
singleton pattern), and exposes the one thing the live scoring path
needs: raw signals in, calibrated interest `p_i` out.

Returns `None` rather than a fabricated score whenever scoring genuinely
isn't possible: no artifacts trained yet, an unrecognized mode, or a
degenerate mode with no calibrator (see `train_ranker.py`). Per §9.2's
"never impute zero" principle, extended to the scoring layer: an
unscoreable view should never look like a confidently-neutral one.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

_boosters: dict[str, lgb.Booster] | None = None
_calibrators: dict[str, object] | None = None
_signal_names: list[str] | None = None


class RankerNotTrainedError(RuntimeError):
    pass


def _load() -> None:
    global _boosters, _calibrators, _signal_names
    manifest_path = ARTIFACTS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise RankerNotTrainedError(
            f"{manifest_path} not found — run `python -m server.models.train_ranker` first "
            "(the Dockerfile does this at image-build time, like the catalog)."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _signal_names = manifest["signal_names"]
    _boosters = {}
    _calibrators = {}
    for mode in manifest["modes"]:
        _boosters[mode] = lgb.Booster(model_file=str(ARTIFACTS_DIR / f"ranker_{mode}.txt"))
        with open(ARTIFACTS_DIR / f"calibrator_{mode}.pkl", "rb") as f:
            _calibrators[mode] = pickle.load(f)


def is_trained() -> bool:
    return (ARTIFACTS_DIR / "manifest.json").exists()


def signal_names() -> list[str]:
    if _signal_names is None:
        _load()
    return list(_signal_names)


def score(mode: str, normalized_signals: dict[str, float | None]) -> tuple[float | None, float | None]:
    """Returns (raw_score, calibrated_p_i), either element `None` if
    that mode has no trained model or no usable calibrator. Missing
    individual signals are passed through as NaN, exactly like training
    (`eval/ranker.py`'s `_feature_row`) — never imputed."""
    if _boosters is None:
        _load()
    booster = _boosters.get(mode)
    if booster is None:
        return (None, None)
    x = np.array([[normalized_signals.get(name) if normalized_signals.get(name) is not None else np.nan for name in _signal_names]])
    raw = float(booster.predict(x)[0])
    calibrator = _calibrators.get(mode)
    if calibrator is None:
        return (raw, None)
    p_i = float(calibrator.predict_proba(np.array([[raw]]))[0][1])
    return (raw, p_i)
