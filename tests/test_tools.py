"""Offline tests for the Scigantic MCP tool layer.

Uses httpx.MockTransport so nothing hits the network. Each test wraps its async
body in asyncio.run(), so it runs under plain `pytest` without pytest-asyncio,
and the file is also directly executable: `python3 tests/test_tools.py`.

Note: these import scigantic_mcp.tools / .client only — NOT .server — so they
run on any Python with httpx, independent of the mcp SDK (which needs 3.10+).
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scigantic_mcp import tools  # noqa: E402
from scigantic_mcp.client import NotFoundError, ScigateClient  # noqa: E402


def make_client(handler) -> ScigateClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.test")
    return ScigateClient(base_url="https://api.test", http_client=http)


# --- fixtures: canned API responses keyed by (method, path) -----------------

ARCHIVE_WITH_CARD = {
    "id": "a1",
    "title": "Test Archive",
    "category": "Genomics & Bioinformatics",
    "cloudProvider": "huggingface",
    "license": "CC-BY-4.0",
    "summary": "A tiny test dataset",
    "description": "Longer description of the test dataset.",
    "websiteUrl": "https://example.org/a1",
    "bucketName": "test-bucket",
    "region": "us-east-1",
    "bucketAccessType": "public",
    "schemaCard": {
        "format": "parquet",
        "columns": [{"name": "gene", "type": "string"}],
        "accessHints": [{"language": "python-datasets", "snippet": "from datasets import load_dataset\nds = load_dataset(\"test-bucket\")"}],
        "starterCell": "import pandas as pd  # worked example",
    },
}

HF_NO_CARD = {
    "id": "hfnocard",
    "title": "HF No Card",
    "cloudProvider": "huggingface",
    "bucketName": "org/dataset",
    "bucketAccessType": "public",
}


def default_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    method = request.method
    if method == "GET" and path == "/api/archives":
        return httpx.Response(200, json={"success": True, "count": 1, "data": [ARCHIVE_WITH_CARD]})
    if method == "GET" and path == "/api/archives/a1":
        return httpx.Response(200, json={"success": True, "data": ARCHIVE_WITH_CARD})
    if method == "GET" and path == "/api/archives/nocard":
        return httpx.Response(200, json={"success": True, "data": {"id": "nocard", "title": "No Card"}})
    if method == "GET" and path == "/api/archives/hfnocard":
        return httpx.Response(200, json={"success": True, "data": HF_NO_CARD})
    if method == "GET" and path == "/api/archives/missing":
        return httpx.Response(404, json={"error": {"message": "not found"}})
    if method == "GET" and path == "/api/archives/a1/files":
        return httpx.Response(200, json={"success": True, "data": {"files": [
            {"name": "data.parquet", "size": 1024}, {"name": "README.md", "size": 50}]}})
    return httpx.Response(404, json={"error": {"message": "unmapped"}})


# --- tests -------------------------------------------------------------------

def test_search_archives_formats_results():
    async def body():
        c = make_client(default_handler)
        out = await tools.search_archives(c, query="genomics", limit=5)
        assert "Test Archive" in out
        assert "id: a1" in out
        assert "https://example.org/a1" in out  # falls back to websiteUrl
        await c.aclose()
    asyncio.run(body())


def test_search_requires_query():
    async def body():
        c = make_client(default_handler)
        assert "query is required" in await tools.search_archives(c, query="  ")
        await c.aclose()
    asyncio.run(body())


def test_get_archive_notes_schema_card():
    async def body():
        c = make_client(default_handler)
        out = await tools.get_archive(c, id="a1")
        assert "CC-BY-4.0" in out
        assert "schema card is available" in out
        await c.aclose()
    asyncio.run(body())


def test_get_archive_404():
    async def body():
        c = make_client(default_handler)
        assert "not found" in (await tools.get_archive(c, id="missing")).lower()
        await c.aclose()
    asyncio.run(body())


def test_get_schema_card_present_and_absent():
    async def body():
        c = make_client(default_handler)
        present = await tools.get_schema_card(c, id="a1")
        assert "parquet" in present
        assert json.loads(present[present.index("{"):])  # the JSON body parses
        absent = await tools.get_schema_card(c, id="nocard")
        assert "No schema card" in absent
        await c.aclose()
    asyncio.run(body())


def test_list_archive_files():
    async def body():
        c = make_client(default_handler)
        out = await tools.list_archive_files(c, id="a1")
        assert "data.parquet (1024 bytes)" in out
        await c.aclose()
    asyncio.run(body())


def test_get_data_access_uses_schema_card_hints():
    async def body():
        c = make_client(default_handler)
        out = await tools.get_data_access(c, id="a1")
        assert "test-bucket" in out
        assert "load_dataset" in out          # the card's accessHint snippet
        assert "worked example" in out         # the starterCell
        assert "region: us-east-1" in out
        await c.aclose()
    asyncio.run(body())


def test_get_data_access_filters_by_language():
    async def body():
        c = make_client(default_handler)
        out = await tools.get_data_access(c, id="a1", language="datasets")
        assert "load_dataset" in out
        await c.aclose()
    asyncio.run(body())


def test_get_data_access_fallback_when_no_card():
    async def body():
        c = make_client(default_handler)
        out = await tools.get_data_access(c, id="hfnocard")
        assert "generated (no schema-card hints" in out
        assert 'load_dataset("org/dataset")' in out  # HF fallback
        await c.aclose()
    asyncio.run(body())


def test_client_retries_on_503_then_succeeds():
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/archives":
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503, json={"error": {"message": "try later"}})
            return httpx.Response(200, json={"success": True, "data": [ARCHIVE_WITH_CARD]})
        return httpx.Response(404)

    async def body():
        c = make_client(flaky)
        c.max_retries = 2
        out = await tools.search_archives(c, query="genomics")
        assert "Test Archive" in out
        assert calls["n"] == 2  # one retry happened
        await c.aclose()
    asyncio.run(body())


def test_client_raises_notfound():
    async def body():
        c = make_client(default_handler)
        raised = False
        try:
            await c.get_json("/api/archives/missing")
        except NotFoundError:
            raised = True
        assert raised
        await c.aclose()
    asyncio.run(body())


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'OK' if failures == 0 else 'FAILURES: ' + str(failures)}")
    sys.exit(1 if failures else 0)
