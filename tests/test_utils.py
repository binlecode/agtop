import subprocess

from asitop import utils


def test_run_powermetrics_process_ignores_cleanup_permission_errors(monkeypatch):
    monkeypatch.setattr(utils.glob, "glob", lambda pattern: ["/tmp/asitop_powermetrics_stale"])

    def fake_remove(path):
        raise PermissionError("permission denied")

    popen_calls = {}

    class DummyProcess:
        pass

    def fake_popen(args, stdin=None, stdout=None):
        popen_calls["args"] = args
        popen_calls["stdin"] = stdin
        popen_calls["stdout"] = stdout
        return DummyProcess()

    monkeypatch.setattr(utils.os, "remove", fake_remove)
    monkeypatch.setattr(utils.subprocess, "Popen", fake_popen)

    process = utils.run_powermetrics_process("123", nice=5, interval=2000)

    assert isinstance(process, DummyProcess)
    assert popen_calls["args"] == [
        "sudo",
        "nice",
        "-n",
        "5",
        "powermetrics",
        "--samplers",
        "cpu_power,gpu_power,thermal",
        "-o",
        "/tmp/asitop_powermetrics123",
        "-f",
        "plist",
        "-i",
        "2000",
    ]
    assert popen_calls["stdin"] is subprocess.PIPE
    assert popen_calls["stdout"] is subprocess.PIPE
