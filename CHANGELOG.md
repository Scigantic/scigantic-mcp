# Changelog

## 0.3.2

The six `surechembl_*` tools work again. SureChEMBL replaced its REST API
in November 2026, and every endpoint the tools reached through
scigantic-surechembl 0.3 returned 404 or 405. No tool, argument or prompt
was added, removed or renamed.

- Dependency raised to `scigantic-surechembl[names]>=0.4,<1`, the port to
  the new API. The `names` extra brings scigantic-pubchem: SureChEMBL no
  longer has a name lookup, so a chemical name passed to
  `surechembl_compound` or `surechembl_patents_for_compound` is resolved
  by PubChem to a structure and then by UniChem to SureChEMBL ids.
- `surechembl_patent` no longer prints CPC codes, citation counts or
  legal-event counts, which the new API does not return (they would have
  read as zero); it adds IPC codes and priority claims where the record
  has them, and its compound count is now "compounds named in the text".
- `surechembl_patent_chemistry` now lists the compounds SureChEMBL's
  text-mining finds in the patent text; structures that appear only in
  images or MOL attachments are no longer included, and the output says
  so. Counts are lower than before (US-5399578-A: about 450, was 986).
- `surechembl_search_patents` states that only US, EP, WO, JP and CN
  publications are searched, which the new API enforces.
- Tool descriptions and the `patent_landscape` prompt updated to match
  (the prompt now suggests `cpc:` filters in the search tool for CPC
  areas, since documents no longer carry CPC codes).
- The SureChEMBL live tests run again; the module-level skip is removed
  and the known-issue note is gone from the README.

## 0.3.1

Metadata only. No change to tools, prompts or arguments.

- README carries a second registry marker, `mcp-name: com.scigantic/mcp`,
  so the package can be listed in the official MCP Registry under the
  `com.scigantic` namespace.
- README now says the hosted server at `api.scigantic.com/mcp` has five tools
  this package lacks (`search`, `fetch`, `get_sample_notebook`, `lookup_paper`,
  `list_compute_tiers`), not two. The 0.3.0 note below that the hosted server
  lacks the SureChEMBL tools is out of date: it now exposes all six.
- `server.json` and `glama.json` added for directory listings.
- README catalog size updated to about 6,900 archives, and a known-issue note
  added: SureChEMBL changed its API, so the six `surechembl_*` tools fail
  until a later release. Their live tests are skipped for now.

## 0.3.0

Six SureChEMBL patent-chemistry tools and one prompt, backed by the
`scigantic-surechembl` library (new dependency, `>=0.2,<1`; it brings only
`requests`).

- `surechembl_compound(identifier)`: SureChEMBL id, ChEMBL id, `pubchem:CID`,
  `drugbank:ID`, InChIKey, SMILES or name in; structure, properties, UniChem
  cross-references and patent count out. Bare digits are read as a SureChEMBL
  id, so a PubChem CID must be prefixed.
- `surechembl_patents_for_compound(identifier, limit)`: the union over every
  SureChEMBL id the identifier maps to, with per-id totals stated, since a
  structure can sit under more than one id.
- `surechembl_patent(doc_id, include_text)`: bibliography and abstract by
  default; claims and description (each capped at 12,000 characters) on
  request.
- `surechembl_patent_chemistry(doc_id, limit)`, `surechembl_search_patents(
  query, limit)` (Solr syntax passed through; a Solr syntax error is returned
  as its first line, not its grammar dump), `surechembl_structure_search(
  structure, mode, limit)` (similarity hits sorted by score client-side, since
  the server does not; substructure queries under 5 atoms are refused by the
  library before anything is sent).
- Prompt `patent_landscape(compound)`.
- All tool calls run the synchronous library in a worker thread; errors come
  back as `Error: ...` text, never as exceptions, matching the catalog tools.
- The hosted remote at `api.scigantic.com/mcp` is a separate TypeScript
  implementation and does not yet carry these tools; see the Scigantic repo.

## 0.2.0

Type-checking enforcement and a stale-header fix. No change to tool names,
arguments, or MCP-level behaviour; the HTTP `User-Agent` sent to the Scigantic
API does change (see below), which is why this is a minor bump rather than a
patch the way 0.1.1's pure-metadata change was.

- `USER_AGENT` in `client.py` was a hardcoded literal, `"scigantic-mcp/0.1
  (+https://scigantic.com)"`, already stale since the package moved past
  0.1.x. It is now built from the package's own `__version__` (`from . import
  __version__`), the same source `server.py`'s `serverInfo.version` already
  reads, so there is exactly one version-of-truth. A new test asserts the
  header actually carries the current version, so this can't silently go
  stale again.
- Added a `py.typed` marker and verified (via a real `python -m build` +
  `unzip -l`) that it ships in the built wheel, plus `[tool.setuptools.package-data]`
  to make sure of it.
- Added `mypy --strict` as a CI job (`typecheck`, checking the `scigantic_mcp`
  package only, matching sibling `scigantic-pubchem`'s own `mypy src/...`
  scope — the test suite itself is not part of that gate). The code was
  already fully type-hinted; the only finding was `_backoff()` returning
  `Any` because typeshed types a non-literal `int ** int` loosely. Fixed by
  using a `2.0` float base instead of `2`.
- Added `Typing :: Typed` and per-version `Programming Language :: Python ::
  3.1x` classifiers so the new PyPI Python-version badge (see below) and the
  typed-package marker actually show up on PyPI, matching `scigantic-pubchem`.
- README: added CI, PyPI version, PyPI Python-version, and license badges,
  matching `scigantic-pubchem`'s existing badge row. This package had none
  before.
- CI and publish matrices widened from 3.10-3.13 to 3.10-3.14, matching
  `scigantic-pubchem`. Verified first that the `mcp` SDK's own PyPI
  classifiers list 3.14 support, and confirmed a real `mcp>=2,<3` install
  plus `mypy --strict` and the full test suite pass locally under 3.14
  before widening the matrix, rather than copying pubchem's matrix blindly.

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
- README: added the `mcp-name` ownership marker the official MCP Registry
  (registry.modelcontextprotocol.io) checks for on PyPI packages, ahead of
  publishing there as `io.github.Scigantic/scigantic-mcp`.

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
