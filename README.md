# scigantic-mcp

<p align="center">
    <a href="https://github.com/Scigantic/scigantic-mcp/actions/workflows/ci.yml">
        <img alt="CI" src="https://github.com/Scigantic/scigantic-mcp/actions/workflows/ci.yml/badge.svg" /></a>
    <a href="https://pypi.org/project/scigantic-mcp/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/scigantic-mcp" /></a>
    <a href="https://pypi.org/project/scigantic-mcp/">
        <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/scigantic-mcp" /></a>
    <a href="https://github.com/Scigantic/scigantic-mcp/blob/main/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/Scigantic/scigantic-mcp" /></a>
</p>

<!-- mcp-name: io.github.Scigantic/scigantic-mcp -->
<!-- mcp-name: com.scigantic/mcp -->

An MCP server for finding public scientific datasets. It lets an AI assistant
search the [Scigantic catalog](https://scigantic.com/explore?utm_source=github&utm_medium=readme&utm_campaign=scigantic-mcp)
of more than 8,000 open data archives (genomics, cryo-EM and structural
biology, neuroimaging, chemistry, earth observation, climate) and read how a
dataset is laid out before downloading any of it. Each archive has a schema
card: file formats, columns, sample rows or decoded file headers, the dataset's
own README and data dictionary, and a starter code cell. Every tool calls
public, read-only endpoints, so there is no account and no API key.

If your client speaks HTTP, there is nothing to install. Add the hosted server:

```
https://api.scigantic.com/mcp
```

If your client launches stdio servers, run this package:

```json
{
  "mcpServers": {
    "scigantic": { "command": "uvx", "args": ["scigantic-mcp"] }
  }
}
```

Then ask for data in plain words. `search_archives("EMPIAR cryo-EM raw micrographs", limit=3)`
returns:

```
Found 3 archive(s) for "EMPIAR cryo-EM raw micrographs":

1. EMPIAR: Electron Microscopy Public Image Archive  [id: e3d9a7c0-1f2b-4a6d-9c8e-2b7f4a1c6e05]
   Structural Biology · api
   EMPIAR is EMBL-EBI's public archive of raw cryo-EM, cryo-ET, and volume-EM image datasets underpinning 3D structures in EMDB and PDB.
   source: https://www.ebi.ac.uk/empiar/
...
```

`get_schema_card(id)` then describes the files, and `get_data_access(id)` gives
the storage location and code to read it in your own environment.

## Try it on hosted data

An archive's page on scigantic.com opens the dataset in a hosted Jupyter
notebook with the data mounted read-only, so nothing is downloaded first. Two
examples:
[EMPIAR](https://scigantic.com/archive/e3d9a7c0-1f2b-4a6d-9c8e-2b7f4a1c6e05?utm_source=github&utm_medium=readme&utm_campaign=scigantic-mcp)
and [ChEMBL 37](https://scigantic.com/archive/97a98fc5-e6f9-555c-a22f-f2b548775f14?utm_source=github&utm_medium=readme&utm_campaign=scigantic-mcp).
A longer walkthrough of the server is in
[Use the Scigantic catalog from your AI agent with MCP](https://scigantic.com/blog/scigantic-mcp-server?utm_source=github&utm_medium=readme&utm_campaign=scigantic-mcp).

## Kiro for Life Sciences

The stdio package is built to drop into **[Kiro for Life Sciences](https://github.com/aws-samples/sample-kiro-power-life-sciences)**
alongside its domain database servers. Where each Kiro server wraps one domain's
APIs (genomics, proteomics, structural, …), Scigantic covers every domain in
one catalog, so an agent can find a dataset and understand its structure
before it picks a domain tool.

## Patent chemistry

Since 0.3.0 it also carries six `surechembl_*` tools for **patent chemistry**,
backed by [SureChEMBL](https://www.surechembl.org/) (EMBL-EBI, 31M compounds
extracted from 45M patents) through the
[scigantic-surechembl](https://github.com/Scigantic/scigantic-surechembl)
library: look a compound up by any identifier, list the patents that mention
it, read a patent, list the compounds named in it, search patents with Solr
syntax, and run structure searches. Also public, read-only, no key.

SureChEMBL replaced its REST API in November 2026. Since 0.3.2 these tools run
on scigantic-surechembl 0.4, the port to the new API. Three things the new API
no longer offers show up in the output: a patent's CPC codes, citations and
legal events are not returned; `surechembl_patent_chemistry` lists the compounds
named in a patent's text, not those that appear only in images or attachments;
and full-text search and patent families cover US, EP, WO, JP and CN
publications only. A chemical name is now resolved through PubChem, since
SureChEMBL has no name lookup any more.

Requires Python 3.10+ and MCP SDK 2.x.

> **Prefer the hosted server if your client speaks HTTP.** Scigantic also runs a
> remote MCP server at `https://api.scigantic.com/mcp` (no auth, nothing to
> install, and it carries five extra tools: `search`, `fetch`,
> `get_sample_notebook`, `lookup_paper` and `list_compute_tiers`):
> add `https://api.scigantic.com/mcp` as a streamable HTTP server in your client
> (Cursor, VS Code, Windsurf and others), or run
> `claude mcp add --transport http scigantic https://api.scigantic.com/mcp`.
> This package exists for clients that launch **stdio** servers, such as Kiro.

## Tools

| Tool | What it does |
|------|--------------|
| `search_archives(query, category?, limit?)` | Natural-language search across the whole catalog. |
| `get_archive(id)` | Full metadata for one archive. |
| `get_schema_card(id)` | The compact schema card — the fastest way to learn a dataset's structure. |
| `get_data_access(id, language?)` | How to load the dataset in **your own** environment: storage location + copy-paste code snippets. |
| `list_archive_files(id, limit?)` | A sample of the files/objects in the archive. |

### Patent chemistry (SureChEMBL)

| Tool | What it does |
|------|--------------|
| `surechembl_compound(identifier)` | A compound by SureChEMBL id, ChEMBL id, `pubchem:CID`, `drugbank:ID`, InChIKey, SMILES or name: structure, properties, cross-references, patent count. |
| `surechembl_patents_for_compound(identifier, limit?)` | The patents in which the compound was found, with the total. |
| `surechembl_patent(doc_id, include_text?)` | A patent's bibliography, abstract, family, priority claims, count of compounds named in the text, and optionally its claims and description. |
| `surechembl_patent_chemistry(doc_id, limit?)` | The compounds SureChEMBL's text-mining finds named in the patent. |
| `surechembl_search_patents(query, limit?)` | Full-text patent search with Solr field syntax (`ttl:`, `asg:`, `pdyear:`, `cpc:`, ...) over US, EP, WO, JP and CN publications. |
| `surechembl_structure_search(structure, mode?, limit?)` | Similarity, substructure, identical or connectivity search over 31M compounds. |

Identifiers are preserved verbatim in the output (SureChEMBL's attribution terms
ask that SCHEMBL ids and publication numbers be kept), and each result links to
surechembl.org. SureChEMBL data is CC BY 4.0.

## Prompts (guided workflows)

These surface as slash commands in Claude Code (`/mcp__scigantic__<name>`):

| Prompt | What it does |
|--------|--------------|
| `explore_dataset(topic)` | Search → inspect schema cards → recommend the best dataset → offer load code. |
| `start_analysis(archive_id, goal?)` | Pull schema card + data-access snippet for an archive and outline an analysis plan. |
| `patent_landscape(compound)` | Resolve a compound, count and list its patents, summarize assignees, years and CPC areas, read the key documents. |

## Install & register in Kiro

Add an entry under `mcpServers` in `~/.kiro/settings/mcp.json`.

**Option A — `uvx` (zero-install, recommended):**

```json
{
  "mcpServers": {
    "scigantic": {
      "command": "uvx",
      "args": ["scigantic-mcp"]
    }
  }
}
```

**Option B — install into a venv (matches the Kiro servers' own mcp.json form):**

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install scigantic-mcp                 # or: pip install /path/to/scigantic-mcp
```

```json
{
  "mcpServers": {
    "scigantic": {
      "command": "/path/to/.venv/bin/scigantic-mcp",
      "env": {
        "SCIGANTIC_API_URL": "https://api.scigantic.com"
      }
    }
  }
}
```

Works the same in Claude Desktop / Claude Code (`claude mcp add scigantic -- uvx scigantic-mcp`)
or any MCP client that launches stdio servers.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `SCIGANTIC_API_URL` | `https://api.scigantic.com` | API base (set to `https://staging-api.scigantic.com` for staging). |
| `SCIGANTIC_API_ORIGIN` | `https://scigantic.com` | Origin header → selects the public (default) catalog tenant. |

## Stability

This package is a thin client over the public Scigantic REST API. **That API is
not versioned and may change without notice** — if a response shape moves, a
pinned older release of this package can break. Pin a version you have tested,
and open an issue if a tool starts returning something unexpected.

The MCP tool names and their arguments are treated as the stable surface, and
will not change without a minor version bump.

## Develop & test

The tool/client layer has no `mcp` dependency, so those tests run on any Python
with `httpx` and need no network (mocked transport):

```bash
python3 tests/test_tools.py     # or: pytest
```

`tests/test_server_import.py` covers the wiring layer — that the server module
imports, and that the registered tools and prompts are the expected set. It needs
the `mcp` SDK installed (Python ≥ 3.10) and is skipped otherwise:

```bash
pip install -e '.[test]' && pytest
```

Keep it that way: the tool tests skip `server.py` on purpose, so an SDK breaking
change is invisible to them. All 12 passed while the server could not import at
all under SDK 2.x, which is what `test_server_import.py` now guards against.

## Roadmap

- **Richer discovery for agents** — structured tool outputs and MCP *resources*
  (attach an archive + its schema card as durable context).
- Upstream inclusion as `life-sciences-scigantic` in
  [`aws-samples/sample-kiro-power-life-sciences`](https://github.com/aws-samples/sample-kiro-power-life-sciences).
- **Hosted compute is intentionally not exposed here.** Scigantic's notebooks are
  interactive (a JupyterLab URL a human opens); handing an external agent that URL
  is a dead end. The agent-to-agent path is `get_data_access` — the caller runs the
  analysis in its own environment. Letting Scigantic *execute code for* an agent
  (run against an ephemeral kernel with the dataset mounted, return outputs) is a
  separate capability the platform would need to build first.

## License

MIT-0.
