import pytest

from agtop.smc import SMCReader, TemperatureReading

pytestmark = pytest.mark.local


def test_smc_reader_connects_and_discovers_keys():
    reader = SMCReader()
    try:
        assert reader.available is True
    finally:
        reader.close()


def test_smc_reader_returns_temperature_reading():
    reader = SMCReader()
    try:
        temps = reader.read_temperatures()
        assert isinstance(temps, TemperatureReading)
        assert isinstance(temps.cpu_temps_c, list)
        assert isinstance(temps.gpu_temps_c, list)
    finally:
        reader.close()


def test_smc_reader_temperatures_are_physical():
    reader = SMCReader()
    try:
        temps = reader.read_temperatures()
        # On Apple Silicon, we expect at least some CPU and GPU sensors
        assert len(temps.cpu_temps_c) > 0, "No CPU temperature sensors found"
        assert len(temps.gpu_temps_c) > 0, "No GPU temperature sensors found"

        # All returned values must be in the physical range (0, 150)
        for t in temps.cpu_temps_c:
            assert 0.0 < t < 150.0, "CPU temp {:.1f}C out of range".format(t)
        for t in temps.gpu_temps_c:
            assert 0.0 < t < 150.0, "GPU temp {:.1f}C out of range".format(t)
    finally:
        reader.close()


def test_smc_reader_close_is_idempotent():
    reader = SMCReader()
    reader.available  # trigger connection
    reader.close()
    reader.close()  # should not raise
