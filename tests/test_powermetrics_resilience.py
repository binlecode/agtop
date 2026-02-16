import plistlib

from agtop import utils


def test_parse_powermetrics_returns_false_when_file_missing(tmp_path):
    base = tmp_path / "agtop_powermetrics"
    result = utils.parse_powermetrics(path=str(base), timecode="123")
    assert result is False


def test_parse_powermetrics_falls_back_to_previous_frame_when_last_frame_is_partial(
    tmp_path,
):
    base = tmp_path / "agtop_powermetrics"
    payload = {
        "timestamp": 1700000000,
        "processor": {},
        "gpu": {},
        "thermal_pressure": "Nominal",
    }
    complete_frame = plistlib.dumps(payload, fmt=plistlib.FMT_XML)
    partial_frame = b"<plist><dict><key>timestamp</key><integer>"
    base.write_bytes(complete_frame + b"\x00" + partial_frame)

    result = utils.parse_powermetrics(path=str(base), timecode="")

    assert result is not False
    cpu_metrics, gpu_metrics, thermal_pressure, bandwidth_metrics, timestamp = result
    assert cpu_metrics["cpu_W"] == 0.0
    assert gpu_metrics["active"] == 0
    assert thermal_pressure == "Nominal"
    assert bandwidth_metrics is None
    assert timestamp == 1700000000

