import os
import stat
import subprocess
import sys


def _run_cli_with_fake_sudo(tmp_path, stderr_line):
    fake_sudo = tmp_path / "sudo"
    fake_sudo.write_text(
        "#!/bin/sh\necho \"$1\" >/dev/null\necho '{}' >&2\nexit 1\n".format(
            stderr_line.replace("'", "'\"'\"'")
        ),
        encoding="utf-8",
    )
    fake_sudo.chmod(fake_sudo.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env["PATH"] = str(tmp_path)

    return subprocess.run(
        [sys.executable, "-m", "agtop.agtop"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=10,
    )


def test_cli_reports_sudo_permission_guidance_and_restores_cursor(tmp_path):
    result = _run_cli_with_fake_sudo(tmp_path, "sudo: a password is required")

    assert result.returncode == 1
    assert "missing sudo privileges" in result.stdout
    assert "Run `sudo agtop` and try again." in result.stdout
    assert "\x1b[?25l" in result.stdout
    assert "\x1b[?25h" in result.stdout


def test_cli_reports_missing_powermetrics_binary(tmp_path):
    result = _run_cli_with_fake_sudo(tmp_path, "powermetrics: command not found")

    assert result.returncode == 1
    assert "the `powermetrics` binary was not found" in result.stdout
    assert "requires macOS with powermetrics available" in result.stdout
