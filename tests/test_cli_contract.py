import subprocess
import sys


def test_cli_help_runs_and_exposes_show_cores_as_flag():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--show_cores" in result.stdout
    assert "--show_cores SHOW_CORES" not in result.stdout
    assert "--core-view {gauge,history,both}" in result.stdout
    assert "--proc-filter PROC_FILTER" in result.stdout
    assert "--alert-bw-sat-percent ALERT_BW_SAT_PERCENT" in result.stdout
    assert "--alert-package-power-percent ALERT_PACKAGE_POWER_PERCENT" in result.stdout
    assert "--alert-swap-rise-gb ALERT_SWAP_RISE_GB" in result.stdout
    assert "--alert-sustain-samples ALERT_SUSTAIN_SAMPLES" in result.stdout
    assert "--subsamples SUBSAMPLES" in result.stdout


def test_cli_rejects_legacy_show_cores_value_form():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--show_cores", "true"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: true" in result.stderr


def test_cli_rejects_invalid_core_view_value():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--core-view", "sparkline"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_cli_rejects_invalid_proc_filter_regex():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--proc-filter", "["],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "invalid --proc-filter regex" in result.stderr


def test_cli_rejects_invalid_alert_bw_threshold():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--alert-bw-sat-percent", "101"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "threshold must be in the range 1-100" in result.stderr


def test_cli_rejects_invalid_alert_swap_rise_value():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--alert-swap-rise-gb", "-0.1"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "swap rise threshold must be >= 0" in result.stderr


def test_cli_rejects_invalid_alert_sustain_samples():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--alert-sustain-samples", "0"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "sustain samples must be >= 1" in result.stderr


def test_cli_rejects_removed_max_count_flag():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--max_count", "10"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_cli_rejects_invalid_subsamples_value():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--subsamples", "0"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "subsamples must be >= 1" in result.stderr


def test_module_import_is_safe_with_unrelated_argv():
    script = (
        "import sys; "
        "sys.argv=['prog', '--not-a-real-flag']; "
        "import agtop.agtop; "
        "print('import-ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "import-ok" in result.stdout
