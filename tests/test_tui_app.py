import pytest

from agtop import __version__
from agtop.agtop import build_parser
from agtop.tui.app import AgtopApp

pytestmark = pytest.mark.local


def test_opening_banner_and_header_show_version():
    app = AgtopApp(build_parser().parse_args([]))

    # The opening splash banner and the persistent header sub-title must both
    # surface the running version (regression: banner showed no version).
    assert __version__ in app._build_splash()
    assert __version__ in (app.sub_title or "")


def test_status_bar_exposes_only_supported_actions():
    app = AgtopApp(build_parser().parse_args([]))
    keys = set(app._bindings.key_to_bindings.keys())

    # Kept utilities, including the help overlay.
    assert {"q", "p", "s", "g", "t", "slash", "question_mark"} <= keys

    # Removed utilities: layout toggle and dashboard-collapse no longer exist.
    assert "v" not in keys
    assert "space" not in keys

    # The framework command palette is disabled (no ^p in the status bar).
    assert app.ENABLE_COMMAND_PALETTE is False


def test_help_overlay_documents_keys_metrics_and_alert_tokens():
    from agtop.tui.app import HELP_TEXT

    # Every keybinding action is described in the overlay.
    for action in ("Quit", "Pause", "Filter", "help"):
        assert action in HELP_TEXT

    # The previously-undocumented alert tokens are now explained in-app.
    for token in ("THERMAL", "BW>", "PKG>", "SWAP+"):
        assert token in HELP_TEXT

    # The new cur/avg/max chart context is explained too.
    assert "avg" in HELP_TEXT
    assert "max" in HELP_TEXT
