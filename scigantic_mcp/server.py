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

from . import __version__, surechembl, tools
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
        "get_schema_card to understand structure before analysis. "
        "The surechembl_* tools cover patent chemistry from SureChEMBL (EMBL-EBI): look a "
        "compound up by any identifier, list the patents that mention it, read a patent's "
        "bibliography and text, list the compounds named in it, search patents by Solr "
        "query, and run similarity or substructure searches over 31 million compounds."
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
# SureChEMBL patent chemistry (EMBL-EBI), via the scigantic-surechembl library.
# ---------------------------------------------------------------------------


@mcp.tool()
async def surechembl_compound(identifier: str) -> str:
    """Look up a compound in SureChEMBL, EMBL-EBI's database of chemistry extracted from
    patents, by any identifier, and report its structure, properties, cross-references
    (ChEMBL, PubChem, DrugBank, ChEBI, PDB) and how many patents mention it.

    Args:
        identifier: A SureChEMBL id ("SCHEMBL1353" or "1353"), a ChEMBL id ("CHEMBL25"),
            a PubChem CID as "pubchem:2244", a DrugBank id as "drugbank:DB00945", a standard
            InChIKey, a SMILES, or a chemical name ("aspirin").
    """
    return await surechembl.surechembl_compound(identifier)


@mcp.tool()
async def surechembl_patents_for_compound(identifier: str, limit: int = 20) -> str:
    """List the patents in which a compound was found (SureChEMBL). Accepts the same identifier
    forms as surechembl_compound. Aspirin is in ~700,000 documents, so read the total and
    narrow with surechembl_search_patents when it is large.

    Args:
        identifier: SureChEMBL id, ChEMBL id, "pubchem:CID", InChIKey, SMILES, or name.
        limit: Max patents to list (default 20, max 200).
    """
    return await surechembl.surechembl_patents_for_compound(identifier, limit=limit)


@mcp.tool()
async def surechembl_patent(doc_id: str, include_text: bool = False) -> str:
    """A patent document from SureChEMBL: title, dates, applicants, inventors, assignees,
    family, priority claims, number of compounds named in the text, abstract, and (optionally)
    the claims and description text.

    Args:
        doc_id: Publication number with kind code, e.g. "US-10000000-B2", "WO2016144528A1",
            "EP-3268771-B1".
        include_text: Also return the claims and description (can be long). Default false.
    """
    return await surechembl.surechembl_patent(doc_id, include_text=include_text)


@mcp.tool()
async def surechembl_patent_chemistry(doc_id: str, limit: int = 50) -> str:
    """The compounds SureChEMBL's text-mining finds named in a patent's text: SCHEMBL id,
    name, SMILES, InChIKey, formula, weight. Structures that appear only in images or MOL
    attachments are not included.

    Args:
        doc_id: Publication number with kind code, e.g. "US-5399578-A".
        limit: Max compounds to list (default 50, max 500).
    """
    return await surechembl.surechembl_patent_chemistry(doc_id, limit=limit)


@mcp.tool()
async def surechembl_search_patents(query: str, limit: int = 20) -> str:
    """Full-text patent search over SureChEMBL with Solr syntax. Plain terms search all text;
    field prefixes narrow: ttl (title), ab (abstract), clm (claims), desc, asg (assignee),
    inv (inventor), pdyear, cpc, ic (IPCR), fam (family id). Quote publication numbers:
    pn:"US-10000000-B2". Combine with AND/OR/NOT. Only US, EP, WO, JP and CN publications are
    searchable.

    Args:
        query: e.g. 'ttl:kinase AND asg:novartis AND pdyear:2024'.
        limit: Max patents to list (default 20, max 200).
    """
    return await surechembl.surechembl_search_patents(query, limit=limit)


@mcp.tool()
async def surechembl_structure_search(structure: str, mode: str = "similarity", limit: int = 20) -> str:
    """Search SureChEMBL's 31 million patent compounds by chemical structure.

    Args:
        structure: A SMILES.
        mode: "similarity" (Tanimoto, default), "substructure" (needs at least 5 atoms; the
            server caps results at 10,000), "identical" (all features must match), or
            "connectivity" (same skeleton, any stereo/isotopes).
        limit: Max hits (default 20, max 500).
    """
    return await surechembl.surechembl_structure_search(structure, mode=mode, limit=limit)


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


@mcp.prompt()
def patent_landscape(compound: str) -> str:
    """Map the patent landscape of a compound: who patents it, since when, in what context."""
    return (
        f"Map the patent landscape for the compound: {compound}\n\n"
        f'1. Call surechembl_compound("{compound}") to confirm the structure, its SCHEMBL id(s) and the total patent count.\n'
        "2. Call surechembl_patents_for_compound with a limit of 100. If the total is much larger, narrow with "
        "surechembl_search_patents using asg:/pdyear:/cpc: filters.\n"
        "3. Summarize: number of documents, the leading assignees and the publication-year range; where it helps, "
        "count documents per CPC area with surechembl_search_patents cpc: filters. Name representative documents "
        "by publication number.\n"
        "4. For the 1-2 most relevant documents, call surechembl_patent to read the abstract and claims, and "
        "surechembl_patent_chemistry to see what other structures they disclose."
    )


def main() -> None:
    """Console-script entry point — runs the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
