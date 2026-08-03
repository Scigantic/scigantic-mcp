"""Stdio MCP server exposing the Scigantic catalog to MCP clients (Kiro, etc.).

Thin wiring layer: each tool delegates to scigantic_mcp.tools (which is what the
tests exercise). Run via the `scigantic-mcp` console script or `uvx scigantic-mcp`.

Built on `MCPServer` from the MCP Python SDK 2.x. SDK 1.x's `FastMCP` was removed
in 2.0 (`mcp.server.fastmcp` no longer exists), which is why pyproject pins
`mcp>=2,<3` rather than an open-ended floor.
"""

from __future__ import annotations

from typing import Optional

from mcp.server import MCPServer

from . import __version__, tools
from .client import ScigateClient

mcp = MCPServer(
    "scigantic",
    title="Scigantic",
    version=__version__,
    website_url="https://scigantic.com",
    instructions=(
        "Scigantic is a cross-domain catalog of public scientific data archives. "
        "Unlike single-domain database servers, it spans genomics, proteomics, structural "
        "biology, imaging, earth observation and more, and ships an LLM-ready 'schema card' "
        "for each dataset. Use search_archives to find datasets across domains, then "
        "get_schema_card to understand structure before analysis."
    ),
)

# Single shared client for the process lifetime (stdio server = one process).
_client: Optional[ScigateClient] = None


def _get_client() -> ScigateClient:
    global _client
    if _client is None:
        _client = ScigateClient()
    return _client


@mcp.tool()
async def search_archives(query: str, category: Optional[str] = None, limit: int = 10) -> str:
    """Search the Scigantic catalog of public scientific data archives by natural-language query.

    Returns ranked matches with id, title, category and a short summary across all domains.
    Follow up with get_schema_card to understand a match's structure.

    Args:
        query: Natural-language search, e.g. "single-cell RNA-seq of human cortex".
        category: Optional category filter, e.g. "Genomics & Bioinformatics" (comma-separate for several).
        limit: Max results (default 10, max 50).
    """
    return await tools.search_archives(_get_client(), query=query, category=category, limit=limit)


@mcp.tool()
async def get_archive(id: str) -> str:
    """Get full metadata for one archive by id, including whether a schema card exists.

    Args:
        id: Archive id from search_archives.
    """
    return await tools.get_archive(_get_client(), id=id)


@mcp.tool()
async def get_schema_card(id: str) -> str:
    """Get the compact schema card for an archive: file format, columns, sample rows/headers,
    sidecar docs (READMEs/data dictionaries) and a copy-paste starter cell.

    This is the fastest way to understand a dataset's structure without downloading it.

    Args:
        id: Archive id from search_archives.
    """
    return await tools.get_schema_card(_get_client(), id=id)


@mcp.tool()
async def list_archive_files(id: str, limit: int = 50) -> str:
    """List a sample of the files/objects in an archive's storage.

    Args:
        id: Archive id from search_archives.
        limit: Max entries (default 50, max 200).
    """
    return await tools.list_archive_files(_get_client(), id=id, limit=limit)


@mcp.tool()
async def get_data_access(id: str, language: Optional[str] = None) -> str:
    """Get how to load a dataset in YOUR OWN environment: storage location plus copy-paste
    code snippets (from the dataset's schema card, or generated as a fallback).

    Use this after finding a dataset when you want to run analysis where you are, rather
    than in a hosted notebook.

    Args:
        id: Archive id from search_archives.
        language: Optional filter for the snippet language (e.g. "datasets", "s3fs", "gcsfs").
    """
    return await tools.get_data_access(_get_client(), id=id, language=language)


# ---------------------------------------------------------------------------
# Prompts — guided workflows. In Claude Code these surface as slash commands
# (/mcp__scigantic__explore_dataset, /mcp__scigantic__start_analysis).
# ---------------------------------------------------------------------------


@mcp.prompt()
def explore_dataset(topic: str) -> str:
    """Find and understand a Scigantic dataset on a topic, end to end."""
    return (
        f"Find and understand a Scigantic dataset about: {topic}\n\n"
        f'1. Use search_archives to find candidate datasets for "{topic}".\n'
        "2. For the 1-2 most relevant results, call get_schema_card to understand structure "
        "(format, columns, sample rows/headers, sidecar docs).\n"
        "3. Summarize what's available and recommend the best fit, citing its archive id.\n"
        "4. If I want to use it, call get_data_access to give me copy-paste code to load it in this environment."
    )


@mcp.prompt()
def start_analysis(archive_id: str, goal: str = "") -> str:
    """Set up analysis of a specific Scigantic archive in your own environment."""
    goal = (goal or "").strip()
    return (
        f"Help me start analyzing the Scigantic archive {archive_id}."
        + (f" My goal: {goal}." if goal else "")
        + "\n\n"
        f"1. Call get_archive and get_schema_card for {archive_id} to understand the dataset.\n"
        "2. Call get_data_access to get the code to load it in this environment.\n"
        "3. Propose a concrete analysis plan and the initial code to load and explore the data"
        + (f", working toward: {goal}" if goal else "")
        + "."
    )


def main() -> None:
    """Console-script entry point — runs the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
