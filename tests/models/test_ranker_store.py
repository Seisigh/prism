"""server/models/train_ranker.py + ranker_store.py: end-to-end train ->
persist -> reload -> score, at a tiny scale so it's fast enough for
pytest. Not a claim about the real deployed artifacts' quality -- those
are trained separately at image-build time (`python -m
server.models.train_ranker`, no override) and reported in STATE.md.
"""
import pytest

from sim.embedding import build_item_vectors

try:
    build_item_vectors()
    _CATALOG_BUILT = True
except FileNotFoundError:
    _CATALOG_BUILT = False

pytestmark = pytest.mark.skipif(not _CATALOG_BUILT, reason="data/catalog.json not built — run `python -m catalog.build`")


def _train_and_point_store_at(tmp_path, monkeypatch, sessions_per_condition=2):
    from server.models import ranker_store, train_ranker

    train_ranker.train_and_save(output_dir=tmp_path, sessions_per_condition=sessions_per_condition)
    monkeypatch.setattr(ranker_store, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ranker_store, "_boosters", None)
    monkeypatch.setattr(ranker_store, "_calibrators", None)
    monkeypatch.setattr(ranker_store, "_signal_names", None)
    return ranker_store


def test_train_persist_reload_and_score_end_to_end(tmp_path, monkeypatch):
    ranker_store = _train_and_point_store_at(tmp_path, monkeypatch)

    assert ranker_store.is_trained()
    names = ranker_store.signal_names()
    assert len(names) > 0

    signals = {n: 0.1 for n in names}
    raw, p_i = ranker_store.score("discovery", signals)
    assert raw is not None
    assert p_i is None or 0.0 <= p_i <= 1.0


def test_score_returns_none_for_an_unrecognized_mode(tmp_path, monkeypatch):
    ranker_store = _train_and_point_store_at(tmp_path, monkeypatch)

    raw, p_i = ranker_store.score("not_a_real_mode", {n: 0.1 for n in ranker_store.signal_names()})
    assert raw is None and p_i is None


def test_is_trained_false_when_no_manifest(tmp_path, monkeypatch):
    from server.models import ranker_store

    monkeypatch.setattr(ranker_store, "ARTIFACTS_DIR", tmp_path / "nothing_here")
    assert ranker_store.is_trained() is False
