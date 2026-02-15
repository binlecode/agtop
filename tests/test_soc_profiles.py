from asitop.soc_profiles import get_soc_profile, normalize_soc_name


def test_normalize_soc_name_collapses_whitespace():
    assert normalize_soc_name("  Apple   M4   Max  ") == "Apple M4 Max"


def test_get_soc_profile_known_m4_max():
    profile = get_soc_profile("Apple M4 Max")
    assert profile.name == "Apple M4 Max"
    assert profile.cpu_chart_ref_w == 55.0
    assert profile.gpu_chart_ref_w == 90.0


def test_get_soc_profile_unknown_series_uses_tier_fallback():
    profile = get_soc_profile("Apple M5 Pro")
    assert profile.name == "Apple M5 Pro"
    assert profile.cpu_chart_ref_w == 40.0
    assert profile.gpu_chart_ref_w == 35.0


def test_get_soc_profile_non_apple_name_keeps_name_with_generic_scaling():
    profile = get_soc_profile("Custom Silicon")
    assert profile.name == "Custom Silicon"
    assert profile.cpu_chart_ref_w == 30.0
    assert profile.gpu_chart_ref_w == 30.0
