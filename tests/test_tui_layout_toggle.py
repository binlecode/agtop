import asyncio

import pytest

from agtop.agtop import build_parser
from agtop.tui.app import AgtopApp

pytestmark = pytest.mark.local


def test_v_key_toggles_main_section_layout_classes():
    args = build_parser().parse_args([])
    app = AgtopApp(args)
    binding_keys = list(app._bindings.key_to_bindings.keys())
    assert "v" in binding_keys

    async def run_scenario():
        async with app.run_test():
            main_section = app.query_one("#main-section")
            assert main_section.has_class("layout-horizontal")
            assert not main_section.has_class("layout-vertical")

            app.action_toggle_layout()
            assert main_section.has_class("layout-vertical")
            assert not main_section.has_class("layout-horizontal")

            app.action_toggle_layout()
            assert main_section.has_class("layout-horizontal")
            assert not main_section.has_class("layout-vertical")

    asyncio.run(run_scenario())
