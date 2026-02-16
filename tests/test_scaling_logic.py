from agtop.power_scaling import power_to_percent, resolve_power_denominator


def test_profile_mode_uses_profile_reference_with_floor():
    denominator = resolve_power_denominator(
        mode="profile",
        profile_ref_w=55.0,
        peak_w=200.0,
        floor_w=20.0,
    )
    assert denominator == 55.0


def test_auto_mode_uses_peak_multiplier():
    denominator = resolve_power_denominator(
        mode="auto",
        profile_ref_w=55.0,
        peak_w=40.0,
        floor_w=20.0,
    )
    assert denominator == 50.0


def test_auto_mode_uses_floor_when_peak_is_low():
    denominator = resolve_power_denominator(
        mode="auto",
        profile_ref_w=55.0,
        peak_w=0.0,
        floor_w=15.0,
    )
    assert denominator == 15.0


def test_power_to_percent_clamps_output():
    assert power_to_percent(999.0, "profile", profile_ref_w=10.0, peak_w=10.0, floor_w=10.0) == 100
    assert power_to_percent(-10.0, "profile", profile_ref_w=10.0, peak_w=10.0, floor_w=10.0) == 0
