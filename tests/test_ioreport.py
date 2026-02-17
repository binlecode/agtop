import sys

import pytest


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_cfstr_from_cfstr_roundtrip():
    from agtop.ioreport import cf_release, cfstr, from_cfstr

    test_str = "Hello, IOReport!"
    ref = cfstr(test_str)
    assert ref is not None
    result = from_cfstr(ref)
    cf_release(ref)
    assert result == test_str


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_subscription_sample_returns_ref():
    from agtop.ioreport import IOReportSubscription, cf_release

    sub = IOReportSubscription([("Energy Model", None)])
    try:
        sample = sub.sample()
        assert sample is not None
        cf_release(sample)
    finally:
        sub.close()
