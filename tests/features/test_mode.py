from server.features.mode import (
    PriorView,
    QuerySubmission,
    assign_mode,
    classify_query_tokens,
    is_comparison,
    is_query_active,
    is_refind,
)

BRANDS = {"kessler", "linden"}


# --- token classification ---------------------------------------------------


def test_three_or_more_tokens_is_directed():
    assert classify_query_tokens("blue running shoes", set()) == "directed"


def test_two_tokens_generic_is_broad():
    assert classify_query_tokens("running shoes", set()) == "broad"


def test_single_generic_token_is_broad():
    assert classify_query_tokens("lamp", set()) == "broad"


def test_model_token_is_directed():
    assert classify_query_tokens("um1530", set()) == "directed"


def test_brand_token_is_directed():
    assert classify_query_tokens("kessler chair", BRANDS) == "directed"  # 2 tokens, but brand present


def test_brand_token_case_insensitive():
    assert classify_query_tokens("Kessler", BRANDS) == "directed"


# --- query active window -----------------------------------------------------


def test_query_active_immediately_after_submission():
    q = QuerySubmission(submitted_at=1000, query="lamp")
    assert is_query_active(1000, q) is True


def test_query_active_within_180s():
    q = QuerySubmission(submitted_at=0, query="lamp")
    assert is_query_active(179_000, q) is True


def test_query_inactive_at_180s():
    q = QuerySubmission(submitted_at=0, query="lamp")
    assert is_query_active(180_000, q) is False


def test_query_inactive_before_submission():
    q = QuerySubmission(submitted_at=5000, query="lamp")
    assert is_query_active(1000, q) is False


def test_category_nav_click_clears_active_query_early():
    q = QuerySubmission(submitted_at=0, query="lamp")
    assert is_query_active(1000, q, category_nav_click_at=500) is False


def test_category_nav_click_after_now_does_not_clear():
    q = QuerySubmission(submitted_at=0, query="lamp")
    assert is_query_active(1000, q, category_nav_click_at=5000) is True


def test_no_query_is_never_active():
    assert is_query_active(1000, None) is False


# --- refind -------------------------------------------------------------------


def test_refind_true_when_viewed_over_60s_ago():
    prior = [PriorView(item_id="i1", start=0)]
    assert is_refind(60_000, "i1", prior) is True


def test_refind_false_when_viewed_under_60s_ago():
    prior = [PriorView(item_id="i1", start=30_000)]
    assert is_refind(60_000, "i1", prior) is False


def test_refind_false_for_a_different_item():
    prior = [PriorView(item_id="i2", start=0)]
    assert is_refind(60_000, "i1", prior) is False


# --- comparison -----------------------------------------------------------------


def test_comparison_true_within_120s_same_set_different_item():
    prior = [PriorView(item_id="i2", start=0, near_substitute_set_id="set-a")]
    assert is_comparison(100_000, "i1", "set-a", prior) is True


def test_comparison_false_outside_120s_window():
    prior = [PriorView(item_id="i2", start=0, near_substitute_set_id="set-a")]
    assert is_comparison(130_000, "i1", "set-a", prior) is False


def test_comparison_false_different_set():
    prior = [PriorView(item_id="i2", start=0, near_substitute_set_id="set-b")]
    assert is_comparison(60_000, "i1", "set-a", prior) is False


def test_comparison_false_when_item_has_no_set():
    prior = [PriorView(item_id="i2", start=0, near_substitute_set_id="set-a")]
    assert is_comparison(60_000, "i1", None, prior) is False


def test_comparison_ignores_repeat_views_of_the_same_item():
    prior = [PriorView(item_id="i1", start=0, near_substitute_set_id="set-a")]
    assert is_comparison(60_000, "i1", "set-a", prior) is False


# --- full precedence ---------------------------------------------------------


def test_precedence_refind_beats_everything():
    prior = [
        PriorView(item_id="i1", start=0),  # refind: >= 60s ago
        PriorView(item_id="i2", start=50_000, near_substitute_set_id="set-a"),  # comparison too
    ]
    mode = assign_mode(
        t=100_000,
        item_id="i1",
        near_substitute_set_id="set-a",
        prior_views=prior,
        active_query=QuerySubmission(submitted_at=99_000, query="kessler running shoes"),
        category_nav_click_at=None,
        brand_tokens=BRANDS,
    )
    assert mode == "refind"


def test_precedence_comparison_beats_search():
    prior = [PriorView(item_id="i2", start=0, near_substitute_set_id="set-a")]
    mode = assign_mode(
        t=60_000,
        item_id="i1",
        near_substitute_set_id="set-a",
        prior_views=prior,
        active_query=QuerySubmission(submitted_at=59_000, query="kessler running shoes"),
        category_nav_click_at=None,
        brand_tokens=BRANDS,
    )
    assert mode == "comparison"


def test_precedence_directed_search_beats_broad_search():
    mode = assign_mode(
        t=1000,
        item_id="i1",
        near_substitute_set_id=None,
        prior_views=[],
        active_query=QuerySubmission(submitted_at=0, query="kessler running shoes"),
        category_nav_click_at=None,
        brand_tokens=BRANDS,
    )
    assert mode == "directed_search"


def test_precedence_broad_search_when_no_directed_signal():
    mode = assign_mode(
        t=1000,
        item_id="i1",
        near_substitute_set_id=None,
        prior_views=[],
        active_query=QuerySubmission(submitted_at=0, query="lamp"),
        category_nav_click_at=None,
        brand_tokens=BRANDS,
    )
    assert mode == "broad_search"


def test_precedence_discovery_is_the_default():
    mode = assign_mode(
        t=1000,
        item_id="i1",
        near_substitute_set_id=None,
        prior_views=[],
        active_query=None,
        category_nav_click_at=None,
        brand_tokens=BRANDS,
    )
    assert mode == "discovery"
