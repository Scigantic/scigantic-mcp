# Changelog

## 0.1.1

Packaging and metadata only. No change to tool behaviour, arguments, or output.

- The PyPI page now links back to this repository. 0.1.0 was published about an
  hour before the repository existed, so its metadata carried only a homepage and
  a docs link, leaving anyone who found the package on PyPI with no route to the
  source. Adds `Repository` and `Issues` to `[project.urls]`.
- README: new **Stability** section stating plainly that the underlying Scigantic
  REST API is not versioned and may change, while the MCP tool names and their
  arguments are the stable surface.
- README: fixed a duplicated clause in the roadmap, left over from removing an
  internal document reference before this repository was made public.

## 0.1.0

First public release, and the first release of any kind — the package had been
advertised as `uvx scigantic-mcp` since June but was never actually published.

Five discovery tools over the public Scigantic catalog (`search_archives`,
`get_archive`, `get_schema_card`, `list_archive_files`, `get_data_access`) plus
two guided prompts (`explore_dataset`, `start_analysis`). Every tool calls
public, read-only endpoints, so there is no API key to configure.

- Requires MCP SDK 2.x (`mcp>=2,<3`). SDK 2.0 removed `mcp.server.fastmcp`
  entirely, so the previous open-ended `mcp>=1.2` floor would have installed an
  SDK this package could not import — the server was ported to `MCPServer`. The
  upper bound is deliberate: an unbounded floor is exactly what made that
  breakage silent.
- `serverInfo.version` now reports the package version. Under SDK 1.x's FastMCP
  it reported the SDK's version instead.
- Tests cover the server wiring, not just the tool layer. The tool tests import
  only `.tools`/`.client` so they run offline on any Python, which meant nothing
  ever imported `server.py` — every test passed while the server could not start.
  `tests/test_server_import.py` closes that gap and CI runs on 3.10 through 3.13.
- No `lookup_paper` tool. The backing endpoint resolves arXiv ids and keywords
  but not DOIs, `arXiv:`-prefixed ids, or titles of papers that are not on arXiv,
  while the tool description advertised all four. It will return once the
  description can be true.
