from server.features.window_spec import CommitmentEvent, seal_window_for_view


def test_no_commitment_window_is_the_full_view():
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=[])
    assert (spec.t_start, spec.t_end) == (0, 5000)
    assert spec.seal_reason == "view_close"


def test_commitment_truncates_window_minus_buffer():
    commits = [CommitmentEvent(t=3000, item_id="i1", type="cart_add")]
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=commits)
    assert spec.t_end == 2000  # 3000 - 1000ms buffer
    assert spec.seal_reason == "commitment_seal"


def test_commitment_for_a_different_item_is_ignored():
    commits = [CommitmentEvent(t=1000, item_id="i2", type="cart_add")]
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=commits)
    assert (spec.t_start, spec.t_end) == (0, 5000)


def test_earliest_of_multiple_commitments_wins():
    commits = [
        CommitmentEvent(t=4000, item_id="i1", type="wishlist"),
        CommitmentEvent(t=2500, item_id="i1", type="cart_add"),
    ]
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=commits)
    assert spec.t_end == 1500  # 2500 - 1000ms, the earlier commitment


def test_commitment_within_the_buffer_collapses_to_zero_length():
    commits = [CommitmentEvent(t=300, item_id="i1", type="cart_add")]
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=commits)
    assert spec.t_start == 0
    assert spec.t_end == 0  # clamped, never negative-length


def test_commitment_after_view_end_does_not_truncate():
    commits = [CommitmentEvent(t=9000, item_id="i1", type="cart_add")]
    spec = seal_window_for_view(view_start=0, view_end=5000, item_id="i1", commitment_events=commits)
    assert (spec.t_start, spec.t_end) == (0, 5000)
