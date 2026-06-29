"""cur/avg/max label-context math on HardwareDashboard.

Histories are zero-padded to a fixed length for chart right-alignment, so the
avg/max shown beside each live reading must reflect only real samples: avg over
the configured --avg window, max as the session peak. Validated by driving the
same deques the production update path feeds.
"""

from collections import deque
from types import SimpleNamespace

from agtop.tui.widgets import HardwareDashboard


def _dashboard(avg_window: int) -> HardwareDashboard:
    cfg = SimpleNamespace(
        alert_sustain_samples=3, chart_glyph="dots", avg_window=avg_window
    )
    return HardwareDashboard(config=cfg)


def _padded_hist(values) -> deque:
    hist: deque = deque([0] * 500, maxlen=500)
    for value in values:
        hist.append(value)
    return hist


def test_avg_uses_window_and_max_is_session_peak():
    dash = _dashboard(avg_window=3)
    hist = _padded_hist([10, 90, 20, 30, 40])
    dash._sample_count = 5

    avg, peak = dash._avg_max(hist)

    assert peak == 90  # session peak across all real samples
    assert round(avg, 4) == 30.0  # mean of the last 3 samples (20, 30, 40)


def test_avg_excludes_zero_padding_when_window_exceeds_samples():
    dash = _dashboard(avg_window=100)
    hist = _padded_hist([50, 70])
    dash._sample_count = 2

    avg, peak = dash._avg_max(hist)

    assert avg == 60.0  # padding zeros must not drag the average toward 0
    assert peak == 70


def test_avg_max_before_any_sample_is_zero():
    dash = _dashboard(avg_window=5)
    hist = _padded_hist([])  # no real samples appended
    dash._sample_count = 0

    assert dash._avg_max(hist) == (0.0, 0.0)


def test_percent_and_watt_suffix_formatting():
    dash = _dashboard(avg_window=5)
    hist = _padded_hist([10.0, 20.0, 90.0])
    dash._sample_count = 3

    # avg = 40, peak = 90 — the unit is appended so the stats are unambiguous
    # next to a headline carrying a different unit (MHz / GB / W).
    assert dash._pct_stats_suffix(hist) == "  avg 40% · max 90%"
    assert dash._watt_stats_suffix(hist) == "  avg 40.0W · max 90.0W"
