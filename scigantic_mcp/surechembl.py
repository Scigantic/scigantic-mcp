"""SureChEMBL patent-chemistry tools for the Scigantic MCP server.

Thin async wrappers over the scigantic-surechembl library (its pacing,
retries, cache and hedged UniChem lookups are the reason to depend on it
rather than call the REST API here). Needs scigantic-surechembl 0.4 or
later, the port to SureChEMBL's late-2026 API; names resolve through its
`names` extra (PubChem), since SureChEMBL no longer has a name lookup. The library is synchronous, so each
call runs in a worker thread. Kept free of any `mcp` import so the tests
can exercise it directly, the same as tools.py.

Output is text shaped for a model to read: SCHEMBL ids and publication
numbers kept verbatim (SureChEMBL's attribution terms ask that ids be
preserved), one line per record, totals stated, and a "next" hint where
a follow-up tool applies.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable, Optional, TypeVar

import scigantic_surechembl as sc
from scigantic_surechembl import SureChEMBLError
from scigantic_surechembl._unichem import INCHIKEY_RE

T = TypeVar("T")

_SCHEMBL_RE = re.compile(r"^(?:SCHEMBL)?(\d+)$", re.IGNORECASE)
_CHEMBL_RE = re.compile(r"^CHEMBL\d+$", re.IGNORECASE)
_SMILES_CHARS_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)\\/%=#$.:*]+$")
_SMILES_HINT_RE = re.compile(r"[()\[\]=#@/\\]")

_MAX_TEXT = 12_000  # characters of patent text returned per section


async def _run(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await asyncio.to_thread(fn, *args, **kwargs)


def _clamp(n: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(n)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def _compound_line(c: sc.Compound) -> str:
    props = []
    if c.mol_formula:
        props.append(c.mol_formula)
    if c.mol_weight is not None:
        props.append(f"{c.mol_weight:.1f} Da")
    if c.log_p is not None:
        props.append(f"logP {c.log_p:.2f}")
    if c.similarity is not None:
        props.append(f"similarity {c.similarity:.2f}")
    return (
        f"{c.schembl_id}  {c.name or '(no name)'}\n"
        f"   SMILES: {c.smiles or 'n/a'}\n"
        f"   InChIKey: {c.inchi_key or 'n/a'}"
        + (f"  ({', '.join(props)})" if props else "")
    )


def _hit_line(h: sc.PatentHit) -> str:
    bits = [h.doc_id]
    if h.publication_date:
        bits.append(h.publication_date.isoformat())
    if h.assignee:
        bits.append(h.assignee)
    return f"{'  '.join(bits)}\n   {h.title or '(no title)'}\n   {h.url}"


# --- identifier resolution --------------------------------------------------


async def _resolve_ids(identifier: str) -> tuple[list[int], str]:
    """SureChEMBL ids for anything a user might paste, plus a note on how
    it was read. Order of interpretation: `SCHEMBL1353`/bare digits as a
    SureChEMBL id; `CHEMBL25` as ChEMBL; `pubchem:2244`/`cid:2244` as a
    PubChem CID; `drugbank:DB00945`, `chebi:...`, `pdb:...` via UniChem;
    a standard InChIKey; then SMILES or a name, whichever the string
    looks more like, with the other as fallback. A name is resolved by
    PubChem to a structure, then by UniChem to SureChEMBL ids."""
    raw = identifier.strip()
    if not raw:
        return [], "empty identifier"
    if _SCHEMBL_RE.match(raw):
        return [sc.compound_id(raw)], f"SureChEMBL id {sc.schembl_id(raw)}"
    if _CHEMBL_RE.match(raw):
        ids = await _run(sc.surechembl_ids_for, "chembl", raw.upper())
        return ids, f"ChEMBL id {raw.upper()} via UniChem"
    if ":" in raw:
        source, _, value = raw.partition(":")
        source = source.strip().lower()
        if source == "cid":
            source = "pubchem"
        ids = await _run(sc.surechembl_ids_for, source, value.strip())
        return ids, f"{source} id {value.strip()} via UniChem"
    if INCHIKEY_RE.match(raw.upper()):
        ids = await _run(sc.surechembl_ids_for_inchikey, raw.upper())
        return ids, f"InChIKey {raw.upper()} via UniChem"
    looks_like_smiles = bool(_SMILES_CHARS_RE.match(raw)) and (bool(_SMILES_HINT_RE.search(raw)) or raw.isupper())
    if looks_like_smiles:
        c = await _run(sc.by_smiles, raw)
        if c is not None:
            return [c.id], f"SMILES {raw}"
        found = await _run(sc.by_name, raw)
        return [c.id for c in found], f"name {raw!r} via PubChem (not a known SMILES)"
    found = await _run(sc.by_name, raw)
    if found:
        return [c.id for c in found], f"name {raw!r} via PubChem"
    if _SMILES_CHARS_RE.match(raw):
        c = await _run(sc.by_smiles, raw)
        if c is not None:
            return [c.id], f"SMILES {raw}"
    return [], f"name {raw!r}"


# --- tools ------------------------------------------------------------------


async def surechembl_compound(identifier: str) -> str:
    try:
        ids, how = await _resolve_ids(identifier)
        if not ids:
            return f"No SureChEMBL compound found for {how}."
        found = await _run(sc.compounds, ids)
        lines = [f"SureChEMBL compound(s) for {how}: {len(found)}\n"]
        for i in ids:
            c = found.get(i)
            if c is None:
                continue
            count = await _run(sc.count_patents_for_compound, i)
            lines.append(_compound_line(c))
            lines.append(f"   in {count:,} patent document(s)   {c.url}")
        x = await _run(sc.xrefs, ids[0])
        if x is not None:
            refs = []
            if x.chembl:
                refs.append("ChEMBL " + ", ".join(x.chembl))
            if x.pubchem_cid:
                refs.append("PubChem CID " + ", ".join(map(str, x.pubchem_cid)))
            if x.drugbank:
                refs.append("DrugBank " + ", ".join(x.drugbank))
            if x.chebi:
                refs.append(", ".join(x.chebi))
            if x.pdb_ligand:
                refs.append("PDB ligand " + ", ".join(x.pdb_ligand))
            if refs:
                lines.append("\nCross-references (UniChem): " + "; ".join(refs))
        lines.append(
            "\nNext: surechembl_patents_for_compound(identifier) lists the patents; "
            "surechembl_structure_search finds related structures."
        )
        return "\n".join(lines)
    except (ValueError, SureChEMBLError) as exc:
        return f"Error: {exc}"


async def surechembl_patents_for_compound(identifier: str, limit: int = 20) -> str:
    limit = _clamp(limit, 20, 1, 200)
    try:
        ids, how = await _resolve_ids(identifier)
        if not ids:
            return f"No SureChEMBL compound found for {how}."
        counts = {i: await _run(sc.count_patents_for_compound, i) for i in ids}
        hits: list[sc.PatentHit] = []
        seen: set[str] = set()
        for i in ids:
            for h in await _run(sc.patents_for_compound, i, limit):
                if h.doc_id not in seen:
                    seen.add(h.doc_id)
                    hits.append(h)
        hits = hits[:limit]
        total = " + ".join(f"{counts[i]:,} ({sc.schembl_id(i)})" for i in ids)
        lines = [f"Patents mentioning {how}: {total} document(s); showing {len(hits)}.\n"]
        lines.extend(_hit_line(h) for h in hits)
        if any(counts[i] > limit for i in ids):
            lines.append(
                f"\nOnly the first {limit} per SureChEMBL id are shown. Raise limit (max 200), or use "
                "surechembl_search_patents with a Solr query to narrow by assignee, year or title."
            )
        lines.append("\nNext: surechembl_patent(doc_id) for a document's text and bibliography.")
        return "\n".join(lines)
    except (ValueError, SureChEMBLError) as exc:
        return f"Error: {exc}"


async def surechembl_patent(doc_id: str, include_text: bool = False) -> str:
    try:
        p = await _run(sc.patent, doc_id)
    except (ValueError, SureChEMBLError) as exc:
        return f"Error: {exc}"
    if p is None:
        return f"SureChEMBL has no document {sc.patent_number(doc_id)}. Publication numbers need the kind code (US-10000000-B2, not US-10000000)."
    try:
        n_compounds = len(await _run(sc.patent_chemistry, p.doc_id))
    except SureChEMBLError:
        n_compounds = -1
    lines = [
        f"{p.doc_id}  {p.title or '(no title)'}",
        f"Published: {p.published.isoformat() if p.published else 'n/a'}"
        + (f"   Family: {p.family_id}" if p.family_id else ""),
        f"Applicants: {', '.join(p.applicants) or 'n/a'}",
        f"Inventors: {', '.join(p.inventors) or 'n/a'}",
        f"Assignees: {', '.join(p.assignees) or 'n/a'}",
    ]
    # SureChEMBL's late-2026 API returns no CPC codes, citations or legal
    # events with a document, so those lines are only shown when present.
    if p.cpc:
        lines.append(f"CPC: {', '.join(p.cpc[:12])}" + (" ..." if len(p.cpc) > 12 else ""))
    if p.ipcr:
        lines.append(f"IPC: {', '.join(p.ipcr[:12])}" + (" ..." if len(p.ipcr) > 12 else ""))
    if p.priority_numbers:
        lines.append(f"Priority: {', '.join(p.priority_numbers[:8])}" + (" ..." if len(p.priority_numbers) > 8 else ""))
    lines += [
        f"Compounds named in the text: {n_compounds if n_compounds >= 0 else 'unknown'}",
        f"URL: {p.url}" + (f"   PDF: {p.pdf_url}" if p.pdf_url else ""),
        "",
        "Abstract: " + (p.abstract or "n/a"),
    ]
    if include_text:
        lines.append("\nClaims:\n" + _truncate(p.claims))
        lines.append("\nDescription:\n" + _truncate(p.description))
    else:
        lines.append(
            "\nCall again with include_text=true for the claims and description "
            f"({len(p.claims or ''):,} and {len(p.description or ''):,} characters)."
        )
    lines.append("Next: surechembl_patent_chemistry(doc_id) for the compounds named in it.")
    return "\n".join(lines)


def _truncate(text: Optional[str]) -> str:
    if not text:
        return "n/a"
    return text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + f"\n... [{len(text) - _MAX_TEXT:,} more characters]"


async def surechembl_patent_chemistry(doc_id: str, limit: int = 50) -> str:
    limit = _clamp(limit, 50, 1, 500)
    try:
        compounds = await _run(sc.patent_chemistry, doc_id)
    except (ValueError, SureChEMBLError) as exc:
        return f"Error: {exc}"
    if not compounds:
        return f"SureChEMBL found no compounds named in the text of {sc.patent_number(doc_id)} (or has no such document)."
    lines = [
        f"{len(compounds):,} compound(s) named in the text of {sc.patent_number(doc_id)}; showing {min(limit, len(compounds))}. "
        "Structures shown only in images or attachments are not included.\n"
    ]
    lines.extend(_compound_line(c) for c in compounds[:limit])
    if len(compounds) > limit:
        lines.append(f"\n... {len(compounds) - limit:,} more. Raise limit (max 500).")
    return "\n".join(lines)


async def surechembl_search_patents(query: str, limit: int = 20) -> str:
    query = (query or "").strip()
    if not query:
        return "Error: query is required."
    limit = _clamp(limit, 20, 1, 200)
    try:
        total = await _run(sc.count_patents, query)
        hits = await _run(sc.search_patents, query, limit)
    except (ValueError, SureChEMBLError) as exc:
        # A Solr syntax error comes back with Solr's whole grammar expectation
        # list; the first line is the useful part ("Cannot parse 'ttl:' ...").
        return f"Error: {str(exc).splitlines()[0]}"
    if not hits:
        return f'No patents matched "{query}".'
    lines = [f'{total:,} patent(s) match "{query}" (SureChEMBL searches US, EP, WO, JP and CN publications); showing {len(hits)}.\n']
    lines.extend(_hit_line(h) for h in hits)
    lines.append("\nNext: surechembl_patent(doc_id) for a document; surechembl_patent_chemistry(doc_id) for its structures.")
    return "\n".join(lines)


async def surechembl_structure_search(structure: str, mode: str = "similarity", limit: int = 20) -> str:
    structure = (structure or "").strip()
    if not structure:
        return "Error: structure (a SMILES) is required."
    mode = (mode or "similarity").strip().lower()
    limit = _clamp(limit, 20, 1, 500)
    try:
        hits = await _run(sc.structure_search, structure, mode, limit)
    except (ValueError, SureChEMBLError) as exc:
        return f"Error: {exc}"
    if not hits:
        return f"No SureChEMBL compounds matched {structure} ({mode})."
    if mode == "similarity":
        hits = sorted(hits, key=lambda c: -(c.similarity or 0))
    lines = [f"{len(hits)} {mode} hit(s) for {structure}" + (f" (the first {limit}; raise limit, max 500)" if len(hits) >= limit else "") + ":\n"]
    lines.extend(_compound_line(c) for c in hits)
    lines.append("\nNext: surechembl_patents_for_compound(SCHEMBL id) for any hit's patents.")
    return "\n".join(lines)
