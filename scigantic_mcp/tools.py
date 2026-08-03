"""Tool implementations for the Scigantic MCP server.

Pure async functions that take a ScigateClient and return formatted text. Kept
free of any `mcp` import so they can be unit-tested under any Python with a
mocked httpx transport; server.py wires them into the MCP server.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .client import NotFoundError, ScigateApiError, ScigateClient


def _source_url(a: Dict[str, Any]) -> str:
    return a.get("sourceUrl") or a.get("websiteUrl") or a.get("huggingFaceUrl") or "n/a"


def _summary(a: Dict[str, Any]) -> str:
    return (a.get("summary") or a.get("description") or "").strip()


async def search_archives(
    client: ScigateClient,
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
) -> str:
    query = (query or "").strip()
    if not query:
        return "Error: query is required."
    limit = max(1, min(int(limit or 10), 50))
    try:
        resp = await client.get_json(
            "/api/archives", {"search": query, "category": category, "limit": str(limit)}
        )
    except ScigateApiError as exc:
        return f"Search failed: {exc}"

    data: List[Dict[str, Any]] = resp.get("data") or []
    rows = data[:limit]
    if not rows:
        return f'No archives matched "{query}".'

    lines = [f"Found {len(rows)} archive(s) for \"{query}\":\n"]
    for i, a in enumerate(rows, 1):
        lines.append(
            f"{i}. {a.get('title', 'Untitled')}  [id: {a.get('id')}]\n"
            f"   {a.get('category') or 'Uncategorized'}"
            f"{' · ' + a['cloudProvider'] if a.get('cloudProvider') else ''}\n"
            f"   {_summary(a)[:200]}\n"
            f"   source: {_source_url(a)}"
        )
    lines.append("\nNext: call get_schema_card(id) to see a dataset's structure before using it.")
    return "\n".join(lines)


async def get_archive(client: ScigateClient, id: str) -> str:
    id = (id or "").strip()
    if not id:
        return "Error: id is required."
    try:
        resp = await client.get_json(f"/api/archives/{id}")
    except NotFoundError:
        return f"Archive {id} not found."
    except ScigateApiError as exc:
        return f"Could not fetch archive {id}: {exc}"

    a = resp.get("data") or {}
    has_card = bool(a.get("schemaCard"))
    storage = a.get("cloudProvider") or "?"
    if a.get("bucketName"):
        storage += " · " + a["bucketName"] + ("/" + a["bucketPrefix"] if a.get("bucketPrefix") else "")
    return (
        f"{a.get('title', 'Untitled')}  [id: {a.get('id')}]\n"
        f"Category: {a.get('category') or 'Uncategorized'}\n"
        f"License: {a.get('license') or 'n/a'}\n"
        f"Storage: {storage}\n"
        f"Source: {_source_url(a)}\n\n"
        f"{a.get('description') or _summary(a)}\n"
        + ("\n(A schema card is available — call get_schema_card for structure details.)" if has_card else "")
    )


async def get_schema_card(client: ScigateClient, id: str) -> str:
    id = (id or "").strip()
    if not id:
        return "Error: id is required."
    try:
        resp = await client.get_json(f"/api/archives/{id}")
    except NotFoundError:
        return f"Archive {id} not found."
    except ScigateApiError as exc:
        return f"Could not fetch archive {id}: {exc}"

    a = resp.get("data") or {}
    card = a.get("schemaCard")
    if not card:
        return f"No schema card has been generated for \"{a.get('title') or id}\" yet."
    return (
        f"Schema card for {a.get('title')} [id: {id}] — file format, columns, "
        f"sample rows/headers, sidecar docs, and a starter cell:\n\n"
        + json.dumps(card, indent=2, ensure_ascii=False)
    )


async def list_archive_files(client: ScigateClient, id: str, limit: int = 50) -> str:
    id = (id or "").strip()
    if not id:
        return "Error: id is required."
    limit = max(1, min(int(limit or 50), 200))
    try:
        resp = await client.get_json(f"/api/archives/{id}/files")
    except NotFoundError:
        return f"Archive {id} not found."
    except ScigateApiError as exc:
        return f"Could not list files for {id}: {exc}"

    data = resp.get("data") or {}
    files = data.get("files") if isinstance(data, dict) else data
    files = files or []
    shown = files[:limit]
    if not shown:
        return "No files listed (the bucket may be private, empty, or list-restricted)."

    def fmt(f: Any) -> str:
        if isinstance(f, str):
            return f
        name = f.get("name") or f.get("key") or "?"
        return f"{name}" + (f" ({f['size']} bytes)" if f.get("size") is not None else "")

    header = f"{len(shown)} file(s)" + (" (truncated)" if len(files) > len(shown) else "") + ":\n"
    return header + "\n".join(fmt(f) for f in shown)


def _fallback_snippet(a: Dict[str, Any]) -> str:
    """Best-effort load snippet for archives without a schema card's accessHints."""
    provider = (a.get("cloudProvider") or "").lower()
    bucket = a.get("bucketName") or ""
    prefix = a.get("bucketPrefix") or ""
    region = a.get("region") or ""
    public = (a.get("bucketAccessType") or "") == "public"
    path = bucket + (("/" + prefix) if prefix else "")
    if provider in ("huggingface", "hf"):
        return f'from datasets import load_dataset\nds = load_dataset("{bucket}")'
    if provider in ("gcp", "gcs"):
        tok = "token='anon'" if public else "token='google_default'"
        return f"import gcsfs\nfs = gcsfs.GCSFileSystem({tok})\nfs.ls('{path}')[:20]"
    if provider in ("aws", "s3"):
        anon = "anon=True" if public else "anon=False"
        note = f"  # region: {region}" if region else ""
        return f"import s3fs\nfs = s3fs.S3FileSystem({anon}){note}\nfs.ls('{path}')[:20]"
    if provider in ("api", "postgres"):
        return f"# Accessed via {provider}; see source: {_source_url(a)}"
    return f"# See source for access details: {_source_url(a)}"


async def get_data_access(client: ScigateClient, id: str, language: Optional[str] = None) -> str:
    """Return how to load this dataset in *your own* environment: storage location plus
    copy-paste code snippets (from the dataset's schema card, or generated as a fallback).
    """
    id = (id or "").strip()
    if not id:
        return "Error: id is required."
    try:
        resp = await client.get_json(f"/api/archives/{id}")
    except NotFoundError:
        return f"Archive {id} not found."
    except ScigateApiError as exc:
        return f"Could not fetch archive {id}: {exc}"

    a = resp.get("data") or {}
    card = a.get("schemaCard") or {}
    hints: List[Dict[str, Any]] = card.get("accessHints") or []
    if language:
        lang = language.lower()
        hints = [h for h in hints if lang in (h.get("language") or "").lower()] or hints

    storage = a.get("cloudProvider") or "?"
    if a.get("bucketName"):
        storage += " · " + a["bucketName"] + ("/" + a["bucketPrefix"] if a.get("bucketPrefix") else "")
    if a.get("region"):
        storage += f"  (region: {a['region']})"

    out = [
        f"How to access \"{a.get('title') or id}\" in your own environment:\n",
        f"Storage: {storage}",
        f"Access: {a.get('bucketAccessType') or 'unknown'}",
        f"Source: {_source_url(a)}",
        "",
        "Load it:",
    ]
    if hints:
        for h in hints:
            out.append(f"\n# {h.get('language') or 'snippet'}\n{h.get('snippet') or ''}")
    else:
        out.append(f"\n# generated (no schema-card hints for this archive)\n{_fallback_snippet(a)}")
    if card.get("starterCell"):
        out.append("\n# worked example (starter cell)\n" + card["starterCell"])
    return "\n".join(out)


# NOTE: a `lookup_paper` tool (paper -> linked archives) was dropped before the
# first PyPI release. The backing endpoint, /api/papers/lookup, is arXiv-only:
# it resolves bare arXiv ids and free-text keywords, but not DOIs, "arXiv:"-
# prefixed ids, or titles of papers that are not on arXiv — while the tool
# description advertised all four. Re-add it here once the backend resolves
# DOIs/titles, so the tool description can be true.
