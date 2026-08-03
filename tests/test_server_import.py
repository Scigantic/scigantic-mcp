"""Smoke test for the server wiring layer — needs the mcp SDK.

This exists because tests/test_tools.py deliberately imports only .tools/.client
so it can run offline on any Python. That left server.py with ZERO coverage, and
it is exactly where the SDK contract lives: when SDK 2.0 removed
`mcp.server.fastmcp`, every tool test still passed while the server crashed on
import. Anything that would break `uvx scigantic-mcp` at startup belongs here.

Skipped automatically when mcp is not installed (e.g. Python < 3.10).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("mcp", reason="mcp SDK not installed (needs Python >= 3.10)")

EXPECTED_TOOLS = {
    "search_archives",
    "get_archive",
    "get_schema_card",
    "list_archive_files",
    "get_data_access",
}
EXPECTED_PROMPTS = {"explore_dataset", "start_analysis"}


def test_server_module_imports():
    """The import that SDK 2.0 broke. Guards the console-script entry point."""
    from scigantic_mcp import server

    assert callable(server.main)


def test_registered_tools_match_expected():
    import asyncio

    from scigantic_mcp import server

    names = {t.name for t in asyncio.run(_list(server.mcp.list_tools()))}
    assert names == EXPECTED_TOOLS


def test_registered_prompts_match_expected():
    import asyncio

    from scigantic_mcp import server

    names = {p.name for p in asyncio.run(_list(server.mcp.list_prompts()))}
    assert names == EXPECTED_PROMPTS


def test_server_reports_package_version():
    """MCPServer takes an explicit version; SDK 1.x's FastMCP reported the SDK's."""
    from scigantic_mcp import __version__, server

    assert server.mcp.version == __version__


async def _list(maybe_awaitable):
    """list_tools()/list_prompts() are sync in some SDK builds, async in others."""
    import inspect

    return await maybe_awaitable if inspect.isawaitable(maybe_awaitable) else maybe_awaitable
