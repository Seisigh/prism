"""tier1_label (§9.1) and is_fast_skip (§9.3 item 8) — the two
session-wide, forward-looking prediction targets. is_fast_skip's tests
below exist specifically because the first implementation keyed on
duration alone and was unsafe: dwell is ∩-shaped in utility (see
STATE.md's decile curve), so a short view is ambiguous between a
confident reject and a confident accept, and duration alone can't tell
them apart.
"""
from server.features.labels import is_fast_skip, tier1_label
from server.features.window_spec import CommitmentEvent


def test_tier1_label_true_when_committed_after_view_start():
    commits = [CommitmentEvent(t=5000, item_id="i1", type="cart_add")]
    assert tier1_label("i1", view_start=1000, commitment_events=commits) is True


def test_tier1_label_false_for_a_different_item():
    commits = [CommitmentEvent(t=5000, item_id="i2", type="cart_add")]
    assert tier1_label("i1", view_start=1000, commitment_events=commits) is False


def test_tier1_label_false_when_commitment_is_before_view_start():
    commits = [CommitmentEvent(t=500, item_id="i1", type="cart_add")]
    assert tier1_label("i1", view_start=1000, commitment_events=commits) is False


# --- is_fast_skip: the regression this file exists for -----------------------


def test_short_view_with_no_later_commitment_or_revisit_is_a_fast_skip():
    assert (
        is_fast_skip(
            view_duration_ms=300,
            item_id="i1",
            view_start=1000,
            commitment_events=[],
            other_view_starts_for_item=[],
        )
        is True
    )


def test_long_view_is_never_a_fast_skip_regardless_of_outcome():
    assert (
        is_fast_skip(
            view_duration_ms=5000,
            item_id="i1",
            view_start=1000,
            commitment_events=[],
            other_view_starts_for_item=[],
        )
        is False
    )


def test_short_view_later_committed_is_NOT_a_fast_skip():
    """The exact scenario duration-alone gets wrong: a strong positive
    utility resolves to commitment *fast* (see the drift-diffusion
    decile curve — dwell is shortest at a confident accept, same as at a
    confident reject). Without the commitment check, this instant-yes
    view would have landed in the negative class."""
    commits = [CommitmentEvent(t=2000, item_id="i1", type="cart_add")]
    assert (
        is_fast_skip(
            view_duration_ms=300,
            item_id="i1",
            view_start=1000,
            commitment_events=commits,
            other_view_starts_for_item=[],
        )
        is False
    )


def test_short_view_later_revisited_is_NOT_a_fast_skip():
    """A short first glance the visitor comes back to isn't a confident,
    final reject — it's ambiguous, and ambiguous must not be forced into
    the negative class either."""
    assert (
        is_fast_skip(
            view_duration_ms=300,
            item_id="i1",
            view_start=1000,
            commitment_events=[],
            other_view_starts_for_item=[9000],
        )
        is False
    )


def test_short_view_with_EARLIER_revisit_only_is_still_a_fast_skip():
    """A revisit *before* this view doesn't un-ambiguous this one — only
    a later look-back or commitment does. (The item might have been
    quickly re-confirmed as uninteresting on a second, still-short,
    look.)"""
    assert (
        is_fast_skip(
            view_duration_ms=300,
            item_id="i1",
            view_start=5000,
            commitment_events=[],
            other_view_starts_for_item=[1000],  # earlier, not later
        )
        is True
    )


def test_short_view_with_commitment_for_a_different_item_is_still_a_fast_skip():
    commits = [CommitmentEvent(t=2000, item_id="i2", type="cart_add")]
    assert (
        is_fast_skip(
            view_duration_ms=300,
            item_id="i1",
            view_start=1000,
            commitment_events=commits,
            other_view_starts_for_item=[],
        )
        is True
    )


def test_duration_exactly_at_threshold_is_not_a_fast_skip():
    assert (
        is_fast_skip(
            view_duration_ms=1500,
            item_id="i1",
            view_start=1000,
            commitment_events=[],
            other_view_starts_for_item=[],
            threshold_ms=1500,
        )
        is False
    )
