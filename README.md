# scigantic-mcp

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes the
**Scigantic catalog of public scientific data archives** to any MCP client.

It is built to drop into **[Kiro for Life Sciences](https://github.com/aws-samples/sample-kiro-power-life-sciences)**
alongside its domain database servers. Where each Kiro server wraps one domain's
APIs (genomics, proteomics, structural, …), Scigantic is the **cross-domain
launchpad**: 5,000+ curated public archives spanning every domain, each with an
LLM-ready **schema card** (file format, columns, sample rows/headers, inlined
READMEs/data dictionaries, and a copy-paste starter cell) so an agent can
understand a dataset's structure *before* downloading anything.

It is **discovery-only and zero-config** — every tool calls public, read-only
Scigantic endpoints, so there is no API key to set up.

Requires Python 3.10+ and MCP SDK 2.x.

> **Prefer the hosted server if your client speaks HTTP.** Scigantic also runs a
> remote MCP server at `https://api.scigantic.com/mcp` (no auth, nothing to
> install, and it carries two extra tools):
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

## Prompts (guided workflows)

These surface as slash commands in Claude Code (`/mcp__scigantic__<name>`):

| Prompt | What it does |
|--------|--------------|
| `explore_dataset(topic)` | Search → inspect schema cards → recommend the best dataset → offer load code. |
| `start_analysis(archive_id, goal?)` | Pull schema card + data-access snippet for an archive and outline an analysis plan. |

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
