from catalog.taxonomy import infer_age_band, infer_gender


def test_infer_gender_detects_womens_signal():
    assert infer_gender("womens", "womens block heel shoes") == "womens"


def test_infer_gender_detects_mens_signal_without_women_false_positive():
    assert infer_gender("womens", "mens leather dress shoe") == "mens"


def test_infer_gender_does_not_confuse_men_substring_in_women():
    # "men" is a substring of "women" — must not misfire "mens" here.
    assert infer_gender("womens", "womens block heel shoes") != "mens"


def test_infer_gender_leaves_ungendered_types_alone():
    assert infer_gender("unisex", "mens leather dress shoe") == "unisex"


def test_infer_gender_falls_back_to_default_when_ambiguous():
    assert infer_gender("womens", "shoes for men and women") == "womens"


def test_infer_age_band_detects_kids_keyword():
    assert infer_age_band("adult", "toddler building blocks") == "kids"


def test_infer_age_band_defaults_when_no_signal():
    assert infer_age_band("adult", "stainless steel saucepan") == "adult"
