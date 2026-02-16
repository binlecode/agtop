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


def test_cli_rejects_legacy_show_cores_value_form():
    result = subprocess.run(
        [sys.executable, "-m", "agtop.agtop", "--show_cores", "true"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: true" in result.stderr


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
